import asyncio

from fastapi import APIRouter, Depends, Query, Request

from app.application.v1.transaction.handlers import (
    check_transaction_handler, create_onchain_transaction_handler,
    list_transactions_handler)
from app.application.v1.transaction.schemas import (TransactionDTO,
                                                    TransactionHashResponse,
                                                    TransactionOnChainRequest,
                                                    TransactionOnChainResponse)
from app.application.v1.transaction.usecase import (CreateOnChainTransaction,
                                                    GetTransactionHash,
                                                    ListTransactions)
from app.infrastructure.blockchain.transaction.node_repository import \
    Web3TransactionRepository
from app.infrastructure.config import load_config
from app.infrastructure.db.transaction.postgresql_repository import \
    PostgreSQLTransactionRepository
from app.infrastructure.db.wallet.postgresql_repository import (
    EthereumWalletService, HashiCorpVaultService)
from app.shared.utils.validators import wei_to_eth

router = APIRouter(prefix="/v1", tags=["Transaction"])


def get_transaction_usecase(tx_hash: str, request: Request):
    web3_repo = Web3TransactionRepository(request.app.state.web3)
    wallet_repo = request.app.state.wallet_repo
    db_repo = request.app.state.transaction_repo
    return GetTransactionHash(tx_hash, web3_repo, wallet_repo, db_repo)


@router.get(
    "/transaction/{tx_hash}",
    response_model=TransactionHashResponse,
    tags=["Transaction"],
)
async def check_transaction(
    tx_hash: str,
    request: Request,
    usecase: GetTransactionHash = Depends(get_transaction_usecase),
):
    return await check_transaction_handler(tx_hash, usecase)


@router.get(
    "/transaction/status/{tx_hash}",
    response_model=TransactionOnChainResponse,
    tags=["Transaction"],
)
async def get_transaction_status(tx_hash: str, request: Request):
    """
    Busca informações detalhadas de uma transação incluindo confirmações atuais
    """
    db_repo = request.app.state.transaction_repo
    web3_repo = Web3TransactionRepository(request.app.state.web3)

    tx_data = await db_repo.get_transaction_with_confirmations(tx_hash, web3_repo)

    if not tx_data:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionOnChainResponse(
        hash=tx_data["hash"],
        status=tx_data["status"],
        effective_fee=(
            float(wei_to_eth(tx_data["effective_fee"]))
            if tx_data["effective_fee"]
            else 0.0
        ),
        created_at=tx_data["created_at"].isoformat(),
        confirmations=tx_data["confirmations"],
        is_confirmed=tx_data["is_confirmed"],
    )


def get_create_onchain_usecase(request: Request):
    config = load_config()
    vault_service = HashiCorpVaultService(
        url=config.vault_url,
        token=config.vault_token,
        secret_path=config.vault_secret_path,
    )
    wallet_service = EthereumWalletService()
    web3_repo = Web3TransactionRepository(request.app.state.web3)
    transaction_repo = request.app.state.transaction_repo
    return CreateOnChainTransaction(
        web3_repo, transaction_repo, vault_service, wallet_service
    )


@router.post(
    "/transaction", response_model=TransactionOnChainResponse, tags=["Transaction"]
)
async def create_onchain_transaction(
    request_body: TransactionOnChainRequest,
    request: Request,
    usecase: CreateOnChainTransaction = Depends(get_create_onchain_usecase),
):
    return await create_onchain_transaction_handler(request_body, usecase)


def get_list_transactions_usecase(request: Request):
    db_repo = request.app.state.transaction_repo
    return ListTransactions(db_repo)


@router.get("/transaction", response_model=list[TransactionDTO], tags=["Transaction"])
async def list_transactions(
    request: Request,
    limit: int = Query(
        100, ge=1, le=1000, description="Max number of transactions to return"
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    usecase: ListTransactions = Depends(get_list_transactions_usecase),
):
    return await list_transactions_handler(usecase, limit=limit, offset=offset)
