_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def r2(value):
    """Round to 2 decimals the way people expect (half away from zero)."""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def inr(value):
    """Format a number with Indian digit grouping: 12,34,567.89"""
    value = r2(value or 0)
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


def qty_fmt(value):
    value = float(value or 0)
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _two_digits(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + " " + _ONES[n % 10]).strip()


def _three_digits(n):
    hundred, rest = divmod(n, 100)
    parts = []
    if hundred:
        parts.append(_ONES[hundred] + " Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts)


def number_to_words(n):
    """Integer to words using the Indian system (lakh, crore)."""
    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(number_to_words(crore) + " Crore")
    if lakh:
        parts.append(_two_digits(lakh) + " Lakh")
    if thousand:
        parts.append(_two_digits(thousand) + " Thousand")
    if n:
        parts.append(_three_digits(n))
    return " ".join(parts)


def amount_in_words(amount):
    amount = r2(amount)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    words = "Rupees " + number_to_words(rupees)
    if paise:
        words += " and " + _two_digits(paise) + " Paise"
    return words + " Only"
