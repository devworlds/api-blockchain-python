from decimal import Decimal

import pytest

from app.shared.utils.validators import eth_to_wei, validate_eth_value, wei_to_eth


class TestEthToWei:
    """Test ETH to Wei conversion"""

    def test_eth_to_wei_valid_string(self):
        """Test conversion with string input"""
        result = eth_to_wei("1.0")
        assert result == 1000000000000000000

    def test_eth_to_wei_valid_float(self):
        """Test conversion with float input"""
        result = eth_to_wei(0.1)
        # Use approximate comparison due to floating point precision
        assert abs(result - 100000000000000000) < 10

    def test_eth_to_wei_valid_decimal(self):
        """Test conversion with Decimal input"""
        result = eth_to_wei(Decimal("2.5"))
        assert result == 2500000000000000000

    def test_eth_to_wei_small_value(self):
        """Test conversion with very small value"""
        result = eth_to_wei("0.000000000000000001")  # 1 wei
        assert result == 1

    def test_eth_to_wei_large_float_scientific_notation(self):
        """Test conversion with large float in scientific notation"""
        result = eth_to_wei(1e-6)  # 0.000001 ETH
        assert result == 1000000000000

    def test_eth_to_wei_zero_value_error(self):
        """Test that zero value raises ValueError"""
        with pytest.raises(ValueError, match="Value must be positive"):
            eth_to_wei("0")

    def test_eth_to_wei_negative_value_error(self):
        """Test that negative value raises ValueError"""
        with pytest.raises(ValueError, match="Value must be positive"):
            eth_to_wei("-1.0")

    def test_eth_to_wei_too_large_value_error(self):
        """Test that value exceeding max ETH supply raises ValueError"""
        with pytest.raises(ValueError, match="Value too large"):
            eth_to_wei("150000000")  # More than max ETH supply

    def test_eth_to_wei_invalid_string_error(self):
        """Test that invalid string raises ValueError"""
        with pytest.raises(ValueError, match="Error converting ETH to Wei"):
            eth_to_wei("invalid")

    def test_eth_to_wei_none_value_error(self):
        """Test that None value raises ValueError"""
        with pytest.raises(ValueError, match="Error converting ETH to Wei"):
            eth_to_wei(None)


class TestWeiToEth:
    """Test Wei to ETH conversion"""

    def test_wei_to_eth_valid_int(self):
        """Test conversion with int input"""
        result = wei_to_eth(1000000000000000000)
        assert result == Decimal("1")

    def test_wei_to_eth_valid_string(self):
        """Test conversion with string input"""
        result = wei_to_eth("500000000000000000")
        assert result == Decimal("0.5")

    def test_wei_to_eth_zero_value(self):
        """Test conversion with zero value"""
        result = wei_to_eth(0)
        assert result == Decimal("0")

    def test_wei_to_eth_one_wei(self):
        """Test conversion with 1 wei"""
        result = wei_to_eth(1)
        assert result == Decimal("0.000000000000000001")

    def test_wei_to_eth_large_value(self):
        """Test conversion with large wei value"""
        result = wei_to_eth("100000000000000000000")  # 100 ETH
        assert result == Decimal("100")

    def test_wei_to_eth_negative_value_error(self):
        """Test that negative wei value raises ValueError"""
        with pytest.raises(ValueError, match="Wei value must be non-negative"):
            wei_to_eth(-1)

    def test_wei_to_eth_invalid_string_error(self):
        """Test that invalid string raises ValueError"""
        with pytest.raises(ValueError, match="Error converting Wei to ETH"):
            wei_to_eth("invalid")

    def test_wei_to_eth_none_value_error(self):
        """Test that None value raises ValueError"""
        with pytest.raises(ValueError, match="Error converting Wei to ETH"):
            wei_to_eth(None)


class TestValidateEthValue:
    """Test ETH value validation"""

    def test_validate_eth_value_valid_string(self):
        """Test validation with valid string"""
        assert validate_eth_value("1.0") is True
        assert validate_eth_value("0.1") is True
        assert validate_eth_value("100") is True

    def test_validate_eth_value_valid_float(self):
        """Test validation with valid float"""
        assert validate_eth_value(1.0) is True
        assert validate_eth_value(0.001) is True

    def test_validate_eth_value_zero_invalid(self):
        """Test that zero value is invalid"""
        assert validate_eth_value("0") is False
        assert validate_eth_value(0.0) is False

    def test_validate_eth_value_negative_invalid(self):
        """Test that negative value is invalid"""
        assert validate_eth_value("-1.0") is False
        assert validate_eth_value(-0.1) is False

    def test_validate_eth_value_invalid_string(self):
        """Test that invalid string is invalid"""
        assert validate_eth_value("invalid") is False
        assert validate_eth_value("") is False

    def test_validate_eth_value_none_invalid(self):
        """Test that None is invalid"""
        assert validate_eth_value(None) is False

    def test_validate_eth_value_scientific_notation(self):
        """Test validation with scientific notation"""
        assert validate_eth_value("1e-6") is True
        assert validate_eth_value("1E+2") is True
