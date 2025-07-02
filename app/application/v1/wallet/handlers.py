import logging
from datetime import datetime
from typing import List

from app.application.v1.wallet.schemas import WalletCreationStatusResponse
from app.application.v1.wallet.usecase import (CreateWalletsUseCase,
                                               GetAllWalletsUseCase)


# Simple, direct logging
def write_log(level: str, message: str, extra_data: dict = None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} | {level} | wallet_handler | {message}"
    if extra_data:
        log_entry += f" | {extra_data}"

    # Write to file directly
    try:
        with open("logs/app.log", "a") as f:
            f.write(log_entry + "\n")
            f.flush()
    except:
        pass  # Fail silently

    # Also use standard logging
    logger = logging.getLogger(__name__)
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)


async def create_wallets_handler(
    n: int, usecase: CreateWalletsUseCase
) -> WalletCreationStatusResponse:
    """
    Handler to create N Ethereum wallets using the provided usecase.
    """
    write_log(
        "INFO",
        f"🏦 Iniciando criação de {n} carteira(s)",
        {"operation": "create_wallets", "wallet_count": n},
    )

    try:
        addresses = await usecase.execute(n)
        write_log(
            "INFO",
            f"✅ {len(addresses)} carteira(s) criada(s) com sucesso",
            {
                "operation": "create_wallets_success",
                "wallet_count": len(addresses),
                "addresses": addresses[
                    :3
                ],  # Only first 3 addresses to avoid too long logs
            },
        )
        return WalletCreationStatusResponse(
            status="success", detail=f"{len(addresses)} wallet(s) created successfully."
        )
    except Exception as e:
        write_log(
            "ERROR",
            f"❌ Erro ao criar carteiras: {str(e)}",
            {"operation": "create_wallets_error", "wallet_count": n, "error": str(e)},
        )
        raise


async def get_all_wallets_handler(conn):
    """
    Handler to get all active wallets (not soft-deleted).
    """
    write_log(
        "INFO",
        "📋 Consultando todas as carteiras ativas",
        {"operation": "get_all_wallets"},
    )

    try:
        usecase = GetAllWalletsUseCase(conn)
        wallets = await usecase.execute()
        write_log(
            "INFO",
            f"✅ {len(wallets)} carteira(s) encontrada(s)",
            {"operation": "get_all_wallets_success", "wallet_count": len(wallets)},
        )
        return wallets  # This will be a list of dicts with 'address'
    except Exception as e:
        write_log(
            "ERROR",
            f"❌ Erro ao consultar carteiras: {str(e)}",
            {"operation": "get_all_wallets_error", "error": str(e)},
        )
        raise
