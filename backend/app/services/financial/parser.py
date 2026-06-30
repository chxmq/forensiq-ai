"""Parse bank-statement CSVs into a normalised transaction list.

Tolerant to common column-naming variations (date/txn date, amount vs
debit/credit, description/narration). Returns a list of
``{date, description, amount, balance}`` dicts where credits are positive and
debits negative.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

DATE_KEYS = ("date", "txn date", "transaction date", "value date", "posting date")
DESC_KEYS = ("description", "narration", "particulars", "details", "remarks")
AMOUNT_KEYS = ("amount", "amt", "transaction amount")
DEBIT_KEYS = ("debit", "withdrawal", "dr", "withdrawal amt")
CREDIT_KEYS = ("credit", "deposit", "cr", "deposit amt")
BALANCE_KEYS = ("balance", "closing balance", "running balance")


def _pick(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    lower = {k.lower().strip(): v for k, v in row.items() if k}
    for k in keys:
        if k in lower and str(lower[k]).strip():
            return str(lower[k]).strip()
    return None


def _num(value: str | None) -> float:
    if not value:
        return 0.0
    cleaned = value.replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
    cleaned = cleaned.replace("(", "-").replace(")", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_csv_bytes(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    txns: list[dict[str, Any]] = []
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue
        amount_raw = _pick(row, AMOUNT_KEYS)
        if amount_raw is not None:
            amount = _num(amount_raw)
        else:
            credit = _num(_pick(row, CREDIT_KEYS))
            debit = _num(_pick(row, DEBIT_KEYS))
            amount = credit - debit
        txns.append({
            "date": _pick(row, DATE_KEYS),
            "description": _pick(row, DESC_KEYS) or "",
            "amount": amount,
            "balance": _num(_pick(row, BALANCE_KEYS)),
        })
    return [t for t in txns if t["amount"] != 0 or t["date"]]


def parse_csv_file(path: Path) -> list[dict[str, Any]]:
    return parse_csv_bytes(path.read_bytes())
