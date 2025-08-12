"""Main CLI module for pgdock."""

import os
import json
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .utils import (
    get_instance_dir, validate_name, generate_instance_name, generate_username,
    generate_password, find_free_port, is_port_free, check_docker, check_docker_compose,
    render_compose_template, save_metadata, load_metadata, get_container_status,
    get_container_health, update_pgpass, get_connection_string, list_instances,
    copy_to_clipboard
)

app = typer.Typer(help="PostgreSQL Docker instance manager")
console = Console()


@app.command()
def create(
    name: Optional[str] = typer.Option(None, "--name", help="Instance name"),
    version: str = typer.Option("latest", "--version", help="PostgreSQL version"),
    db_name: Optional[str] = typer.Option(None, "--db-name", help="Database name"),
    user: Optional[str] = typer.Option(None, "--user", help="Database user"),
    password: Optional[str] = typer.Option(None, "--password", help="Database password"),
    port: Optional[int] = typer.Option(None, "--port", help="Host port"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for container to be healthy"),
    json_out: Optional[str] = typer.Option(None, "--json-out", help="Save credentials to JSON file"),
    no_pgpass: bool = typer.Option(False, "--no-pgpass", help="Skip updating ~/.pgpass"),
    timeout: int = typer.Option(90, "--timeout", help="Health check timeout in seconds"),
    copy: bool = typer.Option(False, "--copy", help="Copy connection string to clipboard"),
):
    """Create and start a new PostgreSQL instance."""
    
    # Pre-flight checks
    docker_ok, docker_msg = check_docker()
    if not docker_ok:
        rprint(f"[red]Error:[/red] {docker_msg}")
        raise typer.Exit(1)
    
    compose_ok, compose_cmd, compose_warning = check_docker_compose()
    if not compose_ok:
        rprint(f"[red]Error:[/red] Docker Compose not available.")
        raise typer.Exit(1)
    
    if compose_warning:
        rprint(f"[yellow]Warning:[/yellow] {compose_warning}")
    
    # Generate or validate name
    if name is None:
        name = generate_instance_name()
    elif not validate_name(name):
        rprint("[red]Error:[/red] Name must match [a-z0-9-], max 30 chars. Example: pg-mydb.")
        raise typer.Exit(1)
    
    # Check if instance already exists
    instance_dir = get_instance_dir(name)
    if instance_dir.exists():
        rprint(f"[red]Error:[/red] Instance '{name}' already exists.")
        raise typer.Exit(1)
    
    # Check if container name conflicts
    container_name = f"pgdock-{name}"
    container_status = get_container_status(container_name)
    if container_status != 'not found':
        rprint(f"[red]Error:[/red] Container '{container_name}' already exists (status: {container_status}).")
        raise typer.Exit(1)
    
    # Generate credentials
    if user is None:
        user = generate_username()
    if password is None:
        password = generate_password()
    if db_name is None:
        db_name = name.replace('-', '_')
    
    # Validate database name
    if not db_name.replace('_', '').replace('-', '').isalnum():
        rprint("[red]Error:[/red] Database name must contain only letters, numbers, and underscores.")
        raise typer.Exit(1)
    
    # Port selection
    if port is None:
        port = find_free_port()
        if port is None:
            rprint("[red]Error:[/red] Could not find a free port. Please specify one with --port.")
            raise typer.Exit(1)
    else:
        if not is_port_free(port):
            rprint(f"[red]Error:[/red] Port {port} already in use. Re-run with different --port or omit to auto-pick.")
            raise typer.Exit(1)
    
    # Create instance directory
    instance_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate Docker Compose file
    service_name = f"pgdock-{name}"
    volume_name = f"pgdock_data_{name}"
    
    template_vars = {
        'service_name': service_name,
        'container_name': container_name,
        'version': version,
        'user': user,
        'password': password,
        'db_name': db_name,
        'port': port,
        'volume_name': volume_name,
    }
    
    compose_content = render_compose_template(template_vars)
    compose_file = instance_dir / 'compose.yml'
    
    with open(compose_file, 'w') as f:
        f.write(compose_content)
    
    # Start container
    rprint(f"[blue]Starting PostgreSQL instance '{name}'...[/blue]")
    
    try:
        cmd = compose_cmd.split() + ['-f', str(compose_file), 'up', '-d']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            rprint(f"[red]Error starting container:[/red]\n{result.stderr}")
            # Show logs for debugging
            logs_cmd = compose_cmd.split() + ['-f', str(compose_file), 'logs', '--no-color']
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=30)
            if logs_result.stdout:
                rprint("[yellow]Container logs:[/yellow]")
                rprint(logs_result.stdout[-1000:])  # Last 1000 chars
            raise typer.Exit(1)
    
    except subprocess.TimeoutExpired:
        rprint("[red]Error:[/red] Timeout starting container.")
        raise typer.Exit(1)
    
    # Wait for health check if requested
    if wait:
        rprint("[blue]Waiting for PostgreSQL to be ready...[/blue]")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            health = get_container_health(container_name)
            if health == 'healthy':
                break
            elif health in ['unhealthy', 'not found']:
                rprint(f"[red]Error:[/red] Container became {health}")
                # Show recent logs
                logs_cmd = compose_cmd.split() + ['-f', str(compose_file), 'logs', '--tail', '50', '--no-color']
                logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=30)
                if logs_result.stdout:
                    rprint("[yellow]Recent logs:[/yellow]")
                    rprint(logs_result.stdout)
                raise typer.Exit(1)
            
            time.sleep(2)
        else:
            rprint(f"[red]Error:[/red] PostgreSQL did not become healthy within {timeout}s.")
            # Show recent logs for debugging
            logs_cmd = compose_cmd.split() + ['-f', str(compose_file), 'logs', '--tail', '50', '--no-color']
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=30)
            if logs_result.stdout:
                rprint("[yellow]Recent logs:[/yellow]")
                rprint(logs_result.stdout)
            raise typer.Exit(1)
    
    # Generate metadata
    connection_string = get_connection_string(user, password, 'localhost', port, db_name)
    created_at = time.time()
    
    metadata = {
        'name': name,
        'version': version,
        'port': port,
        'db': db_name,
        'user': user,
        'password': password,
        'container': container_name,
        'volume': volume_name,
        'createdAt': created_at,
        'composeFile': str(compose_file),
        'connectionString': connection_string,
    }
    
    # Save metadata
    save_metadata(instance_dir, metadata)
    
    # Update ~/.pgpass
    if not no_pgpass:
        try:
            update_pgpass('localhost', port, db_name, user, password)
        except Exception as e:
            rprint(f"[yellow]Warning:[/yellow] Could not update ~/.pgpass: {e}")
    
    # Save JSON output if requested
    json_output_path = None
    if json_out:
        json_output_path = Path(json_out)
        try:
            with open(json_output_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
        except Exception as e:
            rprint(f"[yellow]Warning:[/yellow] Could not save JSON to {json_out}: {e}")
    
    # Print success message
    rprint("[green]✓[/green] PostgreSQL instance created successfully!")
    rprint()
    
    # Instance details table
    table = Table(title=f"Instance: {name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Name", name)
    table.add_row("Version", version)
    table.add_row("Port", str(port))
    table.add_row("Database", db_name)
    table.add_row("User", user)
    table.add_row("Container", container_name)
    table.add_row("Volume", volume_name)
    table.add_row("Status", "Running" if wait else "Started")
    
    console.print(table)
    rprint()
    
    # Connection details
    rprint("[bold]Connection String:[/bold]")
    rprint(f"  {connection_string}")
    rprint()
    
    rprint("[bold]Individual Connection Details:[/bold]")
    rprint(f"  Host: localhost")
    rprint(f"  Port: {port}")
    rprint(f"  Database: {db_name}")
    rprint(f"  User: {user}")
    rprint(f"  Password: {password}")
    rprint()
    
    # File locations
    rprint("[bold]Files:[/bold]")
    rprint(f"  Metadata: {instance_dir / 'metadata.json'}")
    rprint(f"  Compose: {compose_file}")
    if json_output_path:
        rprint(f"  JSON Output: {json_output_path}")
    if not no_pgpass:
        rprint(f"  Updated ~/.pgpass")
    
    # Copy to clipboard if requested
    if copy:
        if copy_to_clipboard(connection_string):
            rprint(f"[green]✓[/green] Connection string copied to clipboard")
        else:
            rprint(f"[yellow]Warning:[/yellow] Could not copy to clipboard")


@app.command()
def list():
    """List all PostgreSQL instances."""
    instances = list_instances()
    
    if not instances:
        rprint("[yellow]No instances found.[/yellow]")
        return
    
    table = Table(title="PostgreSQL Instances")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="blue")
    table.add_column("Port", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Created", style="dim")
    
    for instance in instances:
        created_time = ""
        if 'createdAt' in instance:
            try:
                import datetime
                created_time = datetime.datetime.fromtimestamp(instance['createdAt']).strftime('%Y-%m-%d %H:%M')
            except:
                created_time = "unknown"
        
        status_color = "green" if instance.get('status') == 'running' else "red"
        status = f"[{status_color}]{instance.get('status', 'unknown')}[/{status_color}]"
        
        table.add_row(
            instance['name'],
            instance.get('version', 'unknown'),
            str(instance.get('port', 'unknown')),
            status,
            created_time
        )
    
    console.print(table)


@app.command()
def status(
    name: str = typer.Argument(help="Instance name"),
):
    """Show detailed status of a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    # Get current status
    container_status = get_container_status(metadata['container'])
    container_health = get_container_health(metadata['container'])
    
    # Status table
    table = Table(title=f"Instance Status: {name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Name", name)
    table.add_row("Version", metadata.get('version', 'unknown'))
    table.add_row("Container", metadata['container'])
    table.add_row("Volume", metadata['volume'])
    table.add_row("Port", str(metadata.get('port', 'unknown')))
    table.add_row("Database", metadata.get('db', 'unknown'))
    table.add_row("User", metadata.get('user', 'unknown'))
    
    # Status with colors
    status_color = "green" if container_status == 'running' else "red"
    table.add_row("Container Status", f"[{status_color}]{container_status}[/{status_color}]")
    
    health_color = "green" if container_health == 'healthy' else "yellow" if container_health == 'starting' else "red"
    table.add_row("Health Status", f"[{health_color}]{container_health}[/{health_color}]")
    
    # Created time
    if 'createdAt' in metadata:
        try:
            import datetime
            created_time = datetime.datetime.fromtimestamp(metadata['createdAt']).strftime('%Y-%m-%d %H:%M:%S')
            table.add_row("Created", created_time)
        except:
            pass
    
    console.print(table)
    
    if container_status == 'running':
        rprint()
        rprint("[bold]Connection String:[/bold]")
        rprint(f"  {metadata.get('connectionString', 'N/A')}")


@app.command()
def creds(
    name: str = typer.Argument(help="Instance name"),
    json_format: bool = typer.Option(False, "--json", help="Output in JSON format"),
    copy: bool = typer.Option(False, "--copy", help="Copy connection string to clipboard"),
):
    """Show credentials for a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    if json_format:
        # Output JSON to stdout
        creds_data = {
            'name': metadata['name'],
            'host': 'localhost',
            'port': metadata['port'],
            'database': metadata['db'],
            'user': metadata['user'],
            'password': metadata['password'],
            'connectionString': metadata['connectionString']
        }
        print(json.dumps(creds_data, indent=2))
    else:
        # Human readable output
        rprint(f"[bold]Credentials for instance: {name}[/bold]")
        rprint()
        rprint(f"[cyan]Host:[/cyan] localhost")
        rprint(f"[cyan]Port:[/cyan] {metadata['port']}")
        rprint(f"[cyan]Database:[/cyan] {metadata['db']}")
        rprint(f"[cyan]User:[/cyan] {metadata['user']}")
        rprint(f"[cyan]Password:[/cyan] {metadata['password']}")
        rprint()
        rprint(f"[cyan]Connection String:[/cyan]")
        rprint(f"  {metadata['connectionString']}")
    
    # Copy to clipboard if requested
    if copy:
        connection_string = metadata.get('connectionString', '')
        if connection_string and copy_to_clipboard(connection_string):
            rprint(f"[green]✓[/green] Connection string copied to clipboard")
        else:
            rprint(f"[yellow]Warning:[/yellow] Could not copy to clipboard")


@app.command()
def start(
    name: str = typer.Argument(help="Instance name"),
):
    """Start a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    compose_file = instance_dir / 'compose.yml'
    if not compose_file.exists():
        rprint(f"[red]Error:[/red] Compose file not found for instance '{name}'.")
        raise typer.Exit(1)
    
    compose_ok, compose_cmd, _ = check_docker_compose()
    if not compose_ok:
        rprint(f"[red]Error:[/red] Docker Compose not available.")
        raise typer.Exit(1)
    
    try:
        cmd = compose_cmd.split() + ['-f', str(compose_file), 'up', '-d']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            rprint(f"[red]Error starting instance:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        
        rprint(f"[green]✓[/green] Instance '{name}' started successfully.")
        
    except subprocess.TimeoutExpired:
        rprint("[red]Error:[/red] Timeout starting instance.")
        raise typer.Exit(1)


@app.command()
def stop(
    name: str = typer.Argument(help="Instance name"),
):
    """Stop a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    compose_file = instance_dir / 'compose.yml'
    if not compose_file.exists():
        rprint(f"[red]Error:[/red] Compose file not found for instance '{name}'.")
        raise typer.Exit(1)
    
    compose_ok, compose_cmd, _ = check_docker_compose()
    if not compose_ok:
        rprint(f"[red]Error:[/red] Docker Compose not available.")
        raise typer.Exit(1)
    
    try:
        cmd = compose_cmd.split() + ['-f', str(compose_file), 'stop']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            rprint(f"[red]Error stopping instance:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        
        rprint(f"[green]✓[/green] Instance '{name}' stopped successfully.")
        
    except subprocess.TimeoutExpired:
        rprint("[red]Error:[/red] Timeout stopping instance.")
        raise typer.Exit(1)


@app.command()
def destroy(
    name: str = typer.Argument(help="Instance name"),
    purge_volume: bool = typer.Option(False, "--purge-volume", help="Also remove the data volume"),
    remove_config: bool = typer.Option(False, "--remove-config", help="Also remove instance configuration files"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
):
    """Destroy a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    # Confirmation prompts
    if not force:
        rprint(f"[yellow]Warning:[/yellow] This will destroy instance '{name}'.")
        if not typer.confirm("Continue?"):
            rprint("Cancelled.")
            raise typer.Exit(0)
    
    compose_file = instance_dir / 'compose.yml'
    compose_ok, compose_cmd, _ = check_docker_compose()
    
    if not compose_ok:
        rprint(f"[red]Error:[/red] Docker Compose not available.")
        raise typer.Exit(1)
    
    # Stop and remove container
    if compose_file.exists():
        try:
            cmd = compose_cmd.split() + ['-f', str(compose_file), 'down']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                rprint(f"[yellow]Warning:[/yellow] Error stopping container: {result.stderr}")
            else:
                rprint(f"[green]✓[/green] Container stopped and removed.")
                
        except subprocess.TimeoutExpired:
            rprint("[yellow]Warning:[/yellow] Timeout stopping container.")
    
    # Remove volume if requested
    if purge_volume:
        if not force:
            rprint(f"[yellow]Warning:[/yellow] This will permanently delete all data in volume '{metadata['volume']}'.")
            if not typer.confirm("Continue with volume deletion?"):
                rprint("Volume preservation - instance destroyed but data kept.")
                return
        
        try:
            result = subprocess.run([
                'docker', 'volume', 'rm', metadata['volume']
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                rprint(f"[green]✓[/green] Volume '{metadata['volume']}' removed.")
            else:
                rprint(f"[yellow]Warning:[/yellow] Could not remove volume: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            rprint("[yellow]Warning:[/yellow] Timeout removing volume.")
    
    # Remove configuration files if requested
    if remove_config:
        if not force:
            rprint(f"[yellow]Warning:[/yellow] This will remove all configuration files for instance '{name}'.")
            if not typer.confirm("Continue with config deletion?"):
                rprint("Configuration files preserved.")
                return
        
        try:
            shutil.rmtree(instance_dir)
            rprint(f"[green]✓[/green] Configuration files removed.")
        except Exception as e:
            rprint(f"[yellow]Warning:[/yellow] Could not remove config files: {e}")
    
    rprint(f"[green]✓[/green] Instance '{name}' destroyed.")


@app.command()
def backup(
    name: str = typer.Argument(help="Instance name"),
    dest_dir: str = typer.Argument(help="Destination directory for backup"),
    format: str = typer.Option("sql", "--format", help="Backup format: sql or custom"),
    retention_days: Optional[int] = typer.Option(None, "--retention-days", help="Delete backups older than N days"),
    json_output: bool = typer.Option(False, "--json", help="Output result in JSON format"),
):
    """Backup a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    # Check if container is running
    container_status = get_container_status(metadata['container'])
    if container_status != 'running':
        rprint(f"[red]Error:[/red] Instance '{name}' is not running (status: {container_status}).")
        raise typer.Exit(1)
    
    # Validate and create destination directory
    dest_path = Path(dest_dir)
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        # Test write access
        test_file = dest_path / '.pgdock_write_test'
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        rprint(f"[red]Error:[/red] Cannot write to destination directory: {e}")
        raise typer.Exit(1)
    
    # Generate backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = 'sql' if format == 'sql' else 'dump'
    backup_filename = f"{name}_{timestamp}.{ext}"
    backup_path = dest_path / backup_filename
    
    # Prepare pg_dump command
    if format == 'sql':
        dump_cmd = f"pg_dump -U {metadata['user']} -d {metadata['db']}"
    else:  # custom format
        dump_cmd = f"pg_dump -Fc -U {metadata['user']} -d {metadata['db']}"
    
    # Execute backup
    try:
        rprint(f"[blue]Creating backup of instance '{name}'...[/blue]")
        
        # Run pg_dump inside the container and redirect output to host file
        result = subprocess.run([
            'docker', 'exec', metadata['container'], 'sh', '-c', dump_cmd
        ], stdout=open(backup_path, 'wb'), stderr=subprocess.PIPE, timeout=300)
        
        if result.returncode != 0:
            rprint(f"[red]Error creating backup:[/red]\n{result.stderr.decode()}")
            # Clean up failed backup file
            if backup_path.exists():
                backup_path.unlink()
            raise typer.Exit(1)
        
        backup_size = backup_path.stat().st_size
        rprint(f"[green]✓[/green] Backup created: {backup_path} ({backup_size:,} bytes)")
        
    except subprocess.TimeoutExpired:
        rprint("[red]Error:[/red] Backup operation timed out.")
        if backup_path.exists():
            backup_path.unlink()
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error:[/red] Backup failed: {e}")
        if backup_path.exists():
            backup_path.unlink()
        raise typer.Exit(1)
    
    # Handle retention policy
    if retention_days is not None:
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        pattern = f"{name}_*.{ext}"
        
        deleted_count = 0
        for old_backup in dest_path.glob(pattern):
            try:
                # Skip the file we just created
                if old_backup == backup_path:
                    continue
                
                file_mtime = datetime.fromtimestamp(old_backup.stat().st_mtime)
                if file_mtime < cutoff_date:
                    old_backup.unlink()
                    deleted_count += 1
            except Exception:
                continue  # Skip files we can't process
        
        if deleted_count > 0:
            rprint(f"[blue]Cleaned up {deleted_count} old backup(s) (retention: {retention_days} days)[/blue]")
    
    # Output results
    result_data = {
        'instance': name,
        'backup_path': str(backup_path),
        'size_bytes': backup_size,
        'format': format,
        'created_at': timestamp
    }
    
    if json_output:
        print(json.dumps(result_data, indent=2))
    else:
        rprint()
        rprint("[bold]Backup Summary:[/bold]")
        rprint(f"  Instance: {name}")
        rprint(f"  File: {backup_path}")
        rprint(f"  Size: {backup_size:,} bytes")
        rprint(f"  Format: {format}")


@app.command()
def logs(
    name: str = typer.Argument(help="Instance name"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: Optional[int] = typer.Option(None, "--lines", "-n", help="Number of lines to show"),
):
    """Show logs for a PostgreSQL instance."""
    instance_dir = get_instance_dir(name)
    metadata = load_metadata(instance_dir)
    
    if not metadata:
        rprint(f"[red]Error:[/red] Instance '{name}' not found.")
        raise typer.Exit(1)
    
    compose_file = instance_dir / 'compose.yml'
    if not compose_file.exists():
        rprint(f"[red]Error:[/red] Compose file not found for instance '{name}'.")
        raise typer.Exit(1)
    
    compose_ok, compose_cmd, _ = check_docker_compose()
    if not compose_ok:
        rprint(f"[red]Error:[/red] Docker Compose not available.")
        raise typer.Exit(1)
    
    # Build logs command
    cmd = compose_cmd.split() + ['-f', str(compose_file), 'logs', '--no-color']
    
    if follow:
        cmd.append('-f')
    
    if lines is not None:
        cmd.extend(['--tail', str(lines)])
    
    try:
        # For follow mode, we need to handle interruption gracefully
        if follow:
            process = subprocess.Popen(cmd)
            try:
                process.wait()
            except KeyboardInterrupt:
                process.terminate()
                rprint("\n[blue]Log following stopped.[/blue]")
        else:
            result = subprocess.run(cmd, timeout=30)
            if result.returncode != 0:
                rprint(f"[red]Error retrieving logs.[/red]")
                raise typer.Exit(1)
                
    except subprocess.TimeoutExpired:
        rprint("[red]Error:[/red] Timeout retrieving logs.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()