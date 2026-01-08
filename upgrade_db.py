from sqlalchemy import text
from models import engine

def upgrade_tasks_table():
    with engine.connect() as connection:
        try:
            # Add time_spent column
            connection.execute(text("ALTER TABLE tasks ADD COLUMN time_spent FLOAT DEFAULT 0.0"))
            print("Added time_spent column.")
        except Exception as e:
            print(f"Could not add time_spent: {e}")

        try:
            # Add completed_at column
            connection.execute(text("ALTER TABLE tasks ADD COLUMN completed_at VARCHAR(32)"))
            print("Added completed_at column.")
        except Exception as e:
            print(f"Could not add completed_at: {e}")

if __name__ == "__main__":
    upgrade_tasks_table()
