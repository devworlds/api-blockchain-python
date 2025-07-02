import os
import time
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Monitoring imports
from prometheus_fastapi_instrumentator import Instrumentator
from web3 import Web3

from app.application.v1.transaction.routers import router as transaction_router
from app.application.v1.wallet.routers import router as wallet_router
from app.infrastructure.blockchain.transaction.node_repository import (
    Web3TransactionRepository,
)
from app.infrastructure.config import load_config
from app.infrastructure.db.transaction.postgresql_repository import (
    PostgreSQLTransactionRepository,
)
from app.infrastructure.db.wallet.postgresql_repository import (
    PostgreSQLWalletRepository,
)
from app.shared.monitoring.logging import get_logger, setup_logging
from app.shared.monitoring.metrics import (
    api_request_duration_seconds,
    api_requests_total,
    database_connection_pool_idle,
    database_connection_pool_size,
    database_connection_pool_used,
    database_health_status,
    record_error,
    set_app_info,
)
from app.shared.monitoring.transaction_monitor import (
    TransactionMonitorManager,
    TransactionMonitorService,
)

config = load_config()

# Setup logging
setup_logging(config.log_level)
logger = get_logger(__name__)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"Starting API Blockchain Python v{config.app_version} ({config.environment})"
    )

    try:
        # Database setup
        pool = await asyncpg.create_pool(config.postgres_dsn)
        app.state.pool = pool  # Store pool reference for health checks
        app.state.wallet_repo = PostgreSQLWalletRepository(pool)
        app.state.transaction_repo = PostgreSQLTransactionRepository(pool)

        # Initialize database metrics
        database_connection_pool_size.set(pool.get_size())
        database_connection_pool_used.set(pool.get_size() - pool.get_idle_size())
        database_connection_pool_idle.set(pool.get_idle_size())
        database_health_status.set(1)  # Healthy

        # Web3 setup
        app.state.web3 = Web3(Web3.HTTPProvider(config.web3_provider_url))
        app.state.web3_repo = Web3TransactionRepository(app.state.web3)

        if app.state.web3.is_connected():
            logger.info(
                f"Web3 connection established - Provider: {config.web3_provider_url}, Chain ID: {app.state.web3.eth.chain_id}"
            )
        else:
            logger.warning(
                f"Web3 connection failed - Provider: {config.web3_provider_url}"
            )

        # Transaction monitor setup
        app.state.transaction_monitor_manager = TransactionMonitorManager()

        # Create monitor for transactions with 1 confirmation (fast)
        fast_monitor = TransactionMonitorService(
            web3_repo=app.state.web3_repo,
            db_repo=app.state.transaction_repo,
            min_confirmations=1,
            poll_interval=15,  # 15 seconds
            max_age_hours=2,  # Last 2 hours
        )

        # Create monitor for transactions with 6 confirmations (secure)
        secure_monitor = TransactionMonitorService(
            web3_repo=app.state.web3_repo,
            db_repo=app.state.transaction_repo,
            min_confirmations=6,
            poll_interval=60,  # 1 minute
            max_age_hours=24,  # Last 24 hours
        )

        app.state.transaction_monitor_manager.add_monitor(fast_monitor)
        app.state.transaction_monitor_manager.add_monitor(secure_monitor)

        # Start monitors
        await app.state.transaction_monitor_manager.start_all()

        set_app_info(config.app_version, config.environment)

        logger.info("Application started successfully with transaction monitoring")

        yield

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        record_error(type(e).__name__, "startup")
        raise
    finally:
        logger.info("Shutting down application")

        # Stop monitors
        if hasattr(app.state, "transaction_monitor_manager"):
            await app.state.transaction_monitor_manager.stop_all()

        # Close connection pool
        if hasattr(app.state, "pool"):
            await app.state.pool.close()


app = FastAPI(
    title="API Blockchain Python",
    description="Secure and scalable REST API for blockchain transaction management with monitoring and observability.",
    version=config.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware
if config.enable_metrics:
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app)


# Custom logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()

    # Log request (DEBUG level for health/metrics to reduce noise)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Use DEBUG level for health and metrics endpoints
    if request.url.path in ["/health", "/metrics"]:
        logger.debug(
            f"HTTP {request.method} {request.url} from {client_ip} ({user_agent})"
        )
    else:
        logger.info(
            f"HTTP {request.method} {request.url} from {client_ip} ({user_agent})"
        )

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response (DEBUG level for health/metrics)
        if request.url.path in ["/health", "/metrics"]:
            logger.debug(
                f"HTTP {request.method} {request.url} completed - Status: {response.status_code}, Duration: {duration:.3f}s"
            )
        else:
            logger.info(
                f"HTTP {request.method} {request.url} completed - Status: {response.status_code}, Duration: {duration:.3f}s"
            )

        # Record metrics
        api_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        api_request_duration_seconds.labels(
            method=request.method, endpoint=request.url.path
        ).observe(duration)

        return response

    except Exception as e:
        duration = time.time() - start_time

        # Log error
        logger.error(
            f"HTTP {request.method} {request.url} failed after {duration:.3f}s: {str(e)}"
        )

        # Record error metrics
        api_requests_total.labels(
            method=request.method, endpoint=request.url.path, status_code=500
        ).inc()

        record_error(type(e).__name__, "http_middleware")

        raise


# Include routers
app.include_router(wallet_router)
app.include_router(transaction_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Enhanced health check endpoint with database connection status"""
    health_info = {
        "status": "ok",
        "version": config.app_version,
        "environment": config.environment,
        "web3_connected": False,
        "database_connected": False,
        "database_pool_size": 0,
        "database_pool_used": 0,
        "vault_connected": False,
        "transaction_monitors": {},
    }

    # Check database connection
    if hasattr(app.state, "pool") and app.state.pool:
        try:
            async with app.state.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_info["database_connected"] = True
            health_info["database_pool_size"] = app.state.pool.get_size()
            health_info["database_pool_used"] = (
                app.state.pool.get_size() - app.state.pool.get_idle_size()
            )

            # Update metrics
            database_connection_pool_size.set(app.state.pool.get_size())
            database_connection_pool_used.set(
                app.state.pool.get_size() - app.state.pool.get_idle_size()
            )
            database_connection_pool_idle.set(app.state.pool.get_idle_size())
            database_health_status.set(1)  # Healthy

        except Exception as e:
            health_info["database_connected"] = False
            health_info["database_error"] = str(e)
            database_health_status.set(0)  # Unhealthy

    # Check Web3 connection
    if hasattr(app.state, "web3") and app.state.web3:
        try:
            health_info["web3_connected"] = app.state.web3.is_connected()
            if health_info["web3_connected"]:
                health_info["chain_id"] = app.state.web3.eth.chain_id
        except Exception:
            health_info["web3_connected"] = False

    # Check Vault connection (if available)
    try:
        # This would need to be implemented based on your vault setup
        # For now, just mark as unknown
        health_info["vault_connected"] = None
    except Exception:
        health_info["vault_connected"] = False

    # Check transaction monitors
    if hasattr(app.state, "transaction_monitor_manager"):
        try:
            health_info["transaction_monitors"] = (
                await app.state.transaction_monitor_manager.health_check()
            )
        except Exception as e:
            health_info["transaction_monitors"] = {"error": str(e)}

    # Determine overall status
    if not health_info["database_connected"]:
        health_info["status"] = "unhealthy"
    elif not health_info["web3_connected"]:
        health_info["status"] = "degraded"

    return health_info


# Prometheus metrics endpoint
if config.enable_metrics:

    @app.get("/metrics", tags=["Monitoring"])
    def metrics():
        """Prometheus metrics endpoint"""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Expose metrics after app setup
    instrumentator.expose(app)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint with API information"""
    logger.info("Root endpoint accessed")
    return {
        "message": "API Blockchain Python",
        "version": config.app_version,
        "environment": config.environment,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics" if config.enable_metrics else None,
    }


@app.get("/test-logs", tags=["Testing"])
def test_logs():
    """Test endpoint to generate various types of logs"""
    from loguru import logger as file_logger

    # Configure file logger specifically for this test
    file_logger.add(
        "logs/app.log",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        rotation="50 MB",
        retention="7 days",
    )

    # Generate logs both to console and file
    logger.info("Test logs endpoint called")
    file_logger.info("Test logs endpoint called - FILE LOG")

    logger.warning("This is a warning message for testing")
    file_logger.warning("This is a warning message for testing - FILE LOG")

    logger.error("This is an error message for testing")
    file_logger.error("This is an error message for testing - FILE LOG")

    # Test structured logging
    logger.info(
        "Structured log test",
        component="test",
        operation="log_generation",
        user_id="test_user",
        duration=0.123,
    )
    file_logger.info(
        "Structured log test - FILE LOG",
        extra={
            "component": "test",
            "operation": "log_generation",
            "user_id": "test_user",
        },
    )

    return {
        "message": "Test logs generated successfully",
        "logs_generated": ["info", "warning", "error", "structured"],
        "check_grafana": "Go to Grafana logs panel to see the logs",
        "file_logs": "Logs also written to logs/app.log",
    }


@app.get("/init-metrics", tags=["Testing"])
async def init_metrics():
    """Initialize database metrics manually"""
    try:
        if hasattr(app.state, "pool") and app.state.pool:
            # Force initialize metrics
            database_connection_pool_size.set(app.state.pool.get_size())
            database_connection_pool_used.set(
                app.state.pool.get_size() - app.state.pool.get_idle_size()
            )
            database_connection_pool_idle.set(app.state.pool.get_idle_size())
            database_health_status.set(1)

            return {
                "message": "Metrics initialized",
                "pool_size": app.state.pool.get_size(),
                "pool_used": app.state.pool.get_size() - app.state.pool.get_idle_size(),
                "pool_idle": app.state.pool.get_idle_size(),
            }
        else:
            database_health_status.set(0)
            return {"message": "No database pool available", "pool_available": False}
    except Exception as e:
        database_health_status.set(0)
        return {"message": f"Error initializing metrics: {str(e)}", "error": True}
