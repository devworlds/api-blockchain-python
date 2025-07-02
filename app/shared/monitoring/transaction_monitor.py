import asyncio
import time
from typing import List
from app.shared.monitoring.logging import get_logger, LoggerMixin
from app.infrastructure.blockchain.transaction.node_repository import (
    Web3TransactionRepository,
)
from app.infrastructure.db.transaction.postgresql_repository import (
    PostgreSQLTransactionRepository,
)


class TransactionMonitorService(LoggerMixin):
    """
    Service to monitor pending transactions in background
    and update their status when confirmed
    """

    def __init__(
        self,
        web3_repo: Web3TransactionRepository,
        db_repo: PostgreSQLTransactionRepository,
        min_confirmations: int = 1,
        poll_interval: int = 30,
        max_age_hours: int = 24,
    ):
        self.web3_repo = web3_repo
        self.db_repo = db_repo
        self.min_confirmations = min_confirmations
        self.poll_interval = poll_interval
        self.max_age_hours = max_age_hours
        self.running = False
        self._task = None

    async def start(self):
        """Start the monitoring service"""
        if self.running:
            self.logger.warning("Transaction monitor is already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.logger.info(
            f"Transaction monitor service started - Min confirmations: {self.min_confirmations}, Poll interval: {self.poll_interval}s"
        )

    async def stop(self):
        """Stop the monitoring service"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("Transaction monitor service stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._check_pending_transactions()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
                await asyncio.sleep(self.poll_interval)

    async def _check_pending_transactions(self):
        """Check pending transactions and update status"""
        try:
            # Get pending transactions
            pending_transactions = await self.db_repo.get_pending_transactions(
                max_age_hours=self.max_age_hours
            )

            if not pending_transactions:
                self.logger.debug("No pending transactions to check")
                return

            self.logger.info(
                f"Checking {len(pending_transactions)} pending transactions"
            )

            for tx in pending_transactions:
                await self._check_transaction_status(tx.hash)
                # Small pause between checks to avoid overwhelming the node
                await asyncio.sleep(0.5)

        except Exception as e:
            self.logger.error(f"Error checking pending transactions: {str(e)}")

    async def _check_transaction_status(self, tx_hash: str):
        """Check the status of a specific transaction"""
        try:
            # Check confirmations
            confirmations = self.web3_repo.get_transaction_confirmations(tx_hash)

            if confirmations >= self.min_confirmations:
                # Transaction confirmed
                success = await self.db_repo.update_transaction_status(
                    tx_hash, "confirmed"
                )
                if success:
                    self.logger.info(
                        f"Transaction {tx_hash[:10]}... confirmed and updated ({confirmations} confirmations)"
                    )
                else:
                    self.logger.warning(
                        f"Failed to update transaction status for {tx_hash[:10]}..."
                    )
            else:
                self.logger.debug(
                    f"Transaction {tx_hash[:10]}... still pending ({confirmations}/{self.min_confirmations} confirmations)"
                )

        except Exception as e:
            self.logger.error(
                f"Error checking transaction status for {tx_hash[:10]}...: {str(e)}"
            )


class TransactionMonitorManager:
    """
    Manager to control multiple monitor instances
    """

    def __init__(self):
        self.monitors: List[TransactionMonitorService] = []
        self.logger = get_logger(__name__)

    def add_monitor(self, monitor: TransactionMonitorService):
        """Add a monitor to the list"""
        self.monitors.append(monitor)

    async def start_all(self):
        """Start all monitors"""
        for monitor in self.monitors:
            await monitor.start()
        self.logger.info(f"All {len(self.monitors)} transaction monitors started")

    async def stop_all(self):
        """Stop all monitors"""
        for monitor in self.monitors:
            await monitor.stop()
        self.logger.info("All transaction monitors stopped")

    async def health_check(self) -> dict:
        """Return health status of monitors"""
        return {
            "total_monitors": len(self.monitors),
            "running_monitors": sum(1 for m in self.monitors if m.running),
            "status": (
                "healthy" if all(m.running for m in self.monitors) else "degraded"
            ),
        }
