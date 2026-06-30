"""Generate realistic sample documents for demos.

Produces genuinely analyzable artifacts:
* Property / income document images — a *clean* version and a *tampered* version
  where a value is re-pasted at a different compression level (this really does
  trigger Error Level Analysis) plus a copy-moved stamp (triggers ORB
  copy-move detection).
* Bank-statement CSVs — a *genuine* statement (varied, Benford-consistent,
  irregular timing) and a *fabricated* one (round numbers, repeated amounts,
  regular timing → Benford violation + synthetic-pattern + income overstatement).
"""
from __future__ import annotations

import csv
import io
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "samples"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _base_document(title: str, rows: list[tuple[str, str]], stamp: bool = True) -> Image.Image:
    W, H = 1000, 1300
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Header band.
    d.rectangle([0, 0, W, 120], fill=(13, 59, 102))
    d.text((40, 35), title, font=_font(36), fill="white")
    d.text((40, 82), "Government of India  •  Certified Record", font=_font(18), fill=(200, 220, 240))

    d.rectangle([30, 150, W - 30, H - 60], outline=(180, 180, 180), width=2)

    y = 200
    for label, value in rows:
        d.text((60, y), label, font=_font(22), fill=(90, 90, 90))
        d.text((460, y), value, font=_font(24), fill=(20, 20, 20))
        y += 70

    # Official stamp (circular) — reused for copy-move demo.
    if stamp:
        cx, cy, r = 780, 1050, 90
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 30, 30), width=4)
        d.ellipse([cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14], outline=(150, 30, 30), width=2)
        d.text((cx - 60, cy - 14), "VERIFIED", font=_font(22), fill=(150, 30, 30))
    d.text((60, 1180), "Signature: ____________________", font=_font(20), fill=(40, 40, 40))
    return img


def _save_jpeg(img: Image.Image, path: Path, quality: int = 95) -> None:
    img.convert("RGB").save(path, "JPEG", quality=quality)


def add_scan_noise(img: Image.Image, sigma: float = 7.0, seed: int = 3) -> Image.Image:
    """Simulate a real scan/capture: uniform sensor noise + JPEG round-trip.

    Genuine documents acquired by a scanner/camera carry spatially-uniform
    noise. A forger who pastes fresh content in an editor leaves a region
    *without* this noise — which the noise-floor forensic detector then flags.
    """
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    noise = np.random.RandomState(seed).normal(0.0, sigma, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    out = Image.fromarray(noisy)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=88)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def make_property_document(name: str, owner: str, survey: str, value: str,
                           area: str, ptype: str) -> Image.Image:
    rows = [
        ("Document Type", "Sale Deed / Title"),
        ("Owner Name", owner),
        ("Survey Number", survey),
        ("Property Type", ptype),
        ("Area", area),
        ("Declared Value", value),
        ("Registration Date", "12/03/2019"),
        ("Sub-Registrar", "Bengaluru Urban"),
    ]
    return _base_document("LAND TITLE CERTIFICATE", rows)


def make_income_document(name: str, employer: str, gross: str, net: str) -> Image.Image:
    rows = [
        ("Employee Name", name),
        ("Employer", employer),
        ("Designation", "Senior Manager"),
        ("Gross Annual Income", gross),
        ("Net Annual Income", net),
        ("PF Number", "KA/BNG/0099123/456"),
        ("Issued On", "05/04/2026"),
    ]
    return _base_document("ANNUAL INCOME CERTIFICATE", rows, stamp=True)


def tamper_value(img: Image.Image, new_value: str, position=(460, 480)) -> Image.Image:
    """Edit a value on an already-scanned (noisy) document.

    The fraudulent value is pasted as crisp, noise-free content on a clean white
    box — leaving a region whose noise floor differs sharply from the genuine
    scanned background. This is the forensic fingerprint of a real edited
    document and is reliably caught by the noise-floor anomaly detector.
    """
    flat = img.convert("RGB").copy()
    d = ImageDraw.Draw(flat)
    d.rectangle([position[0] - 6, position[1] - 6, position[0] + 340, position[1] + 40], fill=(255, 255, 255))
    d.text(position, new_value, font=_font(24), fill=(15, 15, 15))
    return flat


def copy_move_stamp(img: Image.Image) -> Image.Image:
    """Clone the official stamp to a second location (copy-move forgery)."""
    flat = img.convert("RGB").copy()
    region = flat.crop((690, 960, 870, 1140))
    flat.paste(region, (120, 300))
    return flat


# ── Transaction generators ──────────────────────────────────────────
def _write_csv(path: Path, txns: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Date", "Description", "Amount", "Balance"])
        bal = 50000.0
        for t in txns:
            bal += t["amount"]
            w.writerow([t["date"], t["description"], f"{t['amount']:.2f}", f"{bal:.2f}"])


def genuine_statement(path: Path, monthly_salary: float = 88000.0) -> float:
    """Realistic statement: log-distributed amounts (naturally Benford-conforming),
    irregular timing and amounts that span several orders of magnitude — exactly
    how genuine account activity behaves."""
    import math

    rng = random.Random(7)
    start = datetime(2025, 10, 1)
    txns: list[dict] = []
    total_in = 0.0
    merchants = ["UPI/Swiggy", "UPI/Amazon", "NEFT/Rent", "ATM Withdrawal", "UPI/Electricity",
                 "POS/BigBazaar", "UPI/Petrol", "UPI/Pharmacy", "Card/Restaurant", "UPI/Mobile"]

    def log_amount(lo: float, hi: float) -> float:
        # Sampling uniformly in log-space yields a Benford-conforming first-digit
        # distribution, like real-world spending.
        return round(math.exp(rng.uniform(math.log(lo), math.log(hi))), 2)

    for month in range(6):
        sal_day = start + timedelta(days=month * 30 + rng.randint(0, 3))
        salary = round(monthly_salary * rng.uniform(0.94, 1.08), 2)
        txns.append({"date": sal_day.strftime("%Y-%m-%d"), "description": "SALARY CREDIT", "amount": salary})
        total_in += salary
        for _ in range(rng.randint(16, 24)):
            day = start + timedelta(days=month * 30 + rng.randint(0, 29))
            amt = -log_amount(60, 60000)
            txns.append({"date": day.strftime("%Y-%m-%d"), "description": rng.choice(merchants), "amount": amt})
        if rng.random() < 0.5:
            day = start + timedelta(days=month * 30 + rng.randint(0, 29))
            extra = log_amount(2000, 40000)
            txns.append({"date": day.strftime("%Y-%m-%d"), "description": "UPI/Freelance", "amount": extra})
            total_in += extra
    txns.sort(key=lambda t: t["date"])
    _write_csv(path, txns)
    return total_in / 6 * 12  # implied annual inflow


def fabricated_statement(path: Path) -> float:
    """Fabricated statement: round numbers, repeats, regular timing → many flags."""
    rng = random.Random(11)
    start = datetime(2025, 10, 1)
    txns: list[dict] = []
    total_in = 0.0
    for month in range(6):
        day = start + timedelta(days=month * 30)  # perfectly regular
        salary = 50000.0  # identical every month
        txns.append({"date": day.strftime("%Y-%m-%d"), "description": "SALARY CREDIT", "amount": salary})
        total_in += salary
        for k in range(8):
            d2 = start + timedelta(days=month * 30 + k * 3)  # uniform spacing
            amt = -float(rng.choice([5000, 10000, 20000, 50000, 100000]))  # round + repeated
            txns.append({"date": d2.strftime("%Y-%m-%d"), "description": "CASH PAYMENT", "amount": amt})
        # occasional big round credit
        txns.append({"date": day.strftime("%Y-%m-%d"), "description": "DEPOSIT", "amount": 100000.0})
        total_in += 100000.0
    txns.sort(key=lambda t: t["date"])
    _write_csv(path, txns)
    return total_in / 6 * 12


def generate_all() -> dict[str, Path]:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    # ── Scenario 1: clean (genuine scan) ─────────────────────────
    clean_prop = add_scan_noise(make_property_document(
        "Ramesh Kumar Sharma", "Ramesh Kumar Sharma", "142/3",
        "Rs 45,00,000", "1200 sqft", "Residential"), seed=1)
    p = SAMPLE_DIR / "clean_title_142-3.jpg"; _save_jpeg(clean_prop, p); out["clean_title"] = p

    # ── Scenario 2: tampered value + copy-moved seal ────────────
    base_prop = add_scan_noise(make_property_document(
        "Suresh Sharma", "Suresh Sharma", "142/3",
        "Rs 45,00,000", "1200 sqft", "Residential"), seed=2)
    tampered = tamper_value(base_prop, "Rs 95,00,000", position=(460, 550))  # inflated value row
    tampered = copy_move_stamp(tampered)
    p = SAMPLE_DIR / "tampered_title_142-3.jpg"; _save_jpeg(tampered, p, quality=92); out["tampered_title"] = p

    # ── Scenario 3: tampered income certificate ─────────────────
    inc = add_scan_noise(make_income_document(
        "Anita Desai", "TechCorp Pvt Ltd", "Rs 42,00,000", "Rs 31,00,000"), seed=4)
    inc_tampered = tamper_value(inc, "Rs 1,20,00,000", position=(460, 410))  # gross income row
    p = SAMPLE_DIR / "tampered_income_anita.jpg"; _save_jpeg(inc_tampered, p, quality=92); out["tampered_income"] = p

    # ── Scenario 4 & 5 docs (genuine scans) ─────────────────────
    prop_gis = add_scan_noise(make_property_document(
        "Mohammed Irfan Khan", "Mohammed Irfan Khan", "210/5",
        "Rs 68,00,000", "1800 sqft", "Residential"), seed=5)
    p = SAMPLE_DIR / "title_210-5_residential.jpg"; _save_jpeg(prop_gis, p); out["gis_title"] = p

    prop_agri = add_scan_noise(make_property_document(
        "Lakshmi Narayan Reddy", "Lakshmi Narayan Reddy", "88/1",
        "Rs 32,00,000", "2.5 acre", "Agricultural"), seed=6)
    p = SAMPLE_DIR / "title_88-1_agri.jpg"; _save_jpeg(prop_agri, p); out["agri_title"] = p

    # ── Statements ──────────────────────────────────────────────
    p = SAMPLE_DIR / "statement_genuine.csv"; genuine_statement(p); out["stmt_genuine"] = p
    p = SAMPLE_DIR / "statement_fabricated.csv"; fabricated_statement(p); out["stmt_fabricated"] = p

    return out


if __name__ == "__main__":
    files = generate_all()
    for k, v in files.items():
        print(f"{k:16s} -> {v}")
