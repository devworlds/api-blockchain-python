from typing import  Optional
import datetime
from pydantic import BaseModel, Field

class Wallet(BaseModel):
    address: str = Field(..., description="The Ethereum address of the wallet")
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: Optional[datetime.datetime] = None
