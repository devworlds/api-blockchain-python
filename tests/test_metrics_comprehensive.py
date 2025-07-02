import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.shared.monitoring.metrics import (  # Metrics instances; Functions
    MetricsContext,
    api_request_duration_seconds,
    api_requests_total,
    app_info,
    blockchain_confirmations,
    blockchain_operation_duration_seconds,
    blockchain_operations_total,
    count_calls,
    database_connection_pool_idle,
    database_connection_pool_size,
    database_connection_pool_used,
    database_health_status,
    database_operation_duration_seconds,
    database_operations_total,
    errors_total,
    record_blockchain_operation,
    record_database_operation,
    record_error,
    record_transaction_created,
    record_transaction_validated,
    record_vault_operation,
    record_wallet_created,
    record_wallet_operation,
    set_app_info,
    track_time,
    transaction_processing_duration_seconds,
    transaction_value_total,
    transactions_created_total,
    transactions_validated_total,
    vault_operation_duration_seconds,
    vault_operations_total,
    wallet_operations_total,
    wallets_created_total,
)


class TestMetricsInstances:
    """Test metrics instances are properly initialized"""

    def test_api_metrics_initialized(self):
        """Test API metrics are properly initialized"""
        assert api_requests_total._name == "api_requests"
        assert api_request_duration_seconds._name == "api_request_duration_seconds"
        assert "method" in api_requests_total._labelnames
        assert "endpoint" in api_requests_total._labelnames
        assert "status_code" in api_requests_total._labelnames

    def test_transaction_metrics_initialized(self):
        """Test transaction metrics are properly initialized"""
        assert transactions_created_total._name == "transactions_created"
        assert transactions_validated_total._name == "transactions_validated"
        assert (
            transaction_processing_duration_seconds._name
            == "transaction_processing_duration_seconds"
        )
        assert transaction_value_total._name == "transaction_value"

        assert "asset" in transactions_created_total._labelnames
        assert "status" in transactions_created_total._labelnames

    def test_blockchain_metrics_initialized(self):
        """Test blockchain metrics are properly initialized"""
        assert blockchain_confirmations._name == "blockchain_confirmations"
        assert blockchain_operations_total._name == "blockchain_operations"
        assert (
            blockchain_operation_duration_seconds._name
            == "blockchain_operation_duration_seconds"
        )

        assert "asset" in blockchain_confirmations._labelnames
        assert "operation" in blockchain_operations_total._labelnames
        assert "status" in blockchain_operations_total._labelnames

    def test_wallet_metrics_initialized(self):
        """Test wallet metrics are properly initialized"""
        assert wallets_created_total._name == "wallets_created"
        assert wallet_operations_total._name == "wallet_operations"

        assert "operation" in wallet_operations_total._labelnames
        assert "status" in wallet_operations_total._labelnames

    def test_vault_metrics_initialized(self):
        """Test vault metrics are properly initialized"""
        assert vault_operations_total._name == "vault_operations"
        assert (
            vault_operation_duration_seconds._name == "vault_operation_duration_seconds"
        )

        assert "operation" in vault_operations_total._labelnames
        assert "status" in vault_operations_total._labelnames

    def test_database_metrics_initialized(self):
        """Test database metrics are properly initialized"""
        assert database_operations_total._name == "database_operations"
        assert (
            database_operation_duration_seconds._name
            == "database_operation_duration_seconds"
        )
        assert database_connection_pool_size._name == "database_connection_pool_size"
        assert database_connection_pool_used._name == "database_connection_pool_used"
        assert database_connection_pool_idle._name == "database_connection_pool_idle"
        assert database_health_status._name == "database_health_status"

        assert "operation" in database_operations_total._labelnames
        assert "table" in database_operations_total._labelnames
        assert "status" in database_operations_total._labelnames

    def test_system_metrics_initialized(self):
        """Test system metrics are properly initialized"""
        assert app_info._name == "app_info"
        assert errors_total._name == "errors"

        assert "error_type" in errors_total._labelnames
        assert "component" in errors_total._labelnames


class TestTrackTimeDecorator:
    """Test track_time decorator"""

    def test_track_time_sync_function(self):
        """Test track_time decorator with synchronous function"""
        mock_metric = Mock()

        @track_time(mock_metric)
        def test_function():
            time.sleep(0.01)  # Small delay
            return "result"

        result = test_function()

        assert result == "result"
        mock_metric.observe.assert_called_once()
        # Check that duration is reasonable (> 0)
        call_args = mock_metric.observe.call_args[0]
        assert call_args[0] > 0

    def test_track_time_sync_function_with_labels(self):
        """Test track_time decorator with labels"""
        mock_metric = Mock()
        mock_labeled_metric = Mock()
        mock_metric.labels.return_value = mock_labeled_metric

        labels = {"operation": "test", "component": "api"}

        @track_time(mock_metric, labels)
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        mock_metric.labels.assert_called_once_with(**labels)
        mock_labeled_metric.observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_time_async_function(self):
        """Test track_time decorator with async function"""
        mock_metric = Mock()

        @track_time(mock_metric)
        async def test_async_function():
            await asyncio.sleep(0.01)  # Small delay
            return "async_result"

        result = await test_async_function()

        assert result == "async_result"
        mock_metric.observe.assert_called_once()
        call_args = mock_metric.observe.call_args[0]
        assert call_args[0] > 0

    @pytest.mark.asyncio
    async def test_track_time_async_function_with_labels(self):
        """Test track_time decorator with async function and labels"""
        mock_metric = Mock()
        mock_labeled_metric = Mock()
        mock_metric.labels.return_value = mock_labeled_metric

        labels = {"operation": "async_test"}

        @track_time(mock_metric, labels)
        async def test_async_function():
            return "async_result"

        result = await test_async_function()

        assert result == "async_result"
        mock_metric.labels.assert_called_once_with(**labels)
        mock_labeled_metric.observe.assert_called_once()

    def test_track_time_sync_function_with_exception(self):
        """Test track_time decorator handles exceptions in sync function"""
        mock_metric = Mock()

        @track_time(mock_metric)
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            test_function()

        # Should still record timing even with exception
        mock_metric.observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_time_async_function_with_exception(self):
        """Test track_time decorator handles exceptions in async function"""
        mock_metric = Mock()

        @track_time(mock_metric)
        async def test_async_function():
            raise ValueError("Async test error")

        with pytest.raises(ValueError, match="Async test error"):
            await test_async_function()

        # Should still record timing even with exception
        mock_metric.observe.assert_called_once()


class TestCountCallsDecorator:
    """Test count_calls decorator"""

    def test_count_calls_sync_function_success(self):
        """Test count_calls decorator with successful sync function"""
        mock_metric = Mock()

        @count_calls(mock_metric)
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        mock_metric.inc.assert_called_once()

    def test_count_calls_sync_function_with_labels(self):
        """Test count_calls decorator with labels"""
        mock_metric = Mock()
        mock_labeled_metric = Mock()
        mock_metric.labels.return_value = mock_labeled_metric

        labels = {"operation": "test"}

        @count_calls(mock_metric, labels)
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        mock_metric.labels.assert_called_once_with(**labels)
        mock_labeled_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_calls_async_function_success(self):
        """Test count_calls decorator with successful async function"""
        mock_metric = Mock()

        @count_calls(mock_metric)
        async def test_async_function():
            return "async_result"

        result = await test_async_function()

        assert result == "async_result"
        mock_metric.inc.assert_called_once()

    def test_count_calls_sync_function_with_exception(self):
        """Test count_calls decorator handles exceptions in sync function"""
        mock_metric = Mock()
        mock_labeled_metric = Mock()
        mock_metric.labels.return_value = mock_labeled_metric

        @count_calls(mock_metric)
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            test_function()

        # Should still increment with error status
        mock_metric.inc.assert_called_once()

    def test_count_calls_sync_function_with_labels_and_exception(self):
        """Test count_calls decorator with labels and exception"""
        mock_metric = Mock()
        mock_labeled_metric = Mock()
        mock_metric.labels.return_value = mock_labeled_metric

        labels = {"operation": "test"}

        @count_calls(mock_metric, labels)
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            test_function()

        # Should call with error status added to labels
        expected_labels = {**labels, "status": "error"}
        mock_metric.labels.assert_called_once_with(**expected_labels)
        mock_labeled_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_calls_async_function_with_exception(self):
        """Test count_calls decorator handles exceptions in async function"""
        mock_metric = Mock()

        @count_calls(mock_metric)
        async def test_async_function():
            raise ValueError("Async test error")

        with pytest.raises(ValueError, match="Async test error"):
            await test_async_function()

        mock_metric.inc.assert_called_once()


class TestMetricsRecordingFunctions:
    """Test metrics recording functions"""

    @patch("app.shared.monitoring.metrics.transactions_created_total")
    @patch("app.shared.monitoring.metrics.transaction_value_total")
    def test_record_transaction_created(self, mock_value_metric, mock_created_metric):
        """Test record_transaction_created function"""
        mock_labeled_created = Mock()
        mock_labeled_value = Mock()
        mock_created_metric.labels.return_value = mock_labeled_created
        mock_value_metric.labels.return_value = mock_labeled_value

        record_transaction_created("ETH", "pending", 1.5)

        mock_created_metric.labels.assert_called_once_with(
            asset="ETH", status="pending"
        )
        mock_labeled_created.inc.assert_called_once()
        mock_value_metric.labels.assert_called_once_with(asset="ETH")
        mock_labeled_value.inc.assert_called_once_with(1.5)

    @patch("app.shared.monitoring.metrics.transactions_created_total")
    def test_record_transaction_created_without_value(self, mock_created_metric):
        """Test record_transaction_created without value"""
        mock_labeled_created = Mock()
        mock_created_metric.labels.return_value = mock_labeled_created

        record_transaction_created("ETH", "pending")

        mock_created_metric.labels.assert_called_once_with(
            asset="ETH", status="pending"
        )
        mock_labeled_created.inc.assert_called_once()

    @patch("app.shared.monitoring.metrics.transactions_validated_total")
    @patch("app.shared.monitoring.metrics.blockchain_confirmations")
    def test_record_transaction_validated(
        self, mock_confirmations_metric, mock_validated_metric
    ):
        """Test record_transaction_validated function"""
        mock_labeled_validated = Mock()
        mock_labeled_confirmations = Mock()
        mock_validated_metric.labels.return_value = mock_labeled_validated
        mock_confirmations_metric.labels.return_value = mock_labeled_confirmations

        record_transaction_validated(True, True, 6, "ETH")

        mock_validated_metric.labels.assert_called_once_with(
            is_valid="True", is_confirmed="True"
        )
        mock_labeled_validated.inc.assert_called_once()
        mock_confirmations_metric.labels.assert_called_once_with(asset="ETH")
        mock_labeled_confirmations.observe.assert_called_once_with(6)

    @patch("app.shared.monitoring.metrics.transactions_validated_total")
    def test_record_transaction_validated_without_confirmations(
        self, mock_validated_metric
    ):
        """Test record_transaction_validated without confirmations"""
        mock_labeled_validated = Mock()
        mock_validated_metric.labels.return_value = mock_labeled_validated

        record_transaction_validated(False, False)

        mock_validated_metric.labels.assert_called_once_with(
            is_valid="False", is_confirmed="False"
        )
        mock_labeled_validated.inc.assert_called_once()

    @patch("app.shared.monitoring.metrics.blockchain_operations_total")
    @patch("app.shared.monitoring.metrics.blockchain_operation_duration_seconds")
    def test_record_blockchain_operation(
        self, mock_duration_metric, mock_operations_metric
    ):
        """Test record_blockchain_operation function"""
        mock_labeled_operations = Mock()
        mock_labeled_duration = Mock()
        mock_operations_metric.labels.return_value = mock_labeled_operations
        mock_duration_metric.labels.return_value = mock_labeled_duration

        record_blockchain_operation("send_transaction", "success", 2.5)

        mock_operations_metric.labels.assert_called_once_with(
            operation="send_transaction", status="success"
        )
        mock_labeled_operations.inc.assert_called_once()
        mock_duration_metric.labels.assert_called_once_with(
            operation="send_transaction"
        )
        mock_labeled_duration.observe.assert_called_once_with(2.5)

    @patch("app.shared.monitoring.metrics.vault_operations_total")
    @patch("app.shared.monitoring.metrics.vault_operation_duration_seconds")
    def test_record_vault_operation(self, mock_duration_metric, mock_operations_metric):
        """Test record_vault_operation function"""
        mock_labeled_operations = Mock()
        mock_labeled_duration = Mock()
        mock_operations_metric.labels.return_value = mock_labeled_operations
        mock_duration_metric.labels.return_value = mock_labeled_duration

        record_vault_operation("store_key", "success", 0.5)

        mock_operations_metric.labels.assert_called_once_with(
            operation="store_key", status="success"
        )
        mock_labeled_operations.inc.assert_called_once()
        mock_duration_metric.labels.assert_called_once_with(operation="store_key")
        mock_labeled_duration.observe.assert_called_once_with(0.5)

    @patch("app.shared.monitoring.metrics.database_operations_total")
    @patch("app.shared.monitoring.metrics.database_operation_duration_seconds")
    def test_record_database_operation(
        self, mock_duration_metric, mock_operations_metric
    ):
        """Test record_database_operation function"""
        mock_labeled_operations = Mock()
        mock_labeled_duration = Mock()
        mock_operations_metric.labels.return_value = mock_labeled_operations
        mock_duration_metric.labels.return_value = mock_labeled_duration

        record_database_operation("insert", "transactions", "success", 0.1)

        mock_operations_metric.labels.assert_called_once_with(
            operation="insert", table="transactions", status="success"
        )
        mock_labeled_operations.inc.assert_called_once()
        mock_duration_metric.labels.assert_called_once_with(
            operation="insert", table="transactions"
        )
        mock_labeled_duration.observe.assert_called_once_with(0.1)

    @patch("app.shared.monitoring.metrics.wallets_created_total")
    def test_record_wallet_created(self, mock_wallets_metric):
        """Test record_wallet_created function"""
        record_wallet_created(5)

        mock_wallets_metric.inc.assert_called_once_with(5)

    @patch("app.shared.monitoring.metrics.wallets_created_total")
    def test_record_wallet_created_default(self, mock_wallets_metric):
        """Test record_wallet_created with default count"""
        record_wallet_created()

        mock_wallets_metric.inc.assert_called_once_with(1)

    @patch("app.shared.monitoring.metrics.wallet_operations_total")
    def test_record_wallet_operation(self, mock_operations_metric):
        """Test record_wallet_operation function"""
        mock_labeled_operations = Mock()
        mock_operations_metric.labels.return_value = mock_labeled_operations

        record_wallet_operation("create", "success")

        mock_operations_metric.labels.assert_called_once_with(
            operation="create", status="success"
        )
        mock_labeled_operations.inc.assert_called_once()

    @patch("app.shared.monitoring.metrics.errors_total")
    def test_record_error(self, mock_errors_metric):
        """Test record_error function"""
        mock_labeled_errors = Mock()
        mock_errors_metric.labels.return_value = mock_labeled_errors

        record_error("ValueError", "transaction_service")

        mock_errors_metric.labels.assert_called_once_with(
            error_type="ValueError", component="transaction_service"
        )
        mock_labeled_errors.inc.assert_called_once()

    @patch("app.shared.monitoring.metrics.app_info")
    def test_set_app_info(self, mock_app_info):
        """Test set_app_info function"""
        set_app_info("1.0.0", "production")

        mock_app_info.info.assert_called_once_with(
            {"version": "1.0.0", "environment": "production"}
        )


class TestMetricsContext:
    """Test MetricsContext context manager"""

    @patch("app.shared.monitoring.metrics.record_blockchain_operation")
    def test_metrics_context_blockchain_success(self, mock_record):
        """Test MetricsContext for blockchain operations success"""
        with MetricsContext("send_transaction", "blockchain"):
            time.sleep(0.01)  # Small delay

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0]
        assert call_args[0] == "send_transaction"
        assert call_args[1] == "success"
        assert call_args[2] > 0  # Duration should be positive

    @patch("app.shared.monitoring.metrics.record_blockchain_operation")
    @patch("app.shared.monitoring.metrics.record_error")
    def test_metrics_context_blockchain_error(
        self, mock_record_error, mock_record_blockchain
    ):
        """Test MetricsContext for blockchain operations with error"""
        with pytest.raises(ValueError, match="Test error"):
            with MetricsContext("send_transaction", "blockchain"):
                raise ValueError("Test error")

        mock_record_blockchain.assert_called_once()
        call_args = mock_record_blockchain.call_args[0]
        assert call_args[0] == "send_transaction"
        assert call_args[1] == "error"
        assert call_args[2] > 0

        mock_record_error.assert_called_once_with("ValueError", "blockchain")

    @patch("app.shared.monitoring.metrics.record_vault_operation")
    def test_metrics_context_vault_success(self, mock_record):
        """Test MetricsContext for vault operations success"""
        with MetricsContext("store_key", "vault"):
            pass

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0]
        assert call_args[0] == "store_key"
        assert call_args[1] == "success"
        assert call_args[2] >= 0

    @patch("app.shared.monitoring.metrics.record_database_operation")
    def test_metrics_context_database_success(self, mock_record):
        """Test MetricsContext for database operations success"""
        with MetricsContext("insert", "database"):
            pass

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0]
        assert call_args[0] == "insert"
        assert call_args[1] == "unknown"  # Default table name
        assert call_args[2] == "success"
        assert call_args[3] >= 0

    @patch("app.shared.monitoring.metrics.record_wallet_operation")
    def test_metrics_context_wallet_success(self, mock_record):
        """Test MetricsContext for wallet operations success"""
        with MetricsContext("create", "wallet"):
            pass

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0]
        assert call_args[0] == "create"
        assert call_args[1] == "success"

    def test_metrics_context_unknown_component(self):
        """Test MetricsContext with unknown component"""
        # Should not raise exception, just not record specific metrics
        with MetricsContext("test_operation", "unknown_component"):
            pass

    def test_metrics_context_timing(self):
        """Test MetricsContext timing functionality"""
        context = MetricsContext("test", "blockchain")

        with context:
            start_time = context.start_time
            time.sleep(0.01)

        assert start_time is not None
        assert start_time > 0
