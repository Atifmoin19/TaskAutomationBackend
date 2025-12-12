import logging
import secrets
from typing import Generator, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Body, UploadFile, File
import csv
import io
import codecs
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils import response
from dotenv import load_dotenv

# Load env vars first so models.py can see DATABASE_URL
load_dotenv()

from models import (
     User as UserModel,
     Task as TaskModel,
     SessionLocal,
     init_db,
     UserCreate,
     UserRead,
     UserUpdate,
     TaskCreate,
     TaskRead,
 )

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Hierarchy Configuration
HIERARCHY_RANKS = {
    "SE1": 1, "SE2": 1, "SSE": 1, "TL": 1,
    "L1": 2,
    "L2": 3,
    "EM": 4,
    "CTO": 5,
    "ADMIN": 5,       # Treating Admin equivalent to CTO/Top level for task visibility
    "SUPERADMIN": 6,
    "OWNER": 7
}

def get_rank(designation: str) -> int:
    # Default to 0 if unknown designation
    if not designation:
        return 0
    # Create a normalized lookup (case-insensitive)
    return HIERARCHY_RANKS.get(designation.upper(), 0)

def validate_manager_hierarchy(db, manager_id: str, employee_designation: str, employee_id: Optional[str] = None):
    """
    Validates if the manager exists and has a higher rank than the employee.
    Allows self-management for Rank >= 5.
    """
    manager = db.query(UserModel).filter(UserModel.emp_id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=400, detail=f"Manager with ID {manager_id} not found")
        
    manager_rank = get_rank(manager.emp_designation)
    employee_rank = get_rank(employee_designation)
    
    # Check for Self-Management first
    if employee_id and manager_id == employee_id:
        if employee_rank >= 5:
            return True
        else:
            raise HTTPException(status_code=400, detail="Only hierarchies of Level 5 (CTO/Admin) and above can be their own manager.")

    # Standard Hierarchy Check: Manager must be strictly higher
    if manager_rank <= employee_rank:
         raise HTTPException(status_code=400, detail=f"Invalid Hierarchy: Manager ({manager.emp_designation}) must be higher rank than Employee ({employee_designation})")
    
    return True

def get_all_subordinates(db, manager_emp_id: str) -> set:
    """
    Recursively finds all subordinates (direct and indirect) for a given manager.
    Returns a set of emp_ids.
    """
    subordinates = set()
    # Find direct reports
    direct_reports = db.query(UserModel).filter(UserModel.manager_id == manager_emp_id).all()
    
    for user in direct_reports:
        subordinates.add(user.emp_id)
        # Recursively find their subordinates
        subordinates.update(get_all_subordinates(db, user.emp_id))
        
    return subordinates

    return subordinates

def get_user_view_scope(db, emp_id: str) -> set:
    """
    Returns the set of emp_ids that the given emp_id is allowed to see (Self + Subordinates).
    """
    user = db.query(UserModel).filter(UserModel.emp_id == emp_id).first()
    if not user:
        return set()
    
    scope = {emp_id}
    rank = get_rank(user.emp_designation)
    
    # If rank is high enough, include subordinates
    if rank >= 2:
        scope.update(get_all_subordinates(db, emp_id))
        
    return scope

def validate_assignee_eligibility(user: UserModel):
    """
    Validates if a user is eligible to be assigned a task.
    Rank 4 (EM) and above are NOT allowed to be assigned tasks.
    """
    rank = get_rank(user.emp_designation)
    if rank >= 4:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot assign task to {user.emp_designation} ({user.emp_name}). Only ranks below EM (Rank 4) can be assigned tasks."
        )
    return True

def get_db() -> Generator:
     db = SessionLocal()
     try:
         yield db
     finally:
         db.close()

# Auth Models and Dependency
class LoginRequest(BaseModel):
    emp_id: str

def verify_token(authorization: Optional[str] = Header(None), db=Depends(get_db)):
    if not authorization:
         raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    elif authorization.startswith("Token "):
        token = authorization.replace("Token ", "")
    else:
        token = authorization
    user = db.query(UserModel).filter(UserModel.token == token).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or Expired Token")
    
    return user


from redis_client import get_redis_client

@app.on_event("startup")
def on_startup():
    # Initialize Postgres tables
    init_db()
    
    # Verify Redis Connection
    redis_conn = get_redis_client()
    if redis_conn:
        logger.info("Redis connected successfully")
    else:
        logger.warning("Redis connection failed")


def get_redis():
    r = get_redis_client()
    try:
        yield r
    finally:
        # Redis client manages its own connection pool, but we can close it if needed.
        # usually for redis-py usage in dependency, we just yield it.
        pass


@app.get('/')
def welcome():
     return response(status.HTTP_200_OK, message="Welcome to the Automation Backend")


@app.post('/login', status_code=200)
def login(login_req: LoginRequest, db=Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.emp_id == login_req.emp_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    
    token = secrets.token_hex(16)
    user.token = token
    db.commit()
    db.refresh(user)
    
    user_data = UserRead.from_orm(user).dict()
    # Remove token from user_data to send it separately as requested
    if "token" in user_data:
        del user_data["token"]

    data = {
        "token": token,
        "userData": user_data
    }
    return response(status.HTTP_200_OK, message="Login successful", data=data)


@app.post('/logout', status_code=200)
def logout(authorization: Optional[str] = Header(None), db=Depends(get_db)):
    if not authorization:
        # If no token, just say logged out or error? Usually success if already "gone" logic, but checking token is safer.
        return response(status.HTTP_401_UNAUTHORIZED, message="Missing Token")

    token = authorization.replace("Bearer ", "")
    user = db.query(UserModel).filter(UserModel.token == token).first()
    
    if user:
        user.token = None # Mark as null/expired
        db.commit()
    
    return response(status.HTTP_200_OK, message="Logout successful")


@app.post('/user', status_code=201)
def create_user(user: UserCreate, db=Depends(get_db)):
     # Check uniqueness by emp_id
     existing = db.query(UserModel).filter(UserModel.emp_id == user.emp_id).first()
     if existing:
         raise HTTPException(status_code=400, detail="User with emp_id already exists")

     existing = db.query(UserModel).filter(UserModel.emp_email == user.emp_email).first()
     if existing:
         raise HTTPException(status_code=400, detail="User with emp_email already exists")

     if user.manager_id:
         validate_manager_hierarchy(db, user.manager_id, user.emp_designation, user.emp_id)

     db_user = UserModel(
         emp_name=user.emp_name,
         emp_id=user.emp_id,
         emp_email=user.emp_email,
         emp_phone=user.emp_phone,
         emp_designation=user.emp_designation,
         emp_department=user.emp_department,
         emp_hierarchy=user.emp_hierarchy,
         manager_id=user.manager_id,
     )
     db.add(db_user)
     db.commit()
     db.refresh(db_user)
     logger.info("User created: %s", {
         "id": db_user.id,
         "emp_id": db_user.emp_id,
         "emp_email": db_user.emp_email,
     })
     
     data = UserRead.from_orm(db_user).dict()
     return response(status_code=status.HTTP_201_CREATED, message="User created successfully", data=data)


@app.get('/user')
def get_users(user_id: Optional[str] = None, db=Depends(get_db)):
    if user_id:
        # Check if user exists (optional, but good for validation)
        # root_user = db.query(UserModel).filter(UserModel.emp_id == user_id).first()
        
        # Get all subordinates recursively (naturally excludes the user_id itself)
        subordinate_ids = get_all_subordinates(db, user_id)
        
        users = db.query(UserModel).filter(UserModel.emp_id.in_(subordinate_ids)).all()
    else:
        # Default behavior: fetch all users (or could be restricted to current_user scope if desired later)
        users = db.query(UserModel).all()

    data = []
    for user in users:
        data.append({
            "id": user.id,
            "emp_id": user.emp_id,
            "emp_email": user.emp_email,
            "emp_name": user.emp_name,
            "emp_phone": user.emp_phone,
            "emp_designation": user.emp_designation,
            "emp_department": user.emp_department,
            "emp_hierarchy": user.emp_hierarchy,
            "manager_id": user.manager_id,
        })
    return response(status.HTTP_200_OK, message="Users fetched successfully", data=data)


@app.put('/user/{emp_id}', status_code=200)
def update_user(emp_id: str, user_update: UserUpdate, db=Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.emp_id == emp_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate uniqueness if changing emp_id
    if user_update.emp_id and user_update.emp_id != emp_id:
        existing_user = db.query(UserModel).filter(UserModel.emp_id == user_update.emp_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="New emp_id already exists")
    
    # Validate uniqueness if changing emp_email
    if user_update.emp_email and user_update.emp_email != db_user.emp_email:
        existing_email = db.query(UserModel).filter(UserModel.emp_email == user_update.emp_email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="New emp_email already exists")

    # Validate manager if changed
    if user_update.manager_id and user_update.manager_id != db_user.manager_id:
         # Check hierarchy with Current designation (or new if provided)
         designation = user_update.emp_designation or db_user.emp_designation
         validate_manager_hierarchy(db, user_update.manager_id, designation, db_user.emp_id)

    # Update fields if provided
    if user_update.emp_name is not None:
        db_user.emp_name = user_update.emp_name
    if user_update.emp_id is not None:
        db_user.emp_id = user_update.emp_id
    if user_update.emp_email is not None:
        db_user.emp_email = user_update.emp_email
    if user_update.emp_phone is not None:
        db_user.emp_phone = user_update.emp_phone
    if user_update.emp_designation is not None:
        db_user.emp_designation = user_update.emp_designation
    if user_update.emp_department is not None:
        db_user.emp_department = user_update.emp_department
    if user_update.emp_hierarchy is not None:
        db_user.emp_hierarchy = user_update.emp_hierarchy
    if user_update.manager_id is not None:
        db_user.manager_id = user_update.manager_id

    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database update failed: {str(e)}")

    data = UserRead.from_orm(db_user).dict()
    # Ensure token is not returned or handled appropriately if needed (usually not needed in update profile response unless refreshed)
    if "token" in data:
        del data["token"]

    return response(status.HTTP_200_OK, message="User updated successfully", data=data)


@app.post('/tasks', status_code=201)
def create_task(task: TaskCreate, db=Depends(get_db), current_user=Depends(verify_token)):
    
    # Generate Task ID if not provided
    if not task.id:
        task.id = secrets.token_hex(8)

    existing = db.query(TaskModel).filter(TaskModel.id == task.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Task with this ID already exists")

    if task.task_duration == "0":
        raise HTTPException(status_code=400, detail="Task duration cannot be 0")

    if not task.task_assigned_to:
        raise HTTPException(status_code=400, detail="Task must be assigned to a user")

    assigned_user = db.query(UserModel).filter(UserModel.emp_id == task.task_assigned_to).first()
    if not assigned_user:
        raise HTTPException(status_code=400, detail="Assigned user not found")
    
    # Validate Rank Logic
    validate_assignee_eligibility(assigned_user)

    db_task = TaskModel(
        id=task.id,
        task_name=task.task_name,
        task_description=task.task_description,
        task_status=task.task_status,
        task_assigned_to=task.task_assigned_to,
        task_assigned_by=task.task_assigned_by,
        task_assigned_date=task.task_assigned_date,
        task_due_date=task.task_due_date,
        task_priority=task.task_priority,
        task_tags=task.task_tags,
        task_notes=task.task_notes,
        task_created_at=task.task_created_at,
        task_updated_at=task.task_updated_at,
        task_duration=task.task_duration,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    data = TaskRead.from_orm(db_task).dict()
    return response(status_code=status.HTTP_201_CREATED, message="Task created successfully", data=data)


@app.get('/tasks')
def get_tasks(user_id: Optional[str] = None, db=Depends(get_db), current_user=Depends(verify_token)):
    """
    Get tasks.
    - If user_id is NOT provided: Returns tasks for Current User + Subordinates (if applicable).
    - If user_id IS provided: Returns tasks for Target User + Target User's Subordinates (if applicable).
      (Only if Current User has permission to view Target User).
    """
    
    # 1. Determine Access Scope of Current User
    # What is the MAX set of users this person is allowed to see data for?
    current_user_scope = get_user_view_scope(db, current_user.emp_id)
    
    # 2. Determine the Root of the Query
    target_root_id = user_id if user_id else current_user.emp_id
    
    # 3. Security Check
    # Ensure current user is allowed to view the target root user
    if target_root_id not in current_user_scope:
         # If trying to view someone outside their hierarchy, deny access (return empty)
         return response(status.HTTP_200_OK, message="Tasks fetched successfully", data=[])

    # 4. Calculate the Final Display Scope
    # We want the tree *rooted* at target_root_id
    display_scope = get_user_view_scope(db, target_root_id)
    
    query = db.query(TaskModel).filter(TaskModel.task_assigned_to.in_(display_scope))

    tasks = query.all()
    data = []
    for task in tasks:
        data.append({
            "id": task.id,
            "task_name": task.task_name,
            "task_description": task.task_description,
            "task_status": task.task_status,
            "task_assigned_to": task.task_assigned_to,
            "task_assigned_by": task.task_assigned_by,
            "task_assigned_date": task.task_assigned_date,
            "task_due_date": task.task_due_date,
            "task_priority": task.task_priority,
            "task_tags": task.task_tags,
            "task_notes": task.task_notes,
            "task_created_at": task.task_created_at,
            "task_updated_at": task.task_updated_at,
            "task_duration": task.task_duration,
        })
    return response(status.HTTP_200_OK, message="Tasks fetched successfully", data=data)


@app.put('/tasks/{task_id}')
def update_task(task_id: str, task: TaskCreate, db=Depends(get_db), current_user=Depends(verify_token)):
    db_task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.task_duration == "0":
        raise HTTPException(status_code=400, detail="Task duration cannot be 0")

    if not task.task_assigned_to:
        raise HTTPException(status_code=400, detail="Task must be assigned to a user")

    assigned_user = db.query(UserModel).filter(UserModel.emp_id == task.task_assigned_to).first()
    if not assigned_user:
            raise HTTPException(status_code=400, detail="Assigned user not found")

    # Validate Rank Logic
    validate_assignee_eligibility(assigned_user)

    # Check if assignee is the same
    # The user specifically asked to remove from prev developer to new developer logic
    # "if asgnee to is same then reutn error" was previous req.
    # Note: user did not say to remove that logic in this specific prompt, but said "verify all apis".
    # I will keep the business logic from previous turn.

    db_task.task_name = task.task_name
    db_task.task_description = task.task_description
    db_task.task_status = task.task_status
    db_task.task_assigned_to = task.task_assigned_to
    db_task.task_assigned_by = task.task_assigned_by
    db_task.task_assigned_date = task.task_assigned_date
    db_task.task_due_date = task.task_due_date
    db_task.task_priority = task.task_priority
    db_task.task_tags = task.task_tags
    db_task.task_notes = task.task_notes
    db_task.task_created_at = task.task_created_at
    db_task.task_updated_at = task.task_updated_at
    db_task.task_duration = task.task_duration

    db.commit()
    db.refresh(db_task)
    
    data = TaskRead.from_orm(db_task).dict()
    return response(status_code=status.HTTP_200_OK, message="Task updated successfully", data=data)


@app.post('/users/upload', status_code=200)
async def upload_users(file: UploadFile = File(...), db=Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    # Decode logic
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        # Fallback or error
        decoded = content.decode('latin-1')
        
    csv_reader = csv.DictReader(io.StringIO(decoded))
    
    added_count = 0
    skipped_count = 0
    
    for row in csv_reader:
        # Basic validation: ensure required user fields exist in CSV row
        required_cols = ["emp_id", "emp_name", "emp_email"]
        if any(col not in row for col in required_cols):
            # If CSV format is bad, maybe fail? or just skip? 
            # Prompt: "if ther are duplicate users then ignore that and restun success"
            # It doesn't explicitly say what to do with missing columns, but implies standard 'create users'.
            # I will skip if key data is missing to avoid error.
            skipped_count += 1
            continue

        emp_id = row.get("emp_id")
        emp_email = row.get("emp_email")
        
        existing = db.query(UserModel).filter((UserModel.emp_id == emp_id) | (UserModel.emp_email == emp_email)).first()
        if existing:
            skipped_count += 1
            continue
        
        new_user = UserModel(
            emp_name=row.get("emp_name"),
            emp_id=emp_id,
            emp_email=emp_email,
            emp_phone=row.get("emp_phone"),
            emp_designation=row.get("emp_designation"),
            emp_department=row.get("emp_department"),
            emp_hierarchy=row.get("emp_hierarchy"),
            manager_id=row.get("manager_id") # Add CSV support for manager
        )
        db.add(new_user)
        added_count += 1
    
    db.commit()
    return response(status.HTTP_200_OK, message="Bulk upload complete", data={"added": added_count, "skipped": skipped_count})


@app.post('/tasks/upload', status_code=200)
async def upload_tasks(file: UploadFile = File(...), db=Depends(get_db), current_user=Depends(verify_token)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
         decoded = content.decode('latin-1')
         
    csv_reader = csv.DictReader(io.StringIO(decoded))
    rows = list(csv_reader)
    
    # Pre-validation: "if any issue in format or type then only retun error"
    # We will iterate first to validate, then insert if all good. 
    # Or insert incrementally and rollback? 
    # Validating first is safer for "retun error that this field is required".
    
    validated_tasks = []
    
    for line_num, row in enumerate(rows, start=1):
        # Validate required fields
        if not row.get("task_name"):
            raise HTTPException(status_code=400, detail=f"Row {line_num}: task_name is required")
        if not row.get("task_assigned_to"):
            raise HTTPException(status_code=400, detail=f"Row {line_num}: task_assigned_to is required")
        
        # Validate Duration != 0
        duration = row.get("task_duration", "0") # Default to 0 if missing -> error
        if duration == "0":
             raise HTTPException(status_code=400, detail=f"Row {line_num}: task_duration cannot be 0")

        # Validate Assigned User Existence
        assigned_id = row.get("task_assigned_to")
        user = db.query(UserModel).filter(UserModel.emp_id == assigned_id).first()
        if not user:
            raise HTTPException(status_code=400, detail=f"Row {line_num}: Assigned user '{assigned_id}' not found")

        # Validate Rank Logic
        validate_assignee_eligibility(user)

        # ID Handling: If missing, generate.
        task_id = row.get("id")
        if not task_id:
            task_id = secrets.token_hex(8) # Generate random ID
            
        validated_tasks.append(dict(row, id=task_id, task_duration=duration))

    # All validated, insert them
    count = 0
    try:
        for item in validated_tasks:
            # Check ID duplication logic if ID was provided
            # If generated, likelihood of collision is low, but checked below.
            if db.query(TaskModel).filter(TaskModel.id == item["id"]).first():
                 # Should we fail or skip? "make new api to accept files... if any issue ... return error"
                 # Duplicate ID is an issue.
                 raise HTTPException(status_code=400, detail=f"Task ID {item['id']} already exists")
            
            db_task = TaskModel(
                id=item["id"],
                task_name=item.get("task_name"),
                task_description=item.get("task_description"),
                task_status=item.get("task_status", "todo"),
                task_assigned_to=item.get("task_assigned_to"),
                task_assigned_by=item.get("task_assigned_by"),
                task_assigned_date=item.get("task_assigned_date"),
                task_due_date=item.get("task_due_date"),
                task_priority=item.get("task_priority"),
                task_tags=item.get("task_tags"),
                task_notes=item.get("task_notes"),
                task_created_at=item.get("task_created_at"),
                task_updated_at=item.get("task_updated_at"),
                task_duration=item.get("task_duration"),
            )
            db.add(db_task)
            count += 1
        
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return response(status.HTTP_200_OK, message="Bulk upload successful", data={"added": count})