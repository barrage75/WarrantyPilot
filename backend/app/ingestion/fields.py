"""Canonical invoice fact names shared by ingestion adapters."""

SUPPLIER_NAME = "supplier_name"
SUPPLIER_ADDRESS = "supplier_address"
INVOICE_NUMBER = "invoice_number"
INVOICE_DATE = "invoice_date"
CUSTOMER_NAME = "customer_name"
TOTAL_TTC = "total_ttc"
WARRANTY_EXTENSION_MENTIONED = "warranty_extension_mentioned"
WARRANTY_DURATION_MONTHS = "warranty_duration_months"
MODEL = "model"
SKU = "sku"
SERIAL = "serial"
QUANTITY = "quantity"
UNIT_PRICE_HT = "unit_price_ht"
HEADER_FIELDS = (
    SUPPLIER_NAME,
    SUPPLIER_ADDRESS,
    INVOICE_NUMBER,
    INVOICE_DATE,
    CUSTOMER_NAME,
    TOTAL_TTC,
    WARRANTY_EXTENSION_MENTIONED,
    WARRANTY_DURATION_MONTHS,
)
LINE_FIELDS = (MODEL, SKU, SERIAL, QUANTITY, UNIT_PRICE_HT)


def line_field(index: int, name: str) -> str:
    return f"lines[{index}].{name}"
