from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# FIX: Create the data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# FIX: Point the database to the data folder
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/seats_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()