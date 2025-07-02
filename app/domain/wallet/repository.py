from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.wallet.entity import Wallet

class WalletRepository(ABC):
    @abstractmethod
    async def save_wallet(self, wallet: Wallet) -> None:
        pass

    @abstractmethod
    async def get_wallet_by_address(self, address: str) -> Optional[Wallet]:
        pass

    @abstractmethod
    async def list_wallets(self) -> List[Wallet]:
        pass 
    