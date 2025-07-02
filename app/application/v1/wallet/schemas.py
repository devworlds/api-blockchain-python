from pydantic import BaseModel
from typing import Optional

#Post /Wallets
class WalletCreationStatusResponse(BaseModel):
    status: str
    detail: Optional[str] = None 