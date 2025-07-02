from app.domain.transaction.repository import TransactionRepository
from web3 import Web3

class Web3TransactionRepository(TransactionRepository):
    def __init__(self, web3):
        self.web3 = web3

    def get_transaction(self, tx_hash: str) -> dict:
        tx = self.web3.eth.get_transaction(tx_hash)
        return {
            "input": tx.input,
            "value": tx.value,
            "to": tx.to,
            "from": tx['from'],
            "hash": tx.hash.hex()
        }

    def is_token_transaction(self, transaction_hash: str) -> bool:
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            # Check if transaction has input data (indicates contract interaction/token transfer)
            return tx.input != '0x' and len(tx.input) > 2
        except Exception:
            return False

    def get_transaction_confirmations(self, transaction_hash: str) -> int:
        """Get number of confirmations for a transaction"""
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            if tx.blockNumber is None:
                print(f"[DEBUG] Transaction {transaction_hash} is pending (blockNumber is None)")
                return 0  # Transaction is pending
            current_block = self.web3.eth.block_number
            confirmations = current_block - tx.blockNumber + 1
            print(f"[DEBUG] Transaction {transaction_hash}: blockNumber={tx.blockNumber}, current_block={current_block}, confirmations={confirmations}")
            return confirmations
        except Exception as e:
            print(f"[ERROR] Failed to get confirmations for {transaction_hash}: {e}")
            return 0

    def is_transaction_confirmed(self, transaction_hash: str, min_confirmations: int = 6) -> bool:
        """Check if transaction has minimum confirmations for persistence"""
        try:
            confirmations = self.get_transaction_confirmations(transaction_hash)
            return confirmations >= min_confirmations
        except Exception:
            return False

    def is_valid_transaction(self, transaction_hash: str, require_confirmations: bool = True, min_confirmations: int = 6) -> bool:
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            if tx is None or not hasattr(tx, 'hash'):
                print(f"[DEBUG] Transaction {transaction_hash} not found or missing hash attribute")
                return False
            if require_confirmations:
                result = self.is_transaction_confirmed(transaction_hash, min_confirmations)
                print(f"[DEBUG] is_transaction_confirmed({transaction_hash}, {min_confirmations}) = {result}")
                return result
            print(f"[DEBUG] Transaction {transaction_hash} found and confirmations not required")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to validate transaction {transaction_hash}: {e}")
            return False

    def get_transaction_transfers(self, tx_hash: str) -> list:
        """
        Retorna uma lista de transferências (ETH ou tokens) associadas a um tx_hash.
        Cada item é um dicionário com: asset, from, to, value
        """
        tx = self.web3.eth.get_transaction(tx_hash)
        transfers = []
        # ETH transfer
        if tx.value and tx.value > 0:
            transfers.append({
                "asset": "eth",
                "from": tx['from'],
                "to": tx['to'],
                "value": tx.value
            })
        # Token transfers (ERC20)
        try:
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            for log in receipt.logs:
                # ERC20 Transfer event signature
                if log.topics and log.topics[0].hex() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
                    from_address = "0x" + log.topics[1].hex()[-40:]
                    to_address = "0x" + log.topics[2].hex()[-40:]
                    value = int(log.data, 16)
                    transfers.append({
                        "asset": "token",
                        "from": from_address,
                        "to": to_address,
                        "value": value
                    })
        except Exception:
            pass
        return transfers