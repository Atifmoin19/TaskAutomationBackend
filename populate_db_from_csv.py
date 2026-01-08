
import csv
from datetime import datetime
from models import SessionLocal, User as UserModel, Task as TaskModel, Foundation

db = SessionLocal()

def import_users():
    print("Importing Users...")
    with open('users.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            emp_id = row.get("emp_id")
            if not emp_id:
                continue

            existing = db.query(UserModel).filter(UserModel.emp_id == emp_id).first()
            if not existing:
                try:
                    new_user = UserModel(
                        emp_id=emp_id,
                        emp_name=row.get("emp_name"),
                        emp_email=row.get("emp_email"),
                        emp_phone=row.get("emp_phone"),
                        emp_designation=row.get("emp_designation"),
                        emp_department=row.get("emp_department"),
                        emp_hierarchy=row.get("emp_hierarchy"),
                        manager_id=row.get("manager_id") if row.get("manager_id") != "NULL" else None
                    )
                    db.add(new_user)
                    db.commit()
                    print(f"Added User: {emp_id}")
                except Exception as e:
                    print(f"Error adding user {emp_id}: {e}")
                    db.rollback()
            else:
                print(f"User {emp_id} already exists.")

def import_foundation():
    print("\nImporting Foundation...")
    with open('foundation.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            emp_id = row.get("emp_id")
            if not emp_id:
                continue
            
            # Ensure user exists first (FK constraint usually)
            user_exists = db.query(UserModel).filter(UserModel.emp_id == emp_id).first()
            if not user_exists:
                print(f"Skipping Foundation for {emp_id} - User not found in Users table.")
                continue

            existing = db.query(Foundation).filter(Foundation.emp_id == emp_id).first()
            if not existing:
                try:
                    new_found = Foundation(
                        emp_id=emp_id,
                        password=row.get("password"),
                        token=row.get("token") if row.get("token") != "NULL" else None
                    )
                    db.add(new_found)
                    db.commit()
                    print(f"Added Foundation for: {emp_id}")
                except Exception as e:
                    print(f"Error adding foundation {emp_id}: {e}")
                    db.rollback()
            else:
                 print(f"Foundation {emp_id} already exists.")


def create_missing_users_from_tasks(reader):
    # Tasks might reference users NOT in users.csv (e.g. S00218, S00625 mentioned in tasks.csv but maybe missed in users.csv import)
    # We scan tasks first to create dummy users if needed?
    # Actually users.csv seems to have S00218. S00625 is NOT in users.csv provided in view_file (only 9 rows shown).
    # If S00625 is missing, Task insertion will fail due to ForeignKey.
    # We will create dummy users for any missing assignee.
    pass # implementing inside import_tasks

def import_tasks():
    print("\nImporting Tasks...")
    with open('tasks.csv', mode='r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        
        for row in reader:
            task_id = row.get("id")
            assigned_to = row.get("task_assigned_to")
            
            if assigned_to == "NULL" or not assigned_to:
                # If required in model, we skip or handle. Model says task_assigned_to is mapped to User.emp_id
                # If NULL in CSV, maybe skip task or set to valid user?
                # For now skipping tasks without assignee if model enforces it.
                # Assuming model might allow NULL if nullable=True, but let's check code...
                # main.py: "Task must be assigned to a user"
                # So we skip if NULL.
                print(f"Skipping Task {task_id} - No Assignee")
                continue

            # Check if User exists
            user_exists = db.query(UserModel).filter(UserModel.emp_id == assigned_to).first()
            if not user_exists:
                print(f"Creating Missing User {assigned_to} for Task {task_id}")
                try:
                    dummy_user = UserModel(
                        emp_id=assigned_to,
                        emp_name=f"Unknown User {assigned_to}",
                        emp_email=f"{assigned_to}@example.com",
                        emp_designation="Unknown",
                        emp_hierarchy="EMPLOYEE",
                        emp_department="Unknown"
                    )
                    db.add(dummy_user)
                    db.commit()
                except Exception as e:
                    print(f"Fixed fail: {e}")
                    db.rollback()

            existing = db.query(TaskModel).filter(TaskModel.id == task_id).first()
            if not existing:
                try:
                    # Parse dates
                    created = row.get("task_created_at")
                    updated = row.get("task_updated_at")
                    completed = row.get("completed_at")
                    due = row.get("task_due_date")
                    assigned_date = row.get("task_assigned_date")

                    def parse_dt(dt_str):
                        if not dt_str or dt_str == "NULL": return None
                        # Python 3.10 fromisoformat handles most ISOs, but Z might need replacing if old python
                        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

                    new_task = TaskModel(
                        id=task_id,
                        task_name=row.get("task_name"),
                        task_description=row.get("task_description"),
                        task_status=row.get("task_status"),
                        task_assigned_to=assigned_to,
                        task_assigned_by=row.get("task_assigned_by") if row.get("task_assigned_by") != "NULL" else None,
                        task_priority=row.get("task_priority"),
                        task_duration=row.get("task_duration"),
                        time_spent=row.get("time_spent"),
                        task_created_at=parse_dt(created),
                        task_updated_at=parse_dt(updated),
                        completed_at=parse_dt(completed),
                        task_due_date=parse_dt(due),
                        task_assigned_date=parse_dt(assigned_date)
                    )
                    db.add(new_task)
                    db.commit()
                    print(f"Added Task: {task_id}")
                except Exception as e:
                    print(f"Error adding task {task_id}: {e}")
                    db.rollback()
            else:
                 print(f"Task {task_id} already exists.")

if __name__ == "__main__":
    import_users()
    import_foundation()
    import_tasks()
    db.close()
