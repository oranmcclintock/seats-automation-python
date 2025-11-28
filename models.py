from sqlalchemy import Column, Integer, String, Boolean
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True)
    token = Column(String)
    mobile_key = Column(String)  # The signing key
    webhook_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)