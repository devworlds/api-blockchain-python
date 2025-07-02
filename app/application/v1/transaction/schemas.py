from pydantic import BaseModel, field_validator
from pydantic.types import T
from app.application.v1.transaction.dto import TransactionDTO
from typing import Optional, Union
from decimal import Decimal
from app.shared.utils.validators import validate_eth_value, eth_to_wei


class TransactionHashResponse(BaseModel):
    is_valid: bool
    transfers: list[TransactionDTO]
    confirmations: int = 0
    is_confirmed: bool = False
    min_confirmations_required: int = 6
    is_destination_our_wallet: bool = False


class TransactionOnChainRequest(BaseModel):
    address_from: str
    address_to: str
    asset: str
    value: Union[str, float, Decimal]
    contract_address: Optional[str] = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, v):
        """Validate ETH value is positive and valid"""
        if not validate_eth_value(v):
            raise ValueError("Value must be a positive valid number in ETH")
        return v

    def get_value_in_wei(self) -> int:
        """Convert value to Wei safely"""
        return eth_to_wei(self.value)


class TransactionOnChainResponse(BaseModel):
    hash: str
    status: str
    effective_fee: float
    created_at: str
    # Confirmation information (updated by background monitor)
    confirmations: Optional[int] = 0
    is_confirmed: Optional[bool] = False
    wait_time: Optional[float] = None
    timeout: Optional[bool] = False
