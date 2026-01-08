from models import SessionLocal, Foundation, User as UserModel

db = SessionLocal()

# 1. Create a User first (Required due to ForeignKey if strict, but Foundation might be loosely coupled in your model. 
# Based on main.py logic, User usually exists first, but let's check models.py dependency.)
# Assuming simple insertion for Foundation as requested:

# Check if entry exists to avoid error
emp_id = "test_manual_01"
existing = db.query(Foundation).filter(Foundation.emp_id == emp_id).first()

if not existing:
    # Create Dummy User to satisfy FK if exists
    user = db.query(UserModel).filter(UserModel.emp_id == emp_id).first()
    if not user:
        new_user = UserModel(
            emp_id=emp_id,
            emp_name="Test Manual User",
            emp_email="test_manual@example.com",
            emp_designation="L1",
            emp_hierarchy="L1",
            emp_department="Engineering"
        )
        db.add(new_user)
        db.commit() # Commit user first
    
    # Create Foundation
    new_foundation = Foundation(
        emp_id=emp_id,
        password="TestPassword@123",
        token=None
    )
    db.add(new_foundation)
    db.commit()
    print(f"Created Foundation entry for {emp_id}")
else:
    print(f"Foundation entry for {emp_id} already exists")

db.close()
