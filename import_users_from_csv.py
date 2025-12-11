import csv
import sys
import os

# Add current directory to path so we can import models
sys.path.append(os.getcwd())

from models import SessionLocal, User

def import_users(csv_path: str):
    db = SessionLocal()
    try:
        if not os.path.exists(csv_path):
            print(f"File {csv_path} not found.")
            return

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # Check validation/existence
                emp_id = row.get("emp_id")
                emp_email = row.get("emp_email")
                
                existing = db.query(User).filter((User.emp_id == emp_id) | (User.emp_email == emp_email)).first()
                if existing:
                    print(f"Skipping {row.get('emp_name')} ({emp_id}) - Already exists.")
                    continue

                user = User(
                    emp_name=row.get("emp_name"),
                    emp_id=emp_id,
                    emp_email=emp_email,
                    emp_phone=row.get("emp_phone"),
                    emp_designation=row.get("emp_designation"),
                    emp_department=row.get("emp_department"),
                    emp_hierarchy=row.get("emp_hierarchy")
                )
                db.add(user)
                count += 1
            
            db.commit()
            print(f"Successfully added {count} users.")
            
    except Exception as e:
        print(f"Error importing users: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_users("users.csv")
