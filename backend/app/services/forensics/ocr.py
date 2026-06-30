"""Text extraction (Tesseract OCR + native PDF text) and field parsing.

Extracts the underwriting-relevant fields (PAN, amounts, owner, survey/plot
numbers, dates, area) that the cross-source verification engine later reconciles
against registry and financial data.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
AADHAAR_RE = re.compile(r"\b(\d{4}\s?\d{4}\s?\d{4})\b")
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
SURVEY_RE = re.compile(
    r"(?:survey\s*(?:number|no\.?)?|s\.?\s*no\.?|plot\s*(?:no\.?)?|khasra|gut)\s*[:.#]?\s*"
    r"([0-9]{1,4}[a-z]?(?:/[0-9a-z]+)?)",
    re.IGNORECASE,
)
AREA_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(sq\.?\s*ft|sqft|sq\.?\s*m|sq\.?\s*yd|acre|cent|guntha)", re.IGNORECASE)
DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
OWNER_RE = re.compile(
    r"(?:owner\s*name|owner|in favou?r of|vendor|seller|mortgagor)\s*[:\-]?\s*"
    r"([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){1,3})"
)
GROSS_SALARY_RE = re.compile(
    r"(?:gross\s*(?:annual\s*)?(?:salary|pay|earnings|income)|total\s*(?:earnings|pay))\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
NET_SALARY_RE = re.compile(
    r"(?:net\s*(?:salary|pay|take\s*home)|take\s*home\s*pay)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
MONTHLY_SALARY_RE = re.compile(
    r"(?:monthly\s*(?:salary|pay|income)|salary\s*per\s*month)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)


def extract_text(path: Path, mime: str) -> str:
    if mime == "application/pdf" or path.suffix.lower() == ".pdf":
        return _pdf_text(path)
    return _image_text(path)


def _pdf_text(path: Path) -> str:
    text = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001
        text = ""
    return text.strip()


def _image_text(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception:  # noqa: BLE001
        return ""


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return 0.0


def extract_fields(text: str) -> dict[str, Any]:
    if not text:
        return {}
    fields: dict[str, Any] = {}

    if m := PAN_RE.search(text):
        fields["pan"] = m.group(1)
    if m := AADHAAR_RE.search(text):
        fields["aadhaar_masked"] = "XXXX XXXX " + m.group(1)[-4:]
    if m := SURVEY_RE.search(text):
        fields["survey_number"] = m.group(1).strip()
    if m := OWNER_RE.search(text):
        fields["owner_name"] = re.sub(r"\s+", " ", m.group(1)).strip()

    amounts = [_to_float(a) for a in AMOUNT_RE.findall(text)]
    amounts = [a for a in amounts if a > 0]
    if amounts:
        fields["amounts"] = sorted(amounts, reverse=True)[:10]
        fields["max_amount"] = max(amounts)

    if areas := AREA_RE.findall(text):
        value, unit = areas[0]
        fields["area_value"] = _to_float(value)
        fields["area_unit"] = re.sub(r"\s+|\.", "", unit).lower()

    if dates := DATE_RE.findall(text):
        fields["dates"] = dates[:6]

    if m := GROSS_SALARY_RE.search(text):
        fields["gross_salary"] = _to_float(m.group(1))
    if m := NET_SALARY_RE.search(text):
        fields["net_salary"] = _to_float(m.group(1))
    if m := MONTHLY_SALARY_RE.search(text):
        fields["monthly_salary"] = _to_float(m.group(1))

    fields["text_length"] = len(text)
    return fields
