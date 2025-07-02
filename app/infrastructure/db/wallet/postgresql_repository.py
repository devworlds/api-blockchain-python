import hvac
from eth_account import Account
from eth_account.messages import encode_defunct
from typing import Dict
from app.application.v1.wallet.usecase import VaultService, WalletService
import asyncpg
from app.domain.wallet.repository import Wallet, WalletRepository

# Monitoring imports
from app.shared.monitoring.logging import (
    get_logger,
    LoggerMixin,
    log_vault_operation,
    log_database_operation,
)
from app.shared.monitoring.metrics import (
    record_vault_operation,
    record_database_operation,
    record_wallet_created,
    record_wallet_operation,
    MetricsContext,
)
import time


class HashiCorpVaultService(VaultService, LoggerMixin):
    def __init__(self, url: str, token: str, secret_path: str = "eth_wallets"):
        self.client = hvac.Client(url=url, token=token)
        self.secret_path = secret_path

        # Test Vault connection
        if self.client.is_authenticated():
            self.logger.info(f"Vault client authenticated successfully - URL: {url}")
        else:
            self.logger.error(f"Vault authentication failed - URL: {url}")

    def store_private_key(self, key_id: str, private_key: str) -> None:
        start_time = time.time()

        self.logger.info(f"Storing private key in Vault - Key ID: {key_id}")

        try:
            with MetricsContext("store_private_key", "vault"):
                secret_data = {"private_key": private_key}
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f"{self.secret_path}/{key_id}", secret=secret_data
                )

            duration = time.time() - start_time
            self.logger.info(
                f"Private key stored successfully - Key ID: {key_id}, Duration: {duration:.3f}s"
            )
            record_vault_operation("store_private_key", "success", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to store private key - Key ID: {key_id}, Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_vault_operation("store_private_key", "error", duration)
            raise

    def get_private_key(self, key_id: str) -> str:
        start_time = time.time()

        self.logger.info(f"Retrieving private key from Vault - Key ID: {key_id}")

        try:
            with MetricsContext("get_private_key", "vault"):
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=f"{self.secret_path}/{key_id}"
                )
                private_key = response["data"]["data"]["private_key"]

            duration = time.time() - start_time
            self.logger.info(
                f"Private key retrieved successfully - Key ID: {key_id}, Duration: {duration:.3f}s"
            )
            record_vault_operation("get_private_key", "success", duration)

            return private_key

        except Exception as e:
            duration = time.time() - start_time
            error_message = str(e)

            # Check if it's a path not found error (key doesn't exist)
            if "InvalidPath" in error_message or "404" in error_message:
                self.logger.error(
                    f"Private key not found in Vault - Key ID: {key_id}. The wallet may need to be recreated. Error: {error_message}, Duration: {duration:.3f}s"
                )
                record_vault_operation("get_private_key", "not_found", duration)
                raise ValueError(
                    f"Private key not found in Vault for wallet {key_id.replace('eth_wallet_', '')}. This wallet may need to be recreated."
                )
            else:
                self.logger.error(
                    f"Failed to retrieve private key - Key ID: {key_id}, Error: {error_message}, Duration: {duration:.3f}s"
                )
                record_vault_operation("get_private_key", "error", duration)
                raise


class EthereumWalletService(WalletService, LoggerMixin):
    def create_wallet(self) -> Dict[str, str]:
        """Generate a new Ethereum wallet and return address and private key."""
        start_time = time.time()

        self.logger.info("Creating new Ethereum wallet")

        try:
            with MetricsContext("create_wallet", "wallet"):
                acct = Account.create()
                wallet_data = {"address": acct.address, "private_key": acct.key.hex()}

            duration = time.time() - start_time
            self.logger.info(
                f"Ethereum wallet created successfully - Address: {wallet_data['address']}, Duration: {duration:.3f}s"
            )
            # Note: record_wallet_created() moved to usecase to handle batch count
            record_wallet_operation("create_wallet", "success")

            return wallet_data

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to create Ethereum wallet - Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_wallet_operation("create_wallet", "error")
            raise

    def sign_transaction(self, private_key: str, transaction: dict) -> str:
        """Sign a transaction dict using the provided private key."""
        start_time = time.time()
        try:
            with MetricsContext("sign_transaction", "wallet"):
                acct = Account.from_key(private_key)
                signed = acct.sign_transaction(transaction)
                raw_tx = signed.raw_transaction
                signed_tx = raw_tx.hex()
            duration = time.time() - start_time
            self.logger.info(
                f"Transaction signed successfully - Signer: {acct.address}, Duration: {duration:.3f}s"
            )
            record_wallet_operation("sign_transaction", "success")
            return signed_tx
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to sign transaction - Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_wallet_operation("sign_transaction", "error")
            raise


class PostgreSQLWalletRepository(WalletRepository, LoggerMixin):
    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str):
        pool = await asyncpg.create_pool(dsn=dsn)
        return cls(pool)

    async def save_wallet(self, wallet: Wallet) -> None:
        start_time = time.time()

        self.logger.info(f"Saving wallet to database - Address: {wallet.address}")

        try:
            with MetricsContext("save_wallet", "database"):
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO wallets(address, created_at, updated_at, deleted_at) VALUES($1, $2, $3, $4) ON CONFLICT (address) DO NOTHING",
                        wallet.address,
                        wallet.created_at,
                        wallet.updated_at,
                        wallet.deleted_at,
                    )

            duration = time.time() - start_time
            self.logger.info(
                f"Wallet saved successfully - Address: {wallet.address}, Duration: {duration:.3f}s"
            )
            record_database_operation("save_wallet", "wallets", "success", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to save wallet - Address: {wallet.address}, Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_database_operation("save_wallet", "wallets", "error", duration)
            raise

    async def get_wallet_by_address(self, address: str) -> Wallet | None:
        start_time = time.time()

        self.logger.info(f"Fetching wallet by address - Address: {address}")

        try:
            with MetricsContext("get_wallet_by_address", "database"):
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT address, created_at, updated_at, deleted_at FROM wallets WHERE LOWER(address) = LOWER($1)",
                        address,
                    )

                    wallet = None
                    if row:
                        wallet = Wallet(
                            address=row["address"],
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                            deleted_at=row["deleted_at"],
                        )

            duration = time.time() - start_time
            found = wallet is not None
            self.logger.info(
                f"Wallet fetch completed - Address: {address}, Found: {found}, Duration: {duration:.3f}s"
            )
            record_database_operation(
                "get_wallet_by_address", "wallets", "success", duration
            )

            return wallet

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to fetch wallet - Address: {address}, Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_database_operation(
                "get_wallet_by_address", "wallets", "error", duration
            )
            raise

    async def list_wallets(self) -> list[Wallet]:
        start_time = time.time()

        self.logger.info("Listing all wallets")

        try:
            with MetricsContext("list_wallets", "database"):
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT address, created_at, updated_at, deleted_at FROM wallets"
                    )
                    wallets = [
                        Wallet(
                            address=row["address"],
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                            deleted_at=row["deleted_at"],
                        )
                        for row in rows
                    ]

            duration = time.time() - start_time
            count = len(wallets)
            self.logger.info(
                f"Wallets listed successfully - Count: {count}, Duration: {duration:.3f}s"
            )
            record_database_operation("list_wallets", "wallets", "success", duration)

            return wallets

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Failed to list wallets - Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_database_operation("list_wallets", "wallets", "error", duration)
            raise
