from decimal import Decimal

from pydantic import BaseModel


class TransactionDTO(BaseModel):
    asset: str
    address_from: str
    value: Decimal
