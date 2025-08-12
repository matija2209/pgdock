# pgdock - PostgreSQL Docker Instance Manager

A CLI tool for managing PostgreSQL Docker instances with automatic credential generation, health checking, and backup capabilities.

## Features

- **Easy Instance Management**: Create, start, stop, and destroy PostgreSQL instances with simple commands
- **Automatic Setup**: Generates secure credentials, picks free ports, and handles Docker Compose configuration
- **Health Monitoring**: Built-in health checks with timeout handling
- **Backup & Restore**: Built-in backup functionality with retention policies
- **Multiple Formats**: Human-readable output and JSON support
- **Cross-Platform**: Works on macOS and Ubuntu with Docker Desktop or Docker Engine

## Installation

### Via pip (recommended)

```bash
pip install pgdock
```

### Development Installation

```bash
git clone https://github.com/matija2209/postgres-docker-db
cd postgres-docker-db
pip install -e .
```

### Requirements

- Python 3.10+
- Docker Engine (Ubuntu) or Docker Desktop (macOS)
- Docker Compose v2 (or legacy docker-compose)

## Quick Start

### Create a New Instance

```bash
# Create with auto-generated name and credentials
pgdock create

# Create with custom name
pgdock create --name mydb

# Create with specific version and port
pgdock create --name mydb --version 16 --port 5433
```

### Connect to Your Database

```bash
# Get connection details
pgdock creds mydb

# Get connection string in JSON format
pgdock creds mydb --json

# Copy connection string to clipboard
pgdock creds mydb --copy

# Connect with psql using the connection string
psql "$(pgdock creds mydb --json | jq -r .connectionString)"
```

### List All Instances

```bash
pgdock list
```

### Check Instance Status

```bash
pgdock status mydb
```

## Command Reference

### `pgdock create`

Create and start a new PostgreSQL instance.

```bash
pgdock create [OPTIONS]
```

**Options:**
- `--name TEXT`: Instance name (auto-generated if not provided)
- `--version TEXT`: PostgreSQL version (default: "latest")
- `--db-name TEXT`: Database name (defaults to instance name)
- `--user TEXT`: Database user (auto-generated if not provided)
- `--password TEXT`: Database password (auto-generated if not provided)
- `--port INTEGER`: Host port (auto-picked if not provided)
- `--wait/--no-wait`: Wait for container to be healthy (default: --wait)
- `--json-out PATH`: Save credentials to JSON file
- `--no-pgpass`: Skip updating ~/.pgpass
- `--timeout INTEGER`: Health check timeout in seconds (default: 90)
- `--copy`: Copy connection string to clipboard

**Example:**
```bash
pgdock create --name myapp --version 15 --port 5433 --copy
```

### `pgdock list`

List all PostgreSQL instances with their status.

```bash
pgdock list
```

### `pgdock status`

Show detailed status of a PostgreSQL instance.

```bash
pgdock status INSTANCE_NAME
```

### `pgdock creds`

Show credentials for a PostgreSQL instance.

```bash
pgdock creds INSTANCE_NAME [OPTIONS]
```

**Options:**
- `--json`: Output in JSON format
- `--copy`: Copy connection string to clipboard

### `pgdock start/stop`

Start or stop a PostgreSQL instance.

```bash
pgdock start INSTANCE_NAME
pgdock stop INSTANCE_NAME
```

### `pgdock destroy`

Destroy a PostgreSQL instance.

```bash
pgdock destroy INSTANCE_NAME [OPTIONS]
```

**Options:**
- `--purge-volume`: Also remove the data volume
- `--remove-config`: Also remove instance configuration files
- `--force`: Skip confirmation prompts

### `pgdock backup`

Create a backup of a PostgreSQL instance.

```bash
pgdock backup INSTANCE_NAME DEST_DIR [OPTIONS]
```

**Options:**
- `--format TEXT`: Backup format: "sql" or "custom" (default: "sql")
- `--retention-days INTEGER`: Delete backups older than N days
- `--json`: Output result in JSON format

**Example:**
```bash
pgdock backup mydb ./backups --format custom --retention-days 30
```

### `pgdock logs`

Show logs for a PostgreSQL instance.

```bash
pgdock logs INSTANCE_NAME [OPTIONS]
```

**Options:**
- `--follow, -f`: Follow log output
- `--lines, -n INTEGER`: Number of lines to show

## Configuration

### Environment Variables

- `PGDOCK_HOME`: Override default home directory (`~/.pgdock`)

### Instance Storage

pgdock stores instance configurations in `~/.pgdock/instances/`. Each instance has:

- `compose.yml`: Docker Compose configuration
- `metadata.json`: Instance metadata and credentials

### PostgreSQL Credentials

- **Automatic ~/.pgpass Updates**: pgdock automatically updates your `~/.pgpass` file
- **Secure Generation**: Passwords are 20 characters with URL-safe characters
- **Username Pattern**: `u_<8_random_chars>`

## Backup and Retention

pgdock includes built-in backup functionality:

```bash
# Create SQL backup
pgdock backup mydb /path/to/backups

# Create custom format backup with retention
pgdock backup mydb /path/to/backups --format custom --retention-days 7

# JSON output for scripting
pgdock backup mydb /path/to/backups --json
```

**Backup Filename Format**: `{instance_name}_{YYYYMMDD_HHMMSS}.{ext}`

**Retention Policy**: Automatically deletes backups older than specified days, only affecting files matching the instance name pattern.

## Troubleshooting

### Docker Permission Issues (Linux)

If you get permission errors:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Port Conflicts

pgdock automatically finds free ports starting from 5400. To use a specific port:

```bash
pgdock create --port 5433
```

### Health Check Timeouts

If instances fail to start:

1. Check Docker container logs: `pgdock logs instance_name`
2. Verify port availability
3. Check Docker daemon status
4. Increase timeout: `pgdock create --timeout 120`

### Docker Compose Version

pgdock supports both:
- `docker compose` (v2, recommended)
- `docker-compose` (legacy, with warning)

## Migration from Manual Docker Setup

If you're migrating from a manual Docker Compose setup to pgdock:

1. **Stop existing containers**:
   ```bash
   docker compose down
   ```

2. **Install pgdock**:
   ```bash
   pip install pgdock
   ```

3. **Create new managed instance**:
   ```bash
   pgdock create --name mydb --port 5432
   ```

4. **Migrate data** (if needed):
   ```bash
   # Export from old container
   docker exec old_container pg_dump -U user dbname > backup.sql
   
   # Import to new instance  
   psql "$(pgdock creds mydb --json | jq -r .connectionString)" < backup.sql
   ```

## Examples

### Development Workflow

```bash
# Create a development database
pgdock create --name devdb --version 15

# Get connection details for your app
pgdock creds devdb --json

# Check if it's running
pgdock status devdb

# Create a backup before making changes
pgdock backup devdb ./backups

# View recent logs
pgdock logs devdb --lines 50

# Stop when done
pgdock stop devdb
```

### Production-like Setup

```bash
# Create production-like instance
pgdock create --name proddb --version 16 --port 5432

# Create daily backups with retention
pgdock backup proddb /var/backups/postgres --retention-days 30

# Monitor health
pgdock status proddb
```

### Multiple Instances

```bash
# Create multiple versions for testing
pgdock create --name test-pg14 --version 14
pgdock create --name test-pg15 --version 15
pgdock create --name test-pg16 --version 16

# List all instances
pgdock list

# Connect to specific version
psql "$(pgdock creds test-pg15 --json | jq -r .connectionString)"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[License Type] - see LICENSE file for details.