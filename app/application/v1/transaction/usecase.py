import asyncio
import datetime
import re
import time
from http import HTTPStatus

from fastapi import HTTPException
from web3 import Web3

from app.application.v1.transaction.dto import TransactionDTO
from app.application.v1.transaction.schemas import (
    TransactionOnChainRequest,
    TransactionOnChainResponse,
)
from app.domain.transaction.entity import Transaction as TransactionEntity
from app.infrastructure.blockchain.transaction.node_repository import (
    Web3TransactionRepository,
)
from app.infrastructure.db.transaction.postgresql_repository import (
    PostgreSQLTransactionRepository,
)
from app.infrastructure.db.wallet.postgresql_repository import (
    PostgreSQLWalletRepository,
)

# Monitoring imports
from app.shared.monitoring.logging import (
    LoggerMixin,
    get_logger,
    log_blockchain_operation,
    log_database_operation,
    log_function_call,
)
from app.shared.monitoring.metrics import (
    MetricsContext,
    record_blockchain_operation,
    record_transaction_created,
    record_transaction_validated,
    track_time,
    transaction_processing_duration_seconds,
)
from app.shared.utils.validators import wei_to_eth


class GetTransactionHash(LoggerMixin):
    def __init__(
        self,
        tx_hash: str,
        web3_repo: Web3TransactionRepository,
        wallet_repo: PostgreSQLWalletRepository,
        db_repo: PostgreSQLTransactionRepository,
        min_confirmations: int = 12,
    ):
        # Clean the transaction hash by removing any extra spaces
        self.tx_hash = tx_hash.strip()
        self.web3_repo = web3_repo
        self.wallet_repo = wallet_repo
        self.db_repo = db_repo
        self.min_confirmations = min_confirmations

    # Add validation if destination address is ours
    async def validate_destination_address(self, address: str) -> bool:
        """Validate if destination address is one of our wallets"""
        try:
            # Normalize address to lowercase for comparison
            address_lower = address.lower()
            wallet = await self.wallet_repo.get_wallet_by_address(address_lower)
            return wallet is not None
        except Exception as e:
            self.logger.error(
                f"Failed to validate destination address - Address: {address}, Error: {str(e)}"
            )
            return False

    @track_time(
        transaction_processing_duration_seconds,
        {"operation": "validate_transaction", "asset": "unknown"},
    )
    async def execute(self, txhash: str):
        self.logger.info(
            f"Starting transaction validation - Hash: {self.tx_hash}, Min confirmations: {self.min_confirmations}"
        )

        start_time = time.time()

        try:
            with MetricsContext("validate_transaction", "blockchain"):
                tx_data = self.web3_repo.get_transaction(self.tx_hash)

            if not tx_data:
                raise HTTPException(HTTPStatus.NOT_FOUND, "Transaction not found")

            # Determine if this is a token transaction
            is_token = bool(tx_data.get("input") and tx_data.get("input") != "0x")

            # Determine asset type
            if is_token:
                # Get the actual token symbol from the contract
                contract_address = tx_data.get("to")
                if contract_address:
                    asset = self.web3_repo.get_token_symbol(contract_address)
                else:
                    asset = "UNKNOWN"
            else:
                asset = "ETH"  # Always uppercase for consistency

            # Extract transfer information
            transfers = []
            if is_token:
                token_transfers = self.web3_repo.get_transaction_transfers(self.tx_hash)
                transfers.extend(token_transfers)
            else:
                eth_value = int(tx_data.get("value", 0))
                if eth_value > 0:
                    transfers.append(
                        {
                            "asset": "eth",
                            "from": tx_data.get("from"),
                            "address_from": tx_data.get("from"),
                            "value": eth_value,
                        }
                    )

            # Check confirmations
            confirmations = self.web3_repo.get_transaction_confirmations(self.tx_hash)
            is_confirmed = confirmations >= self.min_confirmations

            # Check if destination is our wallet
            # For token transactions, we need to check the actual transfer destinations, not just tx.to
            destination_address = tx_data.get("to")
            is_our_wallet = False

            if is_token:
                # For token transactions, check all transfer destinations
                for transfer in transfers:
                    transfer_to = transfer.get("to")
                    if transfer_to:
                        # Normalize address to lowercase for comparison
                        transfer_to_lower = transfer_to.lower()
                        wallet = await self.wallet_repo.get_wallet_by_address(
                            transfer_to_lower
                        )
                        if wallet:
                            is_our_wallet = True
                            destination_address = (
                                transfer_to  # Update to the actual destination
                            )
                            self.logger.info(
                                f"Token transfer destination is our wallet - Address: {transfer_to}"
                            )
                            break
            else:
                # For ETH transactions, check the direct destination
                if destination_address:
                    is_our_wallet = await self.validate_destination_address(
                        destination_address
                    )

            # Check if this transaction should be saved to database (if either address is ours)
            address_from = tx_data.get("from")
            should_save_transaction = False
            transaction_type = "unknown"
            is_from_our_wallet = False
            is_to_our_wallet = False

            # Check if address_from is one of our wallets
            if address_from:
                # Normalize address to lowercase for comparison
                address_from_lower = address_from.lower()
                wallet_from = await self.wallet_repo.get_wallet_by_address(
                    address_from_lower
                )
                if wallet_from:
                    is_from_our_wallet = True
                    should_save_transaction = True
                    self.logger.info(
                        f"Transaction 'from' address is our wallet - Address: {address_from}"
                    )

            # For token transactions, also check if any transfer source is our wallet
            if is_token:
                for transfer in transfers:
                    transfer_from = transfer.get("from")
                    if transfer_from:
                        # Normalize address to lowercase for comparison
                        transfer_from_lower = transfer_from.lower()
                        wallet_from = await self.wallet_repo.get_wallet_by_address(
                            transfer_from_lower
                        )
                        if wallet_from:
                            is_from_our_wallet = True
                            should_save_transaction = True
                            address_from = transfer_from  # Update to the actual source
                            self.logger.info(
                                f"Token transfer source is our wallet - Address: {transfer_from}"
                            )
                            break

            # Check if destination address is one of our wallets
            if is_our_wallet:
                is_to_our_wallet = True
                should_save_transaction = True
                self.logger.info(
                    f"Transaction 'to' address is our wallet - Address: {destination_address}"
                )

            # Determine transaction type based on wallet involvement
            # Priority: If destination is our wallet, it's primarily a deposit for us
            if is_to_our_wallet and not is_from_our_wallet:
                # External transaction coming to our wallet - this is a deposit
                transaction_type = "deposit"
                self.logger.info(
                    f"External deposit detected (from external to our wallet) - Type: {transaction_type}"
                )
            elif is_from_our_wallet and not is_to_our_wallet:
                # Transaction from our wallet to external - this is a withdrawal
                transaction_type = "withdraw"
                self.logger.info(
                    f"External withdrawal detected (from our wallet to external) - Type: {transaction_type}"
                )
            elif is_from_our_wallet and is_to_our_wallet:
                # Both addresses are ours - this is an internal transfer
                # For internal transfers, we can treat as withdraw from sender perspective
                # But could also create logic to save twice (once as withdraw, once as deposit)
                transaction_type = "withdraw"
                self.logger.info(
                    f"Internal transfer detected (both addresses are ours) - Type: {transaction_type}"
                )
            else:
                # Neither address is ours - this shouldn't happen in this context
                transaction_type = "unknown"
                self.logger.warning(
                    f"Neither address belongs to our wallets - this shouldn't happen here"
                )

            # Save transaction if either address is ours
            if should_save_transaction:
                formatted_tx_hash = (
                    self.tx_hash
                    if self.tx_hash.startswith("0x")
                    else f"0x{self.tx_hash}"
                )

                existing = await self.db_repo.get_transaction_by_hash(formatted_tx_hash)
                if not existing:
                    self.logger.info(
                        f"Transaction not found in database. Persisting transaction - Hash: {formatted_tx_hash}, Type: {transaction_type}"
                    )
                    now = datetime.datetime.now()

                    # For token transactions, save the token value instead of tx.value
                    transaction_value = 0
                    if is_token and transfers:
                        # Use the value from the first transfer that involves our wallet
                        for transfer in transfers:
                            if (
                                transfer.get("from") == address_from
                                and is_from_our_wallet
                            ) or (
                                transfer.get("to") == destination_address
                                and is_to_our_wallet
                            ):
                                transaction_value = transfer.get("value", 0)
                                break
                    else:
                        transaction_value = int(tx_data.get("value", 0) or 0)

                    await self.db_repo.save_transaction(
                        TransactionEntity(
                            hash=formatted_tx_hash,
                            asset=asset,
                            address_from=address_from or "",  # Ensure it's never None
                            address_to=destination_address or "",
                            value=transaction_value,
                            is_token=is_token,
                            type=transaction_type,
                            status="confirmed" if is_confirmed else "pending",
                            effective_fee=None,
                            created_at=now,
                            updated_at=now,
                            deleted_at=None,
                            contract_address=(
                                tx_data.get("to") if is_token else None
                            ),  # Store contract address for tokens
                        )
                    )
                    self.logger.info(
                        f"Transaction saved in database - Hash: {formatted_tx_hash}, Type: {transaction_type}"
                    )
                else:
                    self.logger.info(
                        f"Transaction already exists in database. Skipping save - Hash: {formatted_tx_hash}, Status: {existing.status}"
                    )

            record_transaction_validated(
                is_valid=True,
                is_confirmed=is_confirmed,
                confirmations=confirmations,
                asset=asset,
            )

            duration = time.time() - start_time
            self.logger.info(
                f"Transaction validation completed successfully - Hash: {self.tx_hash}, Token: {is_token}, Confirmations: {confirmations}, Confirmed: {is_confirmed}, Our wallet: {is_our_wallet}, Duration: {duration:.3f}s"
            )

            return {
                "tx_hash": self.tx_hash,
                "tx_data": tx_data,
                "is_token": is_token,
                "confirmations": confirmations,
                "is_confirmed": is_confirmed,
                "min_confirmations_required": self.min_confirmations,
                "is_destination_our_wallet": is_our_wallet,
                "transfers": transfers,
            }

        except HTTPException:
            raise
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Transaction validation failed - Hash: {self.tx_hash}, Error: {str(e)}, Duration: {duration:.3f}s"
            )
            record_blockchain_operation("validate_transaction", "error")
            raise


class CreateOnChainTransaction(LoggerMixin):
    def __init__(
        self,
        web3_repo: Web3TransactionRepository,
        db_repo: PostgreSQLTransactionRepository,
        vault_service,
        wallet_service,
    ):
        self.web3_repo = web3_repo
        self.db_repo = db_repo
        self.vault_service = vault_service
        self.wallet_service = wallet_service

    @track_time(
        transaction_processing_duration_seconds,
        {"operation": "create_transaction", "asset": "unknown"},
    )
    async def execute(
        self, request: TransactionOnChainRequest
    ) -> TransactionOnChainResponse:
        value_in_wei = request.get_value_in_wei()

        self.logger.info(
            f"Starting transaction creation - From: {request.address_from}, To: {request.address_to}, Asset: {request.asset}, Value: {request.value} ETH ({value_in_wei} Wei)"
        )

        start_time = time.time()

        try:
            # Validate required fields
            if (
                not request.address_from
                or not request.address_to
                or not request.asset
                or not request.value
            ):
                self.logger.error(
                    f"Missing required fields - From: {bool(request.address_from)}, To: {bool(request.address_to)}, Asset: {bool(request.asset)}, Value: {bool(request.value)}"
                )
                raise HTTPException(HTTPStatus.BAD_REQUEST, "Missing required fields")

            # 1. Check balance and build transaction
            self.logger.info(f"Building transaction - Asset: {request.asset}")

            with MetricsContext("build_transaction", "blockchain"):
                web3 = self.web3_repo.web3
                address_from = Web3.to_checksum_address(request.address_from)
                address_to = Web3.to_checksum_address(request.address_to)
                nonce = web3.eth.get_transaction_count(address_from)
                chain_id = web3.eth.chain_id

                # Check ETH balance first
                eth_balance = web3.eth.get_balance(address_from)
                self.logger.info(
                    f"Address balance check - Address: {address_from}, ETH Balance: {eth_balance / 1e18:.6f} ETH"
                )

                if eth_balance == 0:
                    self.logger.error(
                        f"Insufficient ETH balance for gas fees - Address: {address_from}, Balance: 0 ETH"
                    )
                    raise HTTPException(
                        HTTPStatus.BAD_REQUEST,
                        f"Insufficient ETH balance for gas fees. Address {address_from} has 0 ETH balance.",
                    )

                # Get current gas price and calculate fees
                gas_price = web3.eth.gas_price
                margin = 1.2
                gas_price = int(gas_price * margin)

                # Handle max_priority_fee with fallback for compatibility
                try:
                    max_priority_fee = web3.eth.max_priority_fee
                except (AttributeError, Exception):
                    # Fallback: use 2 gwei as default priority fee
                    max_priority_fee = 2000000000  # 2 gwei

                max_fee_per_gas = gas_price + max_priority_fee

                if request.asset.lower() == "eth":
                    # For ETH transfers, check if balance covers value + gas fees
                    gas_limit = 21000
                    estimated_gas_cost = gas_limit * max_fee_per_gas
                    total_required = value_in_wei + estimated_gas_cost

                    if eth_balance < total_required:
                        required_eth = total_required / 1e18
                        available_eth = eth_balance / 1e18
                        self.logger.error(
                            f"Insufficient ETH balance - Required: {required_eth:.6f} ETH (value + gas), Available: {available_eth:.6f} ETH"
                        )
                        raise HTTPException(
                            HTTPStatus.BAD_REQUEST,
                            f"Insufficient ETH balance. Required: {required_eth:.6f} ETH (including gas), Available: {available_eth:.6f} ETH",
                        )

                    # Build EIP-1559 transaction for ETH transfer
                    tx = {
                        "from": address_from,
                        "to": address_to,
                        "value": value_in_wei,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "maxFeePerGas": max_fee_per_gas,
                        "maxPriorityFeePerGas": max_priority_fee,
                        "chainId": chain_id,
                        "type": "0x2",  # EIP-1559 transaction type
                    }
                    contract_address = None
                    self.logger.info(
                        f"ETH transaction built - Value: {value_in_wei / 1e18:.6f} ETH, Max fee: {max_fee_per_gas}, Priority fee: {max_priority_fee}, Nonce: {nonce}, Gas cost: {estimated_gas_cost / 1e18:.6f} ETH"
                    )
                else:
                    if not request.contract_address:
                        self.logger.error(
                            f"Contract address required for token transaction - Asset: {request.asset}"
                        )
                        raise HTTPException(
                            HTTPStatus.BAD_REQUEST,
                            "contract_address is required for tokens",
                        )

                    erc20_abi = [
                        {
                            "constant": False,
                            "inputs": [
                                {"name": "_to", "type": "address"},
                                {"name": "_value", "type": "uint256"},
                            ],
                            "name": "transfer",
                            "outputs": [{"name": "", "type": "bool"}],
                            "type": "function",
                        }
                    ]
                    contract = web3.eth.contract(
                        address=Web3.to_checksum_address(request.contract_address),
                        abi=erc20_abi,
                    )
                    data = contract.functions.transfer(
                        address_to, value_in_wei
                    ).build_transaction({"gas": 0, "gasPrice": 0})["data"]

                    # Build EIP-1559 transaction for token transfer
                    tx = {
                        "from": address_from,
                        "to": Web3.to_checksum_address(request.contract_address),
                        "value": 0,
                        "data": data,
                        "nonce": nonce,
                        "chainId": chain_id,
                        "maxFeePerGas": max_fee_per_gas,
                        "maxPriorityFeePerGas": max_priority_fee,
                        "type": "0x2",  # EIP-1559 transaction type
                    }
                    # Estimate gas dynamically for token/contract transactions
                    tx["gas"] = web3.eth.estimate_gas(tx)

                    # For token transfers, check if ETH balance covers gas fees
                    estimated_gas_cost = tx["gas"] * max_fee_per_gas
                    if eth_balance < estimated_gas_cost:
                        required_eth = estimated_gas_cost / 1e18
                        available_eth = eth_balance / 1e18
                        self.logger.error(
                            f"Insufficient ETH balance for token transaction gas - Required: {required_eth:.6f} ETH, Available: {available_eth:.6f} ETH"
                        )
                        raise HTTPException(
                            HTTPStatus.BAD_REQUEST,
                            f"Insufficient ETH balance for gas fees. Required: {required_eth:.6f} ETH, Available: {available_eth:.6f} ETH",
                        )

                    contract_address = request.contract_address
                    self.logger.info(
                        f"Token transaction built - Asset: {request.asset}, Contract: {contract_address}, Max fee: {max_fee_per_gas}, Priority fee: {max_priority_fee}, Nonce: {nonce}, Gas: {tx['gas']}, Gas cost: {estimated_gas_cost / 1e18:.6f} ETH"
                    )

            # 2. Get private key from Vault and sign transaction
            self.logger.info(
                f"Signing transaction with Vault - Address: {address_from}"
            )

            # Add detailed logging for debugging
            self.logger.info(
                f"Transaction details before signing - Chain ID: {chain_id}, Nonce: {nonce}, Gas: {tx['gas']}, Max fee: {max_fee_per_gas}, Priority fee: {max_priority_fee}"
            )

            with MetricsContext("sign_transaction", "vault"):
                key_id = f"eth_wallet_{address_from}"
                private_key = self.vault_service.get_private_key(key_id)

                # Use the modern web3.py v7+ signing method
                signed = web3.eth.account.sign_transaction(tx, private_key)
                signed_tx = signed.raw_transaction.hex()

                # Log signed transaction details
                self.logger.info(
                    f"Transaction signed successfully - Length: {len(signed_tx)}, Prefix: {signed_tx[:20]}"
                )

            # 3. Enviar transação
            self.logger.info("Broadcasting transaction")

            with MetricsContext("broadcast_transaction", "blockchain"):
                # Log before sending
                self.logger.info(
                    f"Sending raw transaction to network - Length: {len(signed_tx)}, Chain ID: {web3.eth.chain_id}"
                )

                # Send the signed transaction
                tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction).hex()
                self.logger.info(f"Transaction sent successfully - Hash: {tx_hash}")

            status = "pending"
            now = datetime.datetime.now()

            # Calculate effective fee based on transaction
            effective_fee = int(tx["gas"] * tx["maxFeePerGas"])

            # 4. Save transaction history
            self.logger.info(f"Saving transaction to database - Hash: {tx_hash}")

            with MetricsContext("save_transaction", "database"):
                # Ensure hash has 0x prefix
                formatted_tx_hash = (
                    tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
                )

                await self.db_repo.save_transaction(
                    TransactionEntity(
                        hash=formatted_tx_hash,
                        asset=request.asset,
                        address_from=request.address_from,
                        address_to=request.address_to,
                        value=value_in_wei,
                        is_token=(request.asset.lower() != "eth"),
                        type="withdraw",
                        status=status,
                        effective_fee=effective_fee,
                        created_at=now,
                        updated_at=now,
                        deleted_at=None,
                        contract_address=(
                            request.contract_address
                            if request.contract_address is not None
                            else None
                        ),
                    )
                )

            # Record metrics
            record_transaction_created(
                asset=request.asset,
                status=status,
                value=float(wei_to_eth(value_in_wei)),
            )

            duration = time.time() - start_time
            self.logger.info(
                f"Transaction created successfully - Hash: {formatted_tx_hash}, Asset: {request.asset}, Status: {status}, Fee: {float(wei_to_eth(effective_fee)):.6f} ETH, Duration: {duration:.2f}s"
            )

            # 5. Return response (background monitor will update status)
            return TransactionOnChainResponse(
                hash=formatted_tx_hash,
                status=status,
                effective_fee=float(wei_to_eth(effective_fee)),
                created_at=now.isoformat(),
                confirmations=0,
                is_confirmed=False,
            )

        except HTTPException:
            # Re-raise HTTP exceptions without additional logging
            raise
        except ValueError as e:
            # Handle specific wallet key not found errors
            if "Private key not found in Vault" in str(e):
                duration = time.time() - start_time
                self.logger.error(
                    f"Transaction creation failed - Wallet key not found - From: {request.address_from}, To: {request.address_to}, Asset: {request.asset}, Error: {str(e)}, Duration: {duration}s"
                )
                record_transaction_created(request.asset, "error")
                raise HTTPException(HTTPStatus.BAD_REQUEST, str(e))
            else:
                duration = time.time() - start_time
                self.logger.error(
                    f"Transaction creation failed - From: {request.address_from}, To: {request.address_to}, Asset: {request.asset}, Error: {str(e)}, Duration: {duration}s"
                )
                record_transaction_created(request.asset, "error")
                raise
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Transaction creation failed - From: {request.address_from}, To: {request.address_to}, Asset: {request.asset}, Error: {str(e)}, Duration: {duration}s"
            )
            record_transaction_created(request.asset, "error")
            raise


class ListTransactions(LoggerMixin):
    def __init__(self, db_repo: PostgreSQLTransactionRepository):
        self.db_repo = db_repo

    async def execute(self, limit: int = 100, offset: int = 0):
        self.logger.info(f"Listing transactions - Limit: {limit}, Offset: {offset}")
        return await self.db_repo.list_transactions(limit=limit, offset=offset)
