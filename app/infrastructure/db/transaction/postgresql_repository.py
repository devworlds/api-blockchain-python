import asyncpg
import datetime
from app.domain.transaction.entity import Transaction as TransactionEntity
from app.infrastructure.db.transaction.model import Transaction as TransactionModel

class PostgreSQLTransactionRepository:
    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str):
        pool = await asyncpg.create_pool(dsn=dsn)
        return cls(pool)

    async def save_transaction(self, tx: TransactionEntity) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO transactions(hash, asset, address_from, address_to, value, is_token, type, status, effective_fee, created_at, updated_at, deleted_at) '
                'VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) '
                'ON CONFLICT (hash) DO NOTHING',
                tx.hash, tx.asset, tx.address_from, tx.address_to, tx.value, tx.is_token, tx.type, tx.status, tx.effective_fee, tx.created_at, tx.updated_at, tx.deleted_at
            )

    async def update_transaction_status(self, tx_hash: str, new_status: str) -> bool:
        """
        Update transaction status
        
        Args:
            tx_hash: Transaction hash
            new_status: New status (pending, confirmed, failed, etc.)
            
        Returns:
            bool: True if transaction was updated, False if not found
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                'UPDATE transactions SET status = $1, updated_at = $2 WHERE hash = $3',
                new_status, datetime.datetime.now(), tx_hash
            )
            # result retorna algo como "UPDATE 1" se uma linha foi afetada
            return result.split()[-1] == '1'

    async def get_transaction_by_hash(self, hash: str) -> TransactionEntity | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT hash, asset, address_from, address_to, value, is_token, type, status, effective_fee, created_at, updated_at, deleted_at FROM transactions WHERE hash = $1', hash
            )
            if row:
                return TransactionEntity(
                    hash=row['hash'],
                    asset=row['asset'],
                    address_from=row['address_from'],
                    address_to=row['address_to'],
                    value=row['value'],
                    is_token=row['is_token'],
                    type=row['type'],
                    status=row['status'],
                    effective_fee=row['effective_fee'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    deleted_at=row['deleted_at']
                )
            return None

    async def list_transactions(self, limit: int = 100, offset: int = 0) -> list[TransactionEntity]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT hash, asset, address_from, address_to, value, is_token, type, status, effective_fee, created_at, updated_at, deleted_at FROM transactions ORDER BY created_at DESC LIMIT $1 OFFSET $2',
                limit, offset
            )
            return [
                TransactionEntity(
                    hash=row['hash'],
                    asset=row['asset'],
                    address_from=row['address_from'],
                    address_to=row['address_to'],
                    value=row['value'],
                    is_token=row['is_token'],
                    type=row['type'],
                    status=row['status'],
                    effective_fee=row['effective_fee'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    deleted_at=row['deleted_at']
                ) for row in rows
            ]

    async def get_pending_transactions(self, max_age_hours: int = 24) -> list[TransactionEntity]:
        """
        Get pending transactions that need monitoring
        
        Args:
            max_age_hours: Maximum age in hours for transactions to check
            
        Returns:
            List of pending transactions
        """
        async with self._pool.acquire() as conn:
            # Get transactions with pending or confirming status created in the last max_age_hours
            rows = await conn.fetch(
                '''SELECT hash, asset, address_from, address_to, value, is_token, type, status, 
                          effective_fee, created_at, updated_at, deleted_at 
                   FROM transactions 
                   WHERE status IN ('pending', 'confirming') 
                   AND created_at > NOW() - INTERVAL '1 hour' * $1
                   ORDER BY created_at ASC''',
                max_age_hours
            )
            return [
                TransactionEntity(
                    hash=row['hash'],
                    asset=row['asset'],
                    address_from=row['address_from'],
                    address_to=row['address_to'],
                    value=row['value'],
                    is_token=row['is_token'],
                    type=row['type'],
                    status=row['status'],
                    effective_fee=row['effective_fee'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    deleted_at=row['deleted_at']
                ) for row in rows
            ]

    async def get_transaction_with_confirmations(self, hash: str, web3_repo) -> dict | None:
        """
        Busca uma transação por hash e inclui informações atuais de confirmações
        
        Args:
            hash: Hash da transação
            web3_repo: Repositório Web3 para buscar confirmações
            
        Returns:
            dict com dados da transação e confirmações atuais
        """
        tx = await self.get_transaction_by_hash(hash)
        if not tx:
            return None
            
        # Get current confirmations if transaction is not yet confirmed
        confirmations = 0
        try:
            confirmations = web3_repo.get_transaction_confirmations(hash)
        except Exception:
            # If unable to get confirmations, use default values
            pass
        
        return {
            "hash": tx.hash,
            "asset": tx.asset,
            "address_from": tx.address_from,
            "address_to": tx.address_to,
            "value": tx.value,
            "is_token": tx.is_token,
            "type": tx.type,
            "status": tx.status,
            "effective_fee": tx.effective_fee,
            "created_at": tx.created_at,
            "updated_at": tx.updated_at,
            "confirmations": confirmations,
            "is_confirmed": confirmations >= 1
        } 