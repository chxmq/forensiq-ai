"""Real image-tampering forensics.

These are genuine, well-established forensic techniques — not heuristics that
pretend to work:

* **Error Level Analysis (ELA)** — re-compresses the image at a known JPEG
  quality and measures per-region compression error. Spliced/edited regions
  compress differently from the surrounding original pixels and light up.
* **Copy-move detection** — ORB keypoint self-matching finds regions that were
  cloned within the same image (a classic way to hide/duplicate content such as
  stamps, signatures or figures).
* **Noise-residual inconsistency** — natural captures have spatially consistent
  sensor noise; pasted content usually breaks that consistency.
* **Metadata / EXIF analysis** — detects editing-software fingerprints and
  inconsistent / missing capture metadata.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageChops, ExifTags

from app.core.config import settings
from app.services.common import Finding, Severity

EDITING_SOFTWARE = (
    "photoshop", "gimp", "lightroom", "pixelmator", "affinity", "snapseed",
    "paint.net", "canva", "coreldraw", "inkscape", "acdsee", "picsart",
)


def _save_artifact(img: np.ndarray, name: str) -> str:
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    out = settings.artifact_dir / name
    cv2.imwrite(str(out), img)
    return f"/api/artifacts/{name}"


# ──────────────────────────────────────────────────────────────────────
# Error Level Analysis
# ──────────────────────────────────────────────────────────────────────
def error_level_analysis(path: Path, doc_id: str) -> tuple[dict[str, Any], list[Finding], dict[str, str]]:
    """Error Level Analysis with *spatial-concentration* discrimination.

    Genuine single-capture documents recompress with error spread evenly across
    all content (every text stroke errors a little). A region that was edited /
    pasted after the fact concentrates the recompression error into one compact
    area. We therefore key the decision on how *concentrated* the high-error
    energy is (dominant connected component vs. total), which is robust to clean
    documents that legitimately contain a lot of text.
    """
    findings: list[Finding] = []
    artifacts: dict[str, str] = {}
    metrics: dict[str, Any] = {}

    try:
        original = Image.open(path).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        metrics["error"] = f"unreadable image: {exc}"
        return metrics, findings, artifacts

    buf = io.BytesIO()
    original.save(buf, "JPEG", quality=settings.ela_quality)
    buf.seek(0)
    resaved = Image.open(buf).convert("RGB")

    ela = ImageChops.difference(original, resaved)
    err = np.asarray(ela).astype(np.float32).max(axis=2)  # 0-255 per-pixel error
    err = cv2.GaussianBlur(err, (0, 0), sigmaX=1.6)        # regional energy

    # Absolute (not global-max-normalised) thresholding → comparable across docs.
    abs_floor = 14.0
    hot = (err > abs_floor).astype(np.uint8)
    total_hot = int(hot.sum())
    high_ratio = total_hot / hot.size

    # Connected-component analysis to measure concentration.
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(hot, connectivity=8)
    dominant_area = 0
    dominant_idx = -1
    for i in range(1, n_lbl):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area > dominant_area:
            dominant_area, dominant_idx = area, i
    dominance = dominant_area / total_hot if total_hot > 0 else 0.0

    metrics.update(
        ela_high_error_ratio=round(high_ratio, 5),
        ela_hot_pixels=total_hot,
        ela_dominant_area=dominant_area,
        ela_concentration=round(dominance, 3),
        ela_components=max(0, n_lbl - 1),
    )

    # Heatmap artifact.
    heat = np.clip(err * 4.0, 0, 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    artifacts["ela_heatmap"] = _save_artifact(heat_color, f"{doc_id}_ela.png")

    # Tamper signature: a compact, dominant high-error region that is neither a
    # speck nor the whole page.
    page_area = hot.size
    region_ok = 250 <= dominant_area <= 0.25 * page_area
    if dominant_idx > 0 and dominance > 0.45 and region_ok:
        x = int(stats[dominant_idx, cv2.CC_STAT_LEFT])
        y = int(stats[dominant_idx, cv2.CC_STAT_TOP])
        w = int(stats[dominant_idx, cv2.CC_STAT_WIDTH])
        h = int(stats[dominant_idx, cv2.CC_STAT_HEIGHT])

        vis = cv2.imread(str(path))
        if vis is not None:
            cv2.rectangle(vis, (x - 6, y - 6), (x + w + 6, y + h + 6), (0, 0, 255), 3)
            artifacts["ela_overlay"] = _save_artifact(vis, f"{doc_id}_ela_box.png")

        sev = Severity.high if dominance > 0.6 else Severity.medium
        findings.append(
            Finding(
                module="forensics",
                code="ELA_INCONSISTENCY",
                title="Localized compression inconsistency (edited region)",
                detail=(
                    f"{dominance*100:.0f}% of the recompression error is concentrated in a "
                    f"single {w}×{h}px region while the rest of the document is consistent. "
                    "This is the signature of content that was pasted or overwritten after "
                    "the original was created — e.g. an altered value, name or date."
                ),
                severity=sev,
                confidence=min(0.92, 0.5 + dominance * 0.5),
                evidence={
                    "concentration": round(dominance, 3),
                    "region": {"x": x, "y": y, "w": w, "h": h},
                    "heatmap": artifacts["ela_heatmap"],
                    "overlay": artifacts.get("ela_overlay"),
                },
            )
        )
    return metrics, findings, artifacts


# ──────────────────────────────────────────────────────────────────────
# Copy-move forgery (ORB self-matching)
# ──────────────────────────────────────────────────────────────────────
def copy_move_detection(path: Path, doc_id: str) -> tuple[dict[str, Any], list[Finding], dict[str, str]]:
    findings: list[Finding] = []
    artifacts: dict[str, str] = {}
    metrics: dict[str, Any] = {}

    img = cv2.imread(str(path))
    if img is None:
        return metrics, findings, artifacts

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=4000)
    kps, desc = orb.detectAndCompute(gray, None)
    if desc is None or len(kps) < 20:
        metrics["copymove_keypoints"] = 0 if desc is None else len(kps)
        return metrics, findings, artifacts

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw = bf.knnMatch(desc, desc, k=4)

    # Collect candidate clone pairs and bin them by their translation offset.
    # A genuine copy-moved block produces MANY matches that all share (almost)
    # the same offset vector. Symmetric artwork (e.g. a circular seal) or
    # repeated rules produce matches whose offsets are scattered — so requiring a
    # single dominant offset cluster eliminates those false positives.
    from collections import defaultdict

    bin_size = 12
    clusters: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    total_pairs = 0
    for group in raw:
        for m in group:
            if m.queryIdx == m.trainIdx or m.distance >= 32:
                continue
            p1 = np.array(kps[m.queryIdx].pt)
            p2 = np.array(kps[m.trainIdx].pt)
            spatial = float(np.linalg.norm(p1 - p2))
            if spatial < 60:  # ignore near-neighbour texture matches
                continue
            key = tuple(sorted((m.queryIdx, m.trainIdx)))
            if key in seen:
                continue
            seen.add(key)
            total_pairs += 1
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            if dx < 0 or (dx == 0 and dy < 0):  # canonical direction
                dx, dy = -dx, -dy
            clusters[(int(dx // bin_size), int(dy // bin_size))].append(key)

    best_offset, best_pairs = None, []
    for off, pairs in clusters.items():
        if len(pairs) > len(best_pairs):
            best_offset, best_pairs = off, pairs

    metrics["copymove_keypoints"] = len(kps)
    metrics["copymove_candidate_pairs"] = total_pairs
    metrics["copymove_cluster_size"] = len(best_pairs)

    # Verification: a genuine clone is pixel-near-identical at a single offset
    # *within content areas*. We translate the image by the cluster's median
    # offset and look for a large contiguous region where both the source and the
    # shifted copy contain real content (text/seal) AND match closely. This
    # ignores the blank paper background, so coincidental ORB matches (symmetric
    # seals, repeated rules, uniform substrate) do NOT survive — eliminating
    # false positives on genuine documents.
    verified_area = 0
    if best_pairs:
        offs = []
        for a, b in best_pairs:
            dx = kps[b].pt[0] - kps[a].pt[0]
            dy = kps[b].pt[1] - kps[a].pt[1]
            if dx < 0 or (dx == 0 and dy < 0):
                dx, dy = -dx, -dy
            offs.append((dx, dy))
        mdx = int(np.median([o[0] for o in offs]))
        mdy = int(np.median([o[1] for o in offs]))
        if abs(mdx) + abs(mdy) >= 40:
            grad = cv2.morphologyEx(
                (cv2.Laplacian(gray, cv2.CV_32F).__abs__() > 18).astype(np.uint8),
                cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8),
            )
            M = np.float32([[1, 0, mdx], [0, 1, mdy]])
            shifted = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), borderValue=0)
            content_shifted = cv2.warpAffine(grad, M, (grad.shape[1], grad.shape[0]), borderValue=0)
            both_content = (grad & content_shifted).astype(np.uint8)
            close = (cv2.absdiff(gray, shifted) < 14).astype(np.uint8)
            matched = cv2.morphologyEx(both_content & close, cv2.MORPH_CLOSE,
                                       np.ones((7, 7), np.uint8))
            n2, _, st2, _ = cv2.connectedComponentsWithStats(matched, connectivity=8)
            verified_area = max((int(st2[i, cv2.CC_STAT_AREA]) for i in range(1, n2)), default=0)
            metrics["copymove_offset"] = [mdx, mdy]
    metrics["copymove_verified_area"] = verified_area

    if len(best_pairs) >= settings.copymove_min_matches and verified_area >= 1500:
        vis = img.copy()
        for a, b in best_pairs[:150]:
            pa = tuple(map(int, kps[a].pt))
            pb = tuple(map(int, kps[b].pt))
            cv2.circle(vis, pa, 4, (0, 0, 255), -1)
            cv2.circle(vis, pb, 4, (0, 255, 0), -1)
            cv2.line(vis, pa, pb, (0, 255, 255), 1)
        artifacts["copymove_overlay"] = _save_artifact(vis, f"{doc_id}_copymove.png")

        sev = Severity.high if len(best_pairs) >= settings.copymove_min_matches * 2 else Severity.medium
        findings.append(
            Finding(
                module="forensics",
                code="COPY_MOVE",
                title="Copy-move (cloned region) forgery detected",
                detail=(
                    f"{len(best_pairs)} keypoint pairs share one consistent translation "
                    f"offset and a {verified_area:,}px block matches near-identically when "
                    "shifted by that offset — confirming a region of the document was cloned "
                    "and pasted elsewhere (commonly used to duplicate stamps/seals or hide "
                    "original content)."
                ),
                severity=sev,
                confidence=min(0.92, 0.55 + len(best_pairs) / 100),
                evidence={
                    "cluster_size": len(best_pairs),
                    "offset": metrics.get("copymove_offset"),
                    "verified_area": verified_area,
                    "overlay": artifacts["copymove_overlay"],
                },
            )
        )
    return metrics, findings, artifacts


# ──────────────────────────────────────────────────────────────────────
# Noise-floor anomaly (pasted / edited region detection)
# ──────────────────────────────────────────────────────────────────────
def noise_floor_anomaly(path: Path, doc_id: str) -> tuple[dict[str, Any], list[Finding], dict[str, str]]:
    """Detect regions whose noise floor is inconsistent with the rest of the page.

    A genuine scan/photo carries spatially-uniform sensor noise. Content that was
    pasted/typed in an editor lacks this noise, producing a localized region whose
    local noise standard deviation collapses far below the document's background
    noise floor — a reliable splice/edit signature for documents.
    """
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}
    artifacts: dict[str, str] = {}

    img = cv2.imread(str(path))
    if img is None:
        return metrics, findings, artifacts
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)

    residual = gray - cv2.GaussianBlur(gray, (0, 0), 1.0)
    win = (25, 25)
    mean = cv2.boxFilter(residual, -1, win)
    mean_sq = cv2.boxFilter(residual * residual, -1, win)
    local_std = np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))

    # Background = bright, flat areas (the page substrate carrying scan noise).
    bright = cv2.GaussianBlur(gray, (0, 0), 2.0) > 200
    bg_vals = local_std[bright]
    if bg_vals.size < 500:
        metrics["noisefloor_applicable"] = False
        return metrics, findings, artifacts

    floor = float(np.median(bg_vals))
    metrics["noisefloor_background"] = round(floor, 3)
    metrics["noisefloor_applicable"] = True

    if floor < 0.6:  # document carries little/no scan noise → test not meaningful
        metrics["noisefloor_applicable"] = False
        return metrics, findings, artifacts

    # Regions that are bright yet have an anomalously low noise floor.
    low = ((local_std < floor * 0.45) & bright).astype(np.uint8)
    low = cv2.morphologyEx(low, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    low = cv2.morphologyEx(low, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    n_lbl, _, stats, _ = cv2.connectedComponentsWithStats(low, connectivity=8)
    blobs = []
    for i in range(1, n_lbl):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= 900:  # ignore specks
            blobs.append((area, i))
    blobs.sort(reverse=True)
    metrics["noisefloor_anomaly_blobs"] = len(blobs)

    if blobs:
        vis = img.copy()
        regions = []
        for area, i in blobs[:4]:
            x = int(stats[i, cv2.CC_STAT_LEFT]); y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH]); h = int(stats[i, cv2.CC_STAT_HEIGHT])
            regions.append({"x": x, "y": y, "w": w, "h": h, "area": area})
            cv2.rectangle(vis, (x - 4, y - 4), (x + w + 4, y + h + 4), (0, 0, 255), 3)
        artifacts["noise_overlay"] = _save_artifact(vis, f"{doc_id}_noise.png")

        biggest = blobs[0][0]
        sev = Severity.high if biggest > 3000 else Severity.medium
        findings.append(
            Finding(
                module="forensics",
                code="NOISE_FLOOR_ANOMALY",
                title="Edited region detected (noise-floor inconsistency)",
                detail=(
                    f"{len(blobs)} region(s) carry an anomalously low noise floor versus the "
                    f"document's scanned background (floor {floor:.2f}). Genuine scans show "
                    "uniform noise everywhere; a 'clean' patch indicates content that was "
                    "pasted or typed over the original — e.g. an altered value, name or date."
                ),
                severity=sev,
                confidence=min(0.9, 0.55 + biggest / 12000),
                evidence={"background_noise": round(floor, 3), "regions": regions,
                          "overlay": artifacts["noise_overlay"]},
            )
        )
    return metrics, findings, artifacts


# ──────────────────────────────────────────────────────────────────────
# EXIF / metadata analysis
# ──────────────────────────────────────────────────────────────────────
def metadata_analysis(path: Path) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    try:
        img = Image.open(path)
        exif = img.getexif()
    except Exception:  # noqa: BLE001
        return metrics, findings

    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()} if exif else {}
    software = str(tags.get("Software", "")).lower()
    metrics["exif_software"] = software or None
    metrics["exif_present"] = bool(tags)

    if any(s in software for s in EDITING_SOFTWARE):
        findings.append(
            Finding(
                module="forensics",
                code="META_EDITING_SOFTWARE",
                title="Image processed by photo-editing software",
                detail=(
                    f"Metadata records the file as last saved by '{tags.get('Software')}'. "
                    "Official documents/scans are not expected to be exported from "
                    "image editors; this indicates post-capture manipulation."
                ),
                severity=Severity.high,
                confidence=0.85,
                evidence={"software": tags.get("Software")},
            )
        )

    # Capture vs modification timestamp mismatch.
    dt_orig = str(tags.get("DateTimeOriginal", ""))
    dt_mod = str(tags.get("DateTime", ""))
    if dt_orig and dt_mod and dt_orig != dt_mod:
        findings.append(
            Finding(
                module="forensics",
                code="META_TIMESTAMP_MISMATCH",
                title="Capture and modification timestamps differ",
                detail=(
                    f"Original capture time ({dt_orig}) differs from the last "
                    f"modification time ({dt_mod}), indicating the file was altered "
                    "after it was created."
                ),
                severity=Severity.low,
                confidence=0.55,
                evidence={"DateTimeOriginal": dt_orig, "DateTime": dt_mod},
            )
        )
    return metrics, findings


def analyze_image(path: Path, doc_id: str) -> dict[str, Any]:
    """Run all image detectors and return a merged result dict."""
    all_findings: list[Finding] = []
    metrics: dict[str, Any] = {}
    artifacts: dict[str, str] = {}

    # ELA + noise-floor are primary tamper detectors; copy-move flags cloned
    # seals/stamps when match confidence is high (raised threshold in config).
    for fn in (error_level_analysis, noise_floor_anomaly, copy_move_detection):
        try:
            m, f, a = fn(path, doc_id)
            metrics.update(m)
            all_findings.extend(f)
            artifacts.update(a)
        except Exception as exc:  # noqa: BLE001
            metrics[f"{fn.__name__}_error"] = str(exc)

    try:
        m, f = metadata_analysis(path)
        metrics.update(m)
        all_findings.extend(f)
    except Exception as exc:  # noqa: BLE001
        metrics["metadata_analysis_error"] = str(exc)

    return {"findings": all_findings, "metrics": metrics, "artifacts": artifacts}
