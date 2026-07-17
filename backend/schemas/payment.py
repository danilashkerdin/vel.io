from pydantic import BaseModel, Field
from typing import Optional


class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    ton_wallet: Optional[str] = None
