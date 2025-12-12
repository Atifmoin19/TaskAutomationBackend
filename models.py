from typing import Optional
import os
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from pydantic import BaseModel

load_dotenv()

Base = declarative_base()

# SQLAlchemy ORM models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    emp_name = Column(String(255), nullable=False)
    emp_id = Column(String(64), unique=True, nullable=False, index=True)
    emp_email = Column(String(255), unique=True, nullable=False, index=True)
    emp_phone = Column(String(32), nullable=True)
    emp_designation = Column(String(128), nullable=True)
    emp_department = Column(String(128), nullable=True)
    emp_hierarchy = Column(String(128), nullable=True)
    manager_id = Column(String(64), nullable=True) # emp_id of the manager

class Foundation(Base):
    __tablename__ = "foundation"

    id = Column(Integer, primary_key=True, index=True)
    emp_id = Column(String(64), unique=True, nullable=False, index=True) # One-to-one with User.emp_id
    password = Column(String(255), nullable=False)
    token = Column(String(255), nullable=True)

class Task(Base):
    __tablename__ = "tasks"


    id = Column(String(64), primary_key=True, index=True)
    task_name = Column(String(255), nullable=False)
    task_description = Column(String(1024), nullable=True)
    task_status = Column(String(64), nullable=True)
    task_assigned_to = Column(String(64), nullable=True)
    task_assigned_by = Column(String(64), nullable=True)
    task_assigned_date = Column(String(32), nullable=True)
    task_due_date = Column(String(32), nullable=True)
    task_priority = Column(String(32), nullable=True)
    task_tags = Column(String(255), nullable=True)
    task_notes = Column(String(1024), nullable=True)
    task_created_at = Column(String(32), nullable=True)
    task_updated_at = Column(String(32), nullable=True)
    task_duration = Column(String(32), nullable=True)

# Database engine/session setup
# Prefer DATABASE_URL env var. Example: postgresql+psycopg://user:pass@localhost:5432/automation
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to SQLite for dev if Postgres URL is not configured
    DATABASE_URL = "sqlite:///./automation_dev.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Pydantic schemas
class UserCreate(BaseModel):
    emp_name: str
    emp_id: str
    emp_email: str
    emp_phone: Optional[str] = None
    emp_designation: Optional[str] = None
    emp_department: Optional[str] = None
    emp_hierarchy: Optional[str] = None
    manager_id: Optional[str] = None
    password: Optional[str] = None # Optional for now, will default in main logic if missing

class UserRead(BaseModel):
    id: int
    emp_name: str
    emp_id: str
    emp_email: str
    emp_phone: Optional[str] = None
    emp_designation: Optional[str] = None
    emp_department: Optional[str] = None
    emp_hierarchy: Optional[str] = None
    manager_id: Optional[str] = None

    class Config:
        from_attributes = True  # Pydantic v2 ORM mode

class TaskCreate(BaseModel):
    id: Optional[str] = None
    task_name: str
    task_description: Optional[str] = None
    task_status: Optional[str] = None
    task_assigned_to: Optional[str] = None
    task_assigned_by: Optional[str] = None
    task_assigned_date: Optional[str] = None
    task_due_date: Optional[str] = None
    task_priority: Optional[str] = None
    task_tags: Optional[str] = None
    task_notes: Optional[str] = None
    task_created_at: Optional[str] = None
    task_updated_at: Optional[str] = None
    task_duration: Optional[str] = None

class TaskRead(BaseModel):
    id: str
    task_name: str
    task_description: Optional[str] = None
    task_status: Optional[str] = None
    task_assigned_to: Optional[str] = None
    task_assigned_by: Optional[str] = None
    task_assigned_date: Optional[str] = None
    task_due_date: Optional[str] = None
    task_priority: Optional[str] = None
    task_tags: Optional[str] = None
    task_notes: Optional[str] = None
    task_created_at: Optional[str] = None
    task_updated_at: Optional[str] = None
    task_duration: Optional[str] = None

    class Config:
        from_attributes = True  # Pydantic v2 ORM mode

class UserUpdate(BaseModel):
    emp_name: Optional[str] = None
    emp_id: Optional[str] = None
    emp_email: Optional[str] = None
    emp_phone: Optional[str] = None
    emp_designation: Optional[str] = None
    emp_department: Optional[str] = None
    emp_hierarchy: Optional[str] = None
    manager_id: Optional[str] = None

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
