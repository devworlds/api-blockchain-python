import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class Transaction(BaseModel):
    hash: str
    asset: str
    address_from: str
    address_to: str
    value: int
    is_token: bool
    type: str
    status: str
    effective_fee: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: Optional[datetime.datetime] = None
    contract_address: Optional[str] = None
