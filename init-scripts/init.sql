-- Create the user only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'as_spa_admin') THEN
        CREATE USER as_spa_admin WITH PASSWORD '71k7j2qc5E';
    END IF;
END
$$;

-- Ensure the database exists before proceeding
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'as_spa') THEN
        CREATE DATABASE as_spa;
    END IF;
END
$$;

-- Grant privileges only if the database exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'as_spa') THEN
        GRANT ALL PRIVILEGES ON DATABASE as_spa TO as_spa_admin;
    END IF;
END
$$;

-- Switch to the database and grant schema-level permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'as_spa') THEN
        PERFORM dblink_connect('dbname=as_spa');
        -- Grant privileges on the public schema
        GRANT ALL PRIVILEGES ON SCHEMA public TO as_spa_admin;

        -- Grant privileges on existing tables, sequences, and functions
        GRANT ALL ON ALL TABLES IN SCHEMA public TO as_spa_admin;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO as_spa_admin;
        GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO as_spa_admin;

        -- Set default privileges for future objects
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO as_spa_admin;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO as_spa_admin;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO as_spa_admin;
    END IF;
END
$$; 