# Forensiq AI — Intelligent Document Integrity System

**Real-time anomaly detection for underwriting.** Forensiq AI is an intelligent
verification layer that sits inside the loan-underwriting workflow and answers a
question that point fraud checks cannot: *is the entire legal, financial and
ownership story behind this application genuine, consistent and trustworthy
across independent sources?*

Instead of validating each document in isolation, Forensiq AI performs forensic
analysis on uploaded documents **and** cross-verifies the extracted information
against trusted registries, transaction behaviour and satellite imagery — then
produces an **explainable** underwriting decision with supporting evidence and
risk reasoning, in real time.

---

## Why this is different

Most existing systems stop at OCR extraction or a single fraud score. Forensiq
AI detects **contradictions across sources** that are nearly impossible to catch
manually, for example:

- A title deed claims a **residential building**, but satellite imagery shows
  **vacant land** and the land registry lists a **different owner**.
- A financial statement declares **high revenue**, but the actual transaction
  activity (and tax records) **do not support that income**.
- A "final" PDF statement was **silently edited after issuance**, or an image
  document had a **value overwritten** after it was scanned.

Every alert is **explainable**: it traces back to specific findings, confidence
scores and visual evidence — not an opaque number.

---

## The six modules

| Module | What it actually does | Techniques |
|---|---|---|
| **Document Forensics** | Detects tampering, edited values, pasted content and metadata manipulation in images & PDFs | Noise-floor anomaly detection, Error-Level Analysis (ELA), EXIF/metadata fingerprinting, PDF incremental-update & producer analysis, Tesseract OCR + field extraction |
| **Financial Integrity** | Flags fabricated/edited statements and income inconsistencies | Benford's Law (χ² goodness-of-fit), Isolation Forest anomaly detection, declared-vs-observed income reconciliation, synthetic-pattern detection (round numbers, repeats, regular timing) |
| **Cross-Source Verification** | Reconciles the application narrative against trusted registries and builds a contradiction knowledge graph | Identity/PAN matching, ownership reconciliation, encumbrance/litigation checks, value & area cross-checks |
| **GIS / Satellite Validation** | Confirms the collateral physically exists and matches the claimed land use | Remote-sensing land-use comparison (built-up ratio, NDVI, structure count), change detection, offline data-driven land-use render |
| **Explainable Risk Intelligence** | Fuses all module scores into one defensible decision with natural-language reasoning | Weighted, saturating risk model with critical-finding floor + contradiction summary |
| **Automated Risk Escalation** | Clears, reviews or auto-escalates and opens investigation cases | Policy engine, case management, full audit trail |

---

## Tech stack

- **Backend** — Python 3.13, FastAPI, SQLAlchemy (SQLite), WebSockets, OpenCV,
  scikit-image, scikit-learn, NumPy/SciPy, Pillow, pikepdf/pypdf, Tesseract OCR.
- **Frontend** — React + TypeScript, Vite, Tailwind CSS, Recharts, system fonts,
  Lucide icons (all bundled — no CDNs).
- **Real-time** — WebSocket streaming of pipeline stages and live detection
  signals.

### Offline by design

Forensiq AI runs **100% offline** — no external LLMs, no cloud APIs, no CDN
fonts and no live map tiles. All ML/forensics run locally; the GIS module uses a
data-driven satellite land-use render instead of online imagery. This satisfies
the requirement that the solution execute without any internet access.

---

## Quick start

**Prerequisites:** Python 3.13, Node 18+, and Tesseract (`brew install tesseract`).
Only needed once for setup (installing packages); the app itself runs offline.

```bash
./start.sh
```

This creates the Python environment, installs dependencies, seeds demo data,
and launches both servers:

- Frontend → **http://localhost:5173**
- API docs → **http://127.0.0.1:8000/docs**

### Manual run

```bash
# Backend
cd backend
python3.13 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m scripts.seed          # generate samples + demo data
./.venv/bin/python -m uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install && npm run dev
```

---

## Demo walkthrough

The seed creates five realistic scenarios (the last is left **un-analyzed** so
you can run it live from the UI):

| Application | Scenario | Expected outcome |
|---|---|---|
| Ramesh Kumar Sharma | Clean application, consistent across all sources | **LOW** → auto-cleared |
| Suresh Sharma | Forged title (overwritten value) + ownership theft + fabricated statement | **CRITICAL** → escalated |
| Anita Desai | Tampered income certificate + Benford violation + income overstatement | **HIGH** → manual review |
| Mohammed Irfan Khan | "Residential" property that satellite shows as **vacant land** + active litigation | **CRITICAL** → escalated |
| Lakshmi Narayan Reddy | Encumbered agricultural collateral *(left for a live demo run)* | run it live |

**Suggested live demo:** open the un-analyzed application (or create a new one),
upload `backend/app/data/samples/*`, click **Run Forensiq Analysis**, and watch
the pipeline stream stages and findings in real time, ending in an explainable
report with forensic heatmaps, a Benford chart, the contradiction knowledge
graph, and a satellite view.

---

## How the forensics actually work (no smoke and mirrors)

- **Noise-floor anomaly** — genuine scans carry spatially-uniform sensor noise.
  A region pasted/typed in an editor has a collapsed noise floor; we locate it
  with a sliding-window noise-std map and connected-component analysis, and draw
  the bounding box on the evidence overlay.
- **Benford's Law** — first digits of organic financial figures follow a
  logarithmic distribution; fabricated statements fail a χ² test (critical
  15.51, 8 dof).
- **Isolation Forest** — unsupervised outlier detection over transaction
  features surfaces injected/anomalous transactions.
- **PDF structural forensics** — counts `%%EOF`/xref sections to detect
  incremental updates (edits after a "final"/signed PDF) and inspects the
  producer/creator metadata.

The mock registries (`backend/app/data/registries/`) stand in for live land,
identity and GIS APIs — the verification logic is exactly what would run against
the real sources.

### Resilience to the "scanned hard copy" problem

A printed-then-rescanned document can erase digital tamper signatures (the whole
page picks up uniform scan noise). Forensiq AI is deliberately **multi-layered**
so it does not depend on document forensics alone: even when a forgery survives
the pixel-level checks, the **cross-source verification, financial-integrity and
GIS modules** still expose the fraud — because a forger cannot also rewrite the
land registry, the tax record, the transaction history and the satellite imagery
to stay mutually consistent. Document forensics narrows it down; cross-source
contradiction is what makes the verdict robust.

---

## Project structure

```
backend/
  app/
    api/            REST + WebSocket routes
    core/           configuration & tunable thresholds
    db/             SQLAlchemy models
    services/
      forensics/    image & PDF forensics + OCR
      financial/    Benford, Isolation Forest, consistency
      verification/ registries + contradiction engine + knowledge graph
      gis/          satellite land-use validation
      risk/         explainable aggregation
      escalation/   policy + case management
      pipeline/     orchestrator + WebSocket manager
    data/           mock registries & generated samples
  scripts/          sample generator + seeder
frontend/
  src/
    components/     UI + charts + map + knowledge graph
    pages/          dashboard, applications, detail, new (live), cases
    lib/            API client, websocket, formatting
```

---

## Configuration

All weights and thresholds are centralised and environment-overridable in
`backend/app/core/config.py` (prefix `FORENSIQ_`), e.g. module weights, the
approve/review/escalate risk thresholds, and each detector's sensitivity.
