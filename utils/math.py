import math


def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))

def get_percentile_item(lst, percentile: float):
    """
    Selects the item at the given percentile from a descending-sorted list.

    Args:
        lst: A list of items sorted in descending order (best item first).
        percentile: A float between 0.0 (top) and 1.0 (bottom), e.g., 0.2 for top 20%.

    Returns:
        The item at the given percentile index.
    """
    if not lst:
        raise ValueError("List is empty")

    percentile = max(0.0, min(1.0, percentile))  # Clamp between 0 and 1

    index = int(percentile * (len(lst) - 1))
    # print("percentile, index")
    # print(percentile, index)

    return lst[index]

