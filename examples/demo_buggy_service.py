"""Small intentionally buggy service for a GitAssign demo.

Copy this file into a separate test repository. Create one GitHub issue per
BUG marker, then create/merge fixes from different contributors. GitAssign can
ingest those issues and closed fixes as historical evidence.
"""

from dataclasses import dataclass


@dataclass
class Order:
    item: str
    unit_price: float
    quantity: int
    tax_rate: float = 0.18


def calculate_total(order: Order) -> float:
    """Return the final order total."""
    subtotal = order.unit_price * order.quantity

    # BUG-1: tax is calculated from the unit price instead of the subtotal.
    tax = order.unit_price * order.tax_rate
    return round(subtotal + tax, 2)


def find_customer(customers: list[dict], email: str) -> dict | None:
    """Find a customer by email address."""
    # BUG-2: email addresses should be compared case-insensitively.
    for customer in customers:
        if customer.get("email") == email:
            return customer
    return None


def paginate(items: list[str], page: int, page_size: int = 3) -> list[str]:
    """Return one 1-based page of items."""
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive")

    # BUG-3: this treats page as zero-based, so page 1 skips the first page.
    start = page * page_size
    return items[start:start + page_size]


def demo() -> None:
    order = Order("keyboard", 100.0, 2)
    customers = [{"id": 7, "email": "owner@example.com"}]
    items = ["A", "B", "C", "D", "E", "F"]

    print("total:", calculate_total(order), "(expected 236.0)")
    print("customer:", find_customer(customers, "OWNER@example.com"), "(expected customer 7)")
    print("page 1:", paginate(items, page=1), "(expected ['A', 'B', 'C'])")


if __name__ == "__main__":
    demo()
