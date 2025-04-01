#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if required environment variables are set
if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ]; then
    echo "Error: Required environment variables are not set"
    echo "Please make sure DB_USER, DB_PASSWORD, and DB_NAME are set in .env file"
    exit 1
fi

# Generate init.sql from template
envsubst < init-scripts/init.sql.template > init-scripts/init.sql

echo "Generated init.sql with environment variables" 