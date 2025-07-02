from pydantic import BaseModel
from decimal import Decimal

class TransactionDTO(BaseModel):
    asset: str
    address_from: str
    value: Decimal