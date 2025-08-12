"""Utility functions for pgdock."""

import os
import json
import random
import string
import socket
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import yaml
from jinja2 import Environment, FileSystemLoader


def get_pgdock_home() -> Path:
    """Get the pgdock home directory."""
    home = os.environ.get('PGDOCK_HOME')
    if home:
        return Path(home).expanduser()
    return Path.home() / '.pgdock'


def get_instances_dir() -> Path:
    """Get the instances directory."""
    instances_dir = get_pgdock_home() / 'instances'
    instances_dir.mkdir(parents=True, exist_ok=True)
    return instances_dir


def get_instance_dir(name: str) -> Path:
    """Get the directory for a specific instance."""
    return get_instances_dir() / name


def validate_name(name: str) -> bool:
    """Validate instance name format."""
    if not name:
        return False
    if len(name) > 30:
        return False
    return all(c.isalnum() or c == '-' for c in name) and name[0].isalnum()


def generate_instance_name() -> str:
    """Generate a random instance name."""
    adjectives = ['quick', 'bright', 'swift', 'cool', 'warm', 'smart', 'fast', 'calm']
    animals = ['tiger', 'eagle', 'shark', 'wolf', 'hawk', 'fox', 'bear', 'owl']
    
    adj = random.choice(adjectives)
    animal = random.choice(animals)
    return f"pg-{adj}-{animal}"


def generate_username() -> str:
    """Generate a random username."""
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(random.choices(chars, k=8))
    return f"u_{suffix}"


def generate_password() -> str:
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits + '_-.~'
    return ''.join(random.choices(chars, k=20))


def find_free_port(start_port: int = 5400, max_attempts: int = 100) -> Optional[int]:
    """Find a free port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return port
        except OSError:
            continue
    return None


def is_port_free(port: int) -> bool:
    """Check if a port is free."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('localhost', port))
            return True
    except OSError:
        return False


def check_docker() -> tuple[bool, str]:
    """Check if Docker is available and accessible."""
    if not shutil.which('docker'):
        return False, "Docker not found. Please install Docker Engine (Ubuntu) or Docker Desktop (macOS)."
    
    try:
        result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, "Docker daemon not running or not accessible. On Linux, ensure you're in the docker group."
        return True, ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "Docker not responding. Please check Docker installation."


def check_docker_compose() -> tuple[bool, str, str]:
    """Check docker compose availability and return the command to use."""
    # Try docker compose (newer)
    try:
        result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "docker compose", ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Try docker-compose (legacy)
    try:
        result = subprocess.run(['docker-compose', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "docker-compose", "Warning: Using legacy docker-compose command. Consider upgrading to Docker Compose v2."
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return False, "", "Docker Compose not found. Please install Docker Compose."


def render_compose_template(template_vars: Dict[str, Any]) -> str:
    """Render the Docker Compose template."""
    # Get the templates directory relative to this file
    template_dir = Path(__file__).parent.parent / 'templates'
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template('compose.yml.j2')
    return template.render(**template_vars)


def save_metadata(instance_dir: Path, metadata: Dict[str, Any]) -> None:
    """Save instance metadata to JSON file."""
    metadata_file = instance_dir / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)


def load_metadata(instance_dir: Path) -> Optional[Dict[str, Any]]:
    """Load instance metadata from JSON file."""
    metadata_file = instance_dir / 'metadata.json'
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_container_status(container_name: str) -> str:
    """Get the status of a Docker container."""
    try:
        result = subprocess.run([
            'docker', 'inspect', '--format', '{{.State.Status}}', container_name
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            return result.stdout.strip()
        return 'not found'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 'unknown'


def get_container_health(container_name: str) -> str:
    """Get the health status of a Docker container."""
    try:
        result = subprocess.run([
            'docker', 'inspect', '--format', '{{.State.Health.Status}}', container_name
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            health = result.stdout.strip()
            return health if health != '<no value>' else 'no health check'
        return 'unknown'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 'unknown'


def update_pgpass(host: str, port: int, db: str, user: str, password: str) -> None:
    """Update ~/.pgpass file with connection credentials."""
    pgpass_file = Path.home() / '.pgpass'
    entry = f"{host}:{port}:{db}:{user}:{password}"
    
    # Create backup if file exists
    if pgpass_file.exists():
        backup_file = Path.home() / '.pgpass.bak'
        shutil.copy2(pgpass_file, backup_file)
        
        # Read existing entries
        with open(pgpass_file, 'r') as f:
            existing_lines = f.read().splitlines()
        
        # Check if entry already exists
        if entry in existing_lines:
            return
        
        # Append new entry
        with open(pgpass_file, 'a') as f:
            f.write(f"\n{entry}")
    else:
        # Create new file
        with open(pgpass_file, 'w') as f:
            f.write(f"{entry}\n")
    
    # Set proper permissions
    pgpass_file.chmod(0o600)


def get_connection_string(user: str, password: str, host: str, port: int, db: str) -> str:
    """Generate PostgreSQL connection string."""
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?schema=public"


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard. Returns True if successful."""
    import platform
    
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(['pbcopy'], input=text, text=True, check=True, timeout=5)
            return True
        elif system == "Linux":
            # Try wl-copy first (Wayland), then xclip (X11)
            if shutil.which('wl-copy'):
                subprocess.run(['wl-copy'], input=text, text=True, check=True, timeout=5)
                return True
            elif shutil.which('xclip'):
                subprocess.run(['xclip', '-selection', 'clipboard'], input=text, text=True, check=True, timeout=5)
                return True
            return False
        else:
            return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def list_instances() -> List[Dict[str, Any]]:
    """List all managed instances."""
    instances_dir = get_instances_dir()
    instances = []
    
    for instance_path in instances_dir.iterdir():
        if instance_path.is_dir():
            metadata = load_metadata(instance_path)
            if metadata:
                # Update status
                container_status = get_container_status(metadata['container'])
                metadata['status'] = container_status
                instances.append(metadata)
    
    return instances