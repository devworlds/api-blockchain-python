from datetime import date
from typing import List
from abc import ABC, abstractmethod
from app.domain.wallet.entity import Wallet
import datetime
from sqlalchemy import Null
from app.shared.monitoring.metrics import record_wallet_created

# --- Abstractions ---
class VaultService(ABC):
    @abstractmethod
    def store_private_key(self, key_id: str, private_key: str) -> None:
        pass

    @abstractmethod
    def get_private_key(self, key_id: str) -> str:
        pass

class WalletService(ABC):
    @abstractmethod
    def create_wallet(self) -> dict:
        """Returns the creation status"""
        pass

    @abstractmethod
    def sign_transaction(self, private_key: str, transaction: dict) -> str:
        pass

# --- Use Cases ---
class CreateWalletsUseCase:
    def __init__(self, vault_service: VaultService, wallet_service: WalletService, wallet_repository):
        self.vault_service = vault_service
        self.wallet_service = wallet_service
        self.wallet_repository = wallet_repository

    async def execute(self, n: int) -> list[str]:
        """
        Creates N Ethereum wallets, stores private keys in Vault, and returns status.
        """
        addresses = []
        for i in range(n):
            wallet = self.wallet_service.create_wallet()
            address = wallet['address']
            private_key = wallet['private_key']
            key_id = f"eth_wallet_{address}"
            self.vault_service.store_private_key(key_id, private_key)
            # Save to repository
            await self.wallet_repository.save_wallet(Wallet(
                address=address, 
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
                deleted_at=None
            ))
            addresses.append(address)
        
        # Record metrics for all wallets created in this batch
        record_wallet_created(n)
        return addresses

class SignTransactionWithVaultWalletUseCase:
    def __init__(self, vault_service: VaultService, wallet_service: WalletService):
        self.vault_service = vault_service
        self.wallet_service = wallet_service

    def execute(self, address: str, transaction: dict) -> str:
        """
        Signs a transaction using the private key stored in Vault for the given address.
        Returns the signed transaction (hex or raw).
        """
        key_id = f"eth_wallet_{address}"
        private_key = self.vault_service.get_private_key(key_id)
        signed_tx = self.wallet_service.sign_transaction(private_key, transaction)
        return signed_tx

class GetAllWalletsUseCase:
    def __init__(self, conn):
        self.conn = conn

    async def execute(self):
        query = "SELECT address FROM wallets WHERE deleted_at IS NULL;"
        rows = await self.conn.fetch(query)
        return [dict(row) for row in rows]

# --- Implementations for VaultService and WalletService should be provided elsewhere and injected here. ---