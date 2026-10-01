def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price.

    Args:
        price: Original price (must be non-negative)
        discount_percent: Discount percentage (0-100)

    Returns:
        Discounted price

    Raises:
        ValueError: If price or discount is negative, or discount > 100
    """
    if price < 0 or discount_percent < 0:
        raise ValueError("Price and discount must be non-negative")
    if discount_percent > 100:
        raise ValueError("Discount cannot exceed 100%")
    return price * (1 - discount_percent / 100)


def find_max(numbers: list[int]) -> int:
    """Find the maximum value in a list.

    Args:
        numbers: List of integers

    Returns:
        Maximum value

    Raises:
        ValueError: If list is empty
    """
    if not numbers:
        raise ValueError("Cannot find max of empty list")
    return max(numbers)
