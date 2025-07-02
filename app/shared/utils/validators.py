from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Union

# Set precision high enough to handle large numbers
getcontext().prec = 50


def eth_to_wei(eth_value: Union[str, float, Decimal]) -> int:
    """
    Convert ETH value to Wei safely using Decimal to avoid precision issues.

    Args:
        eth_value: Value in ETH (string, float, or Decimal)

    Returns:
        int: Value in Wei

    Raises:
        ValueError: If value is invalid
    """
    try:
        # Handle scientific notation by converting float to string with proper formatting
        if isinstance(eth_value, float):
            # Format float to avoid scientific notation
            eth_str = f"{eth_value:.18f}".rstrip("0").rstrip(".")
        else:
            eth_str = str(eth_value)

        eth_decimal = Decimal(eth_str)

        if eth_decimal <= 0:
            raise ValueError("Value must be positive")

        # Check if value is too large (more than total ETH supply)
        max_eth = Decimal("120000000")  # Approximate max ETH supply
        if eth_decimal > max_eth:
            raise ValueError(
                f"Value too large: {eth_decimal} ETH exceeds maximum supply"
            )

        wei_decimal = eth_decimal * Decimal("1000000000000000000")

        # Use to_integral_value instead of quantize for large numbers
        wei_value = int(wei_decimal.to_integral_value(rounding=ROUND_DOWN))

        return wei_value

    except (ValueError, TypeError, ArithmeticError) as e:
        raise ValueError(f"Error converting ETH to Wei: {e}")


def wei_to_eth(wei_value: Union[str, int]) -> Decimal:
    """
    Convert Wei value to ETH safely using Decimal.

    Args:
        wei_value: Value in Wei

    Returns:
        Decimal: Value in ETH

    Raises:
        ValueError: If value is invalid
    """
    try:
        wei_decimal = Decimal(str(wei_value))

        if wei_decimal < 0:
            raise ValueError("Wei value must be non-negative")

        eth_decimal = wei_decimal / Decimal("1000000000000000000")

        return eth_decimal

    except (ValueError, TypeError, ArithmeticError) as e:
        raise ValueError(f"Error converting Wei to ETH: {e}")


def validate_eth_value(eth_value: Union[str, float]) -> bool:
    """
    Validate if an ETH value is valid and positive.

    Args:
        eth_value: ETH value to validate

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        eth_decimal = Decimal(str(eth_value))
        return eth_decimal > 0
    except (ValueError, TypeError, ArithmeticError):
        return False
