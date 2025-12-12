from models import SessionLocal, User, Foundation

def migrate_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Found {len(users)} users.")
        
        migrated_count = 0
        for user in users:
            # Check if foundation exists
            foundation = db.query(Foundation).filter(Foundation.emp_id == user.emp_id).first()
            if not foundation:
                print(f"Creating Foundation entry for {user.emp_id}")
                new_foundation = Foundation(
                    emp_id=user.emp_id,
                    password="123456", # Default password
                    token=None
                )
                db.add(new_foundation)
                migrated_count += 1
            else:
                print(f"Foundation entry already exists for {user.emp_id}")
        
        db.commit()
        print(f"Migration complete. Created {migrated_count} Foundation entries.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_users()
