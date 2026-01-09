from sqlalchemy import text
from models import engine
import sqlalchemy

def upgrade_tasks_table():
    with engine.connect() as connection:
        try:
            # Determine column type based on dialect
            dialect = engine.dialect.name
            col_type = "JSON"
            if dialect == 'sqlite':
                # SQLite usually stores JSON as TEXT, but allows 'JSON' as type name too usually.
                # To be consistent with SQLAlchemy's handling, TEXT is safe, but let's try JSON first or CHECK constraint?
                # Simplest is just add column.
                col_type = "TEXT" # Safe fallback for SQLite to store stringified JSON
            
            sql = f"ALTER TABLE tasks ADD COLUMN task_sessions {col_type}"
            connection.execute(text(sql))
            print(f"Added task_sessions column ({col_type}).")
            
            # Since we replaced the list default in Python, existing rows might be NULL. 
            # We might want to update them to empty list '[]' ?
            # SQLite: UPDATE tasks SET task_sessions = '[]' WHERE task_sessions IS NULL;
            # Postgres: UPDATE tasks SET task_sessions = '[]'::json WHERE task_sessions IS NULL;
            
            if dialect == 'sqlite':
                connection.execute(text("UPDATE tasks SET task_sessions = '[]' WHERE task_sessions IS NULL"))
            else:
                 connection.execute(text("UPDATE tasks SET task_sessions = '[]'::json WHERE task_sessions IS NULL"))
            
            connection.commit()
            print("Initialized NULL sessions to [].")
            
        except Exception as e:
            print(f"Could not add task_sessions: {e}")

if __name__ == "__main__":
    upgrade_tasks_table()
