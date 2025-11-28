from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    alias: str
    token: str
    webhook_url: Optional[str] = None

class UserResponse(UserCreate):
    id: int
    is_active: bool
    mobile_key: Optional[str] = None

    class Config:
        from_attributes = True