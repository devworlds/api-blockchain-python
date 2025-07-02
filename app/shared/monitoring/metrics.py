from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable, Any
import asyncio

# API Request Metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint']
)

# Transaction Metrics
transactions_created_total = Counter(
    'transactions_created_total',
    'Total number of transactions created',
    ['asset', 'status']
)

transactions_validated_total = Counter(
    'transactions_validated_total',
    'Total number of transactions validated',
    ['is_valid', 'is_confirmed']
)

transaction_processing_duration_seconds = Histogram(
    'transaction_processing_duration_seconds',
    'Time spent processing transactions',
    ['operation', 'asset']
)

transaction_value_total = Counter(
    'transaction_value_total',
    'Total value of transactions processed',
    ['asset']
)

# Blockchain Metrics
blockchain_confirmations = Histogram(
    'blockchain_confirmations',
    'Number of confirmations for transactions',
    ['asset']
)

blockchain_operations_total = Counter(
    'blockchain_operations_total',
    'Total blockchain operations',
    ['operation', 'status']
)

blockchain_operation_duration_seconds = Histogram(
    'blockchain_operation_duration_seconds',
    'Blockchain operation duration',
    ['operation']
)

# Wallet Metrics
wallets_created_total = Counter(
    'wallets_created_total',
    'Total number of wallets created'
)

wallet_operations_total = Counter(
    'wallet_operations_total',
    'Total wallet operations',
    ['operation', 'status']
)

# Vault Metrics
vault_operations_total = Counter(
    'vault_operations_total',
    'Total Vault operations',
    ['operation', 'status']
)

vault_operation_duration_seconds = Histogram(
    'vault_operation_duration_seconds',
    'Vault operation duration',
    ['operation']
)

# Database Metrics
database_operations_total = Counter(
    'database_operations_total',
    'Total database operations',
    ['operation', 'table', 'status']
)

database_operation_duration_seconds = Histogram(
    'database_operation_duration_seconds',
    'Database operation duration',
    ['operation', 'table']
)

database_connection_pool_size = Gauge(
    'database_connection_pool_size',
    'Current database connection pool size'
)

database_connection_pool_used = Gauge(
    'database_connection_pool_used',
    'Current database connection pool used connections'
)

database_connection_pool_idle = Gauge(
    'database_connection_pool_idle',
    'Current database connection pool idle connections'
)

database_health_status = Gauge(
    'database_health_status',
    'Database health status (1=healthy, 0=unhealthy)'
)

# System Metrics
app_info = Info(
    'app_info',
    'Application information'
)

# Error Metrics
errors_total = Counter(
    'errors_total',
    'Total number of errors',
    ['error_type', 'component']
)

# Decorators for automatic metrics collection

def track_time(metric: Histogram, labels: dict = None):
    """Decorator to track execution time"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def count_calls(metric: Counter, labels: dict = None):
    """Decorator to count function calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                result = await func(*args, **kwargs)
                if labels:
                    metric.labels(**labels).inc()
                else:
                    metric.inc()
                return result
            except Exception as e:
                if labels:
                    error_labels = {**labels, 'status': 'error'}
                    metric.labels(**error_labels).inc()
                else:
                    metric.inc()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                result = func(*args, **kwargs)
                if labels:
                    metric.labels(**labels).inc()
                else:
                    metric.inc()
                return result
            except Exception as e:
                if labels:
                    error_labels = {**labels, 'status': 'error'}
                    metric.labels(**error_labels).inc()
                else:
                    metric.inc()
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Metrics collection functions

def record_transaction_created(asset: str, status: str, value: float = None):
    """Record a transaction creation"""
    transactions_created_total.labels(asset=asset, status=status).inc()
    if value and asset:
        transaction_value_total.labels(asset=asset).inc(value)

def record_transaction_validated(is_valid: bool, is_confirmed: bool, confirmations: int = None, asset: str = None):
    """Record a transaction validation"""
    transactions_validated_total.labels(
        is_valid=str(is_valid), 
        is_confirmed=str(is_confirmed)
    ).inc()
    if confirmations is not None and asset:
        blockchain_confirmations.labels(asset=asset).observe(confirmations)

def record_blockchain_operation(operation: str, status: str, duration: float = None):
    """Record a blockchain operation"""
    blockchain_operations_total.labels(operation=operation, status=status).inc()
    if duration is not None:
        blockchain_operation_duration_seconds.labels(operation=operation).observe(duration)

def record_vault_operation(operation: str, status: str, duration: float = None):
    """Record a Vault operation"""
    vault_operations_total.labels(operation=operation, status=status).inc()
    if duration is not None:
        vault_operation_duration_seconds.labels(operation=operation).observe(duration)

def record_database_operation(operation: str, table: str, status: str, duration: float = None):
    """Record a database operation"""
    database_operations_total.labels(operation=operation, table=table, status=status).inc()
    if duration is not None:
        database_operation_duration_seconds.labels(operation=operation, table=table).observe(duration)

def record_wallet_created(count: int = 1):
    """Record wallet creation"""
    wallets_created_total.inc(count)

def record_wallet_operation(operation: str, status: str):
    """Record wallet operation"""
    wallet_operations_total.labels(operation=operation, status=status).inc()

def record_error(error_type: str, component: str):
    """Record an error"""
    errors_total.labels(error_type=error_type, component=component).inc()

def set_app_info(version: str, environment: str):
    """Set application information"""
    app_info.info({
        'version': version,
        'environment': environment
    })

# Context managers for tracking operations

class MetricsContext:
    """Context manager for tracking metrics"""
    
    def __init__(self, operation: str, component: str):
        self.operation = operation
        self.component = component
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            status = "success"
        else:
            status = "error"
            record_error(exc_type.__name__, self.component)
        
        # Record operation based on component
        if self.component == "blockchain":
            record_blockchain_operation(self.operation, status, duration)
        elif self.component == "vault":
            record_vault_operation(self.operation, status, duration)
        elif self.component == "database":
            # Assume table name is in operation or default
            table = "unknown"
            record_database_operation(self.operation, table, status, duration)
        elif self.component == "wallet":
            record_wallet_operation(self.operation, status) 