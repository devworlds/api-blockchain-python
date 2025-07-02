from typing import Optional

from pydantic import BaseModel


# Post /Wallets
class WalletCreationStatusResponse(BaseModel):
    status: str
    detail: Optional[str] = None
