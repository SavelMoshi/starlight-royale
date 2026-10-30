from decimal import Decimal, InvalidOperation
import re

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
AMOUNT_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")


def amount(value: str) -> Decimal:
    if not AMOUNT_PATTERN.fullmatch(value.strip()):
        raise ValueError("Enter a positive amount with at most two decimal places.")
    try:
        result = Decimal(value.strip()).quantize(CENT)
    except InvalidOperation as exc:
        raise ValueError("Enter a valid amount.") from exc
    if result <= ZERO:
        raise ValueError("Amount must be greater than zero.")
    return result


def money(value: Decimal, symbol: str = "$") -> str:
    return f"-{symbol}{abs(value):,.2f}" if value < ZERO else f"{symbol}{value:,.2f}"
