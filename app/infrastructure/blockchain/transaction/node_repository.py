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
            "from": tx["from"],
            "hash": tx.hash.hex(),
        }

    def is_token_transaction(self, transaction_hash: str) -> bool:
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            # Check if transaction has input data (indicates contract interaction/token transfer)
            return tx.input != "0x" and len(tx.input) > 2
        except Exception:
            return False

    def get_transaction_confirmations(self, transaction_hash: str) -> int:
        """Get number of confirmations for a transaction"""
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            if tx.blockNumber is None:
                print(
                    f"[DEBUG] Transaction {transaction_hash} is pending (blockNumber is None)"
                )
                return 0  # Transaction is pending
            current_block = self.web3.eth.block_number
            confirmations = current_block - tx.blockNumber + 1
            print(
                f"[DEBUG] Transaction {transaction_hash}: blockNumber={tx.blockNumber}, current_block={current_block}, confirmations={confirmations}"
            )
            return confirmations
        except Exception as e:
            print(f"[ERROR] Failed to get confirmations for {transaction_hash}: {e}")
            return 0

    def is_transaction_confirmed(
        self, transaction_hash: str, min_confirmations: int = 6
    ) -> bool:
        """Check if transaction has minimum confirmations for persistence"""
        try:
            confirmations = self.get_transaction_confirmations(transaction_hash)
            return confirmations >= min_confirmations
        except Exception:
            return False

    def is_valid_transaction(
        self,
        transaction_hash: str,
        require_confirmations: bool = True,
        min_confirmations: int = 6,
    ) -> bool:
        try:
            tx = self.web3.eth.get_transaction(transaction_hash)
            if tx is None or not hasattr(tx, "hash"):
                print(
                    f"[DEBUG] Transaction {transaction_hash} not found or missing hash attribute"
                )
                return False
            if require_confirmations:
                result = self.is_transaction_confirmed(
                    transaction_hash, min_confirmations
                )
                print(
                    f"[DEBUG] is_transaction_confirmed({transaction_hash}, {min_confirmations}) = {result}"
                )
                return result
            print(
                f"[DEBUG] Transaction {transaction_hash} found and confirmations not required"
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to validate transaction {transaction_hash}: {e}")
            return False

    def get_transaction_transfers(self, tx_hash: str) -> list:
        """
        Retorna uma lista de transferências (ETH ou tokens) associadas a um tx_hash.
        Cada item é um dicionário com: asset, from, to, value
        """
        print(f"[DEBUG] get_transaction_transfers called for {tx_hash}")
        tx = self.web3.eth.get_transaction(tx_hash)
        transfers = []

        # ETH transfer
        if tx.value and tx.value > 0:
            print(f"[DEBUG] ETH transfer found: value={tx.value}")
            transfers.append(
                {"asset": "eth", "from": tx["from"], "to": tx["to"], "value": tx.value}
            )
        else:
            print(f"[DEBUG] No ETH transfer found: tx.value={tx.value}")

        # Token transfers (ERC20)
        try:
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            print(f"[DEBUG] Transaction receipt found, logs count: {len(receipt.logs)}")

            for i, log in enumerate(receipt.logs):
                print(
                    f"[DEBUG] Processing log {i}: topics={len(log.topics) if log.topics else 0}"
                )

                # ERC20 Transfer event signature (without 0x prefix)
                transfer_signature = (
                    "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                )

                if log.topics and len(log.topics) > 0:
                    # Get topic without 0x prefix for comparison
                    topic_hex = log.topics[0].hex()
                    print(f"[DEBUG] Log {i} topic[0]: {topic_hex}")

                    if topic_hex == transfer_signature:
                        print(f"[DEBUG] Log {i} is a Transfer event")
                        if len(log.topics) >= 3:
                            from_address = "0x" + log.topics[1].hex()[-40:]
                            to_address = "0x" + log.topics[2].hex()[-40:]

                            # Convert log.data to hex string if it's bytes
                            if isinstance(log.data, bytes):
                                data_hex = log.data.hex()
                            else:
                                data_hex = (
                                    log.data[2:]
                                    if log.data.startswith("0x")
                                    else log.data
                                )

                            value = int(data_hex, 16) if data_hex else 0
                            print(
                                f"[DEBUG] Token Transfer detected: from={from_address}, to={to_address}, value={value}"
                            )
                            transfers.append(
                                {
                                    "asset": "token",
                                    "from": from_address,
                                    "to": to_address,
                                    "value": value,
                                }
                            )
                        else:
                            print(
                                f"[DEBUG] Log {i} Transfer event has insufficient topics: {len(log.topics)}"
                            )
                    else:
                        print(f"[DEBUG] Log {i} is not a Transfer event")
                else:
                    print(f"[DEBUG] Log {i} has no topics")

        except Exception as e:
            print(f"[ERROR] Failed to get transaction receipt for {tx_hash}: {e}")

        print(f"[DEBUG] get_transaction_transfers returning {len(transfers)} transfers")
        return transfers

    def get_token_symbol(self, contract_address: str) -> str:
        """
        Get the symbol of an ERC20 token from its contract address.
        Returns the symbol or 'UNKNOWN' if unable to retrieve.
        """
        try:
            # Standard ERC20 ABI for symbol() function
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function",
                }
            ]

            contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(contract_address), abi=erc20_abi
            )

            symbol = contract.functions.symbol().call()
            # Normalize symbol to uppercase for consistency
            symbol_upper = symbol.upper()
            print(
                f"[DEBUG] Token symbol for {contract_address}: {symbol} -> {symbol_upper}"
            )
            return symbol_upper

        except Exception as e:
            print(f"[ERROR] Failed to get token symbol for {contract_address}: {e}")
            return "UNKNOWN"
