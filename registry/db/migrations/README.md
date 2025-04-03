# Database Migrations

This directory contains scripts to update the database schema.

## Running Migrations

Migrations are automatically run when the application starts. If you need to run migrations manually, you can use the following command:

```bash
python -m registry.db.migrations.run_migrations
```

## Available Migrations

- `add_claimed_to_providers`: Adds the `claimed` column to the providers table with a default value of `False`.

## Adding New Migrations

To add a new migration:

1. Create a new Python file in this directory with a descriptive name.
2. Define a `run_migration()` function that performs the migration.
3. Import and call the function in `run_migrations.py`.
4. Update this README to document the new migration. 