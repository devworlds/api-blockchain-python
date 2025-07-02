from typing import List

from fastapi import APIRouter, Body, Depends, Request

from app.application.v1.wallet.handlers import (create_wallets_handler,
                                                get_all_wallets_handler)
from app.application.v1.wallet.schemas import WalletCreationStatusResponse
from app.application.v1.wallet.usecase import CreateWalletsUseCase
from app.infrastructure.config import load_config
from app.infrastructure.db.wallet.postgresql_repository import (
    EthereumWalletService, HashiCorpVaultService, PostgreSQLWalletRepository)

router = APIRouter(prefix="/v1", tags=["Wallet"])


def get_create_wallets_usecase(request: Request):
    config = load_config()
    vault_service = HashiCorpVaultService(
        url=config.vault_url,
        token=config.vault_token,
        secret_path=config.vault_secret_path,
    )
    wallet_service = EthereumWalletService()
    wallet_repository = request.app.state.wallet_repo
    return CreateWalletsUseCase(vault_service, wallet_service, wallet_repository)


@router.post("/wallets", response_model=WalletCreationStatusResponse, tags=["Wallet"])
async def create_wallets(
    n: int = Body(..., embed=True),
    usecase: CreateWalletsUseCase = Depends(get_create_wallets_usecase),
):
    # Direct file write test
    try:
        with open("logs/app.log", "a") as f:
            f.write(
                f"2025-07-01 16:30:00 | INFO | router | 🚀 POST /wallets called with n={n}\n"
            )
            f.flush()
    except Exception as e:
        pass

    result = await create_wallets_handler(n, usecase)

    # Log result
    try:
        with open("logs/app.log", "a") as f:
            f.write(
                f"2025-07-01 16:30:01 | INFO | router | ✅ POST /wallets completed: {result.status}\n"
            )
            f.flush()
    except Exception as e:
        pass

    return result


from fastapi import APIRouter, Request


@router.get("/wallets")
async def get_all_wallets(request: Request):
    conn = await request.app.state.wallet_repo._pool.acquire()
    try:
        wallets = await get_all_wallets_handler(conn)
    finally:
        await request.app.state.wallet_repo._pool.release(conn)
    return {"wallets": wallets}
