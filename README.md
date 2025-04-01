# PostgreSQL Database

This repository contains the database configuration for the PostgreSQL application.

## Connection Details

The database is accessible at:
```
postgresql://[username]:[password]@[host]:3147/[db_name]?schema=public
```

Default credentials (example):
- Host: localhost
- Port: 3147
- Database: [db_name]
- Username: db_user
- Password: db_password

## Environment Variables

The database configuration can be customized using environment variables. Create a `.env` file in the root directory with the following variables:

```env
DB_USER=db_user
DB_PASSWORD=db_password
DB_NAME=db_name
DB_PORT=3147
```

## How to Run

1. Make sure you have Docker and Docker Compose installed
2. Clone this repository
3. Navigate to the project directory
4. Create a `.env` file with your desired configuration
5. Generate the initialization script:
```bash
./generate-init.sh
```
6. Start the database:
```bash
docker compose up -d
```

The database will be available on the configured port (default: 3147).

## Configuration

### Changing Database Credentials

To change the database username and password:

1. Update the `.env` file with your new credentials
2. Regenerate the initialization script:
```bash
./generate-init.sh
```
3. Restart the container:
```bash
docker compose down -v
docker compose up -d
```

### Changing Port

To change the port mapping, update the `DB_PORT` variable in your `.env` file.

## Initialization Script

The database initialization is handled by a template-based system:

- `init-scripts/init.sql.template`: Template file with environment variable placeholders
- `init-scripts/init.sql`: Generated file (not tracked in git) containing the actual initialization SQL

To modify the initialization process:
1. Edit `init-scripts/init.sql.template`
2. Run `./generate-init.sh` to regenerate `init.sql`
3. Restart the container

## Health Check

The database includes a health check that runs every 10 seconds. You can check the container status with:
```bash
docker compose ps
```

2. Make the Script Executable
Run the following command to make the script executable:

bash
Copy code
chmod +x /home/server/exercise-db/backup.sh


Schedule the Script Using cron
Set up a cron job to run the backup script periodically. For example, to run the backup daily at 2:00 AM:

bash
Copy code
crontab -e
Add the following line to schedule the backup:

bash
Copy code
0 2 * * * /home/server/exercise-db/backup.sh
Save and exit.