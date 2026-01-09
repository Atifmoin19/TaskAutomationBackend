from sqlalchemy import text, create_engine
import os

# Define the database URL. 
# CRITICAL: This must match the connection inside the container or be accessible.
# The logs show psycopg2 errors, which means you are using POSTGRES, not SQLite.
# The error `psycopg2.errors.UndefinedColumn` confirms this.

# We need the DATABASE_URL. 
# Option 1: Try to read from env or default to the one likely used in docker-compose.
# Option 2: Ask user for it.
# I will try to infer it or create a general script that uses env var.

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/automation")

def upgrade_tasks_table():
    if "sqlite" in DATABASE_URL:
        print("Detected SQLite.")
        engine = create_engine(DATABASE_URL)
        col_type = "TEXT"
        add_col_stmt = f"ALTER TABLE tasks ADD COLUMN task_sessions {col_type}"
        default_stmt = "UPDATE tasks SET task_sessions = '[]' WHERE task_sessions IS NULL"
    else:
        print("Detected Postgres (or other).")
        engine = create_engine(DATABASE_URL)
        # Postgres supports JSON type directly
        col_type = "JSON"
        add_col_stmt = f"ALTER TABLE tasks ADD COLUMN task_sessions {col_type}"
        default_stmt = "UPDATE tasks SET task_sessions = '[]'::json WHERE task_sessions IS NULL"

    with engine.connect() as connection:
        try:
            print(f"Attempting to add column task_sessions ({col_type})...")
            connection.execute(text(add_col_stmt))
            print("Column added.")
            
            print("Setting default value for existing rows...")
            connection.execute(text(default_stmt))
            connection.commit()
            print("Done.")
            
        except Exception as e:
            print(f"Error: {e}")
            # If it fails, it might already exist or other error.
            # We can try to assume it exists and just update defaults?
            # But the error logs say "UndefinedColumn", so it definitely doesn't exist.

if __name__ == "__main__":
    print(f"Using Database: {DATABASE_URL}")
    upgrade_tasks_table()
