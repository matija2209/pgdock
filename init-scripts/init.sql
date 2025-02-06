-- Create the user only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exercise_user') THEN
        CREATE USER exercise_user WITH PASSWORD 'Ex3rc1seUs3r';
    END IF;
END
$$;

-- Ensure the database exists before proceeding
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'exercise') THEN
        RAISE NOTICE 'Database exercise does not exist. Skipping further setup.';
    END IF;
END
$$;

-- Grant privileges only if the database exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'exercise') THEN
        GRANT ALL PRIVILEGES ON DATABASE exercise TO exercise_user;
    END IF;
END
$$;

-- Switch to the database and grant schema-level permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'exercise') THEN
        PERFORM dblink_connect('dbname=exercise');
        -- Grant privileges on the public schema
        GRANT ALL PRIVILEGES ON SCHEMA public TO exercise_user;

        -- Grant privileges on existing tables, sequences, and functions
        GRANT ALL ON ALL TABLES IN SCHEMA public TO exercise_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO exercise_user;
        GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO exercise_user;

        -- Set default privileges for future objects
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO exercise_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO exercise_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO exercise_user;
    END IF;
END
$$;
