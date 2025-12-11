from dotenv import load_dotenv
load_dotenv()
from models import engine, Base

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("Creating all tables...")
Base.metadata.create_all(bind=engine)
print("Schema reset complete.")
