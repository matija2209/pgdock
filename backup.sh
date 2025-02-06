#!/bin/bash

# Configuration
BACKUP_DIR="/home/server/backups/exercise"
DB_CONTAINER_NAME="exercise-db"
DB_USER="exercise_admin"
DB_NAME="exercise"

# Timestamp for the backup filename
TIMESTAMP=$(date +"%Y%m%d%H%M%S")

# Ensure the backup directory exists
mkdir -p "$BACKUP_DIR"

# Run the pg_dump command inside the Docker container and save the dump outside Docker
docker exec "$DB_CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/backup_$TIMESTAMP.sql"

# Optional: Remove backups older than 30 days
find "$BACKUP_DIR" -type f -name "backup_exercise_*.sql" -mtime +30 -exec rm {} \;
