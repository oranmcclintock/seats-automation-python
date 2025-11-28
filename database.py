from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./seats_app.db"

# CRITICAL LINE: This is where 'engine' is defined and must not be misspelled or commented out.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# CRITICAL LINE: This is where 'Base' is defined.
Base = declarative_base()

# CRITICAL FUNCTION: This is where 'get_db' is defined.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()