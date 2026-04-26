"""Raster-image (PNG/JPEG) primitive extractor (Phase 20-A / v1.3.0).

Produces the same :class:`archkg.schemas.Primitives` shape that the PDF
extractor does, by running computer-vision on a raster floor-plan
image. Lines come from probabilistic Hough transform after thresholding
and morphological thinning; texts are not detected in this version
(OCR deferred to v1.4).

Limitations users should expect:
- Only orthogonal walls (horizontal / vertical). Diagonal walls are
  classified out and dropped. Most residential plans are orthogonal,
  but Western-style plans with bay windows etc. will lose those walls.
- Hand-drawn or scanned-with-noise plans → poor wall detection.
- No OCR ⇒ no labels ⇒ the 5 label-dependent Room rules
  (RC-BEDROOM-AREA / RC-LIVING-BEDROOM-NETHEIGHT-2.4 /
  RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1 /
  RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0 / RC-NO-LIVING-IN-BASEMENT)
  do not fire on raster input. Geometry-only rules still do
  (corridor width, door width, accessibility door width). For a
  complete review, re-upload the matching vector PDF; the
  ``room_schedule.yaml`` selector keys on existing ``room_id`` /
  ``label``, neither of which raster rooms have, so the schedule
  cannot patch raster runs.

The output coordinate frame is image PIXELS (not PostScript points),
so the caller must pass ``points_per_meter`` already converted to
PIXELS PER METER. For a PDF rendered at ``dpi`` to PNG and then fed
back here, ``ppm_pixel = ppm_pdf * dpi / 72``. The studio form's
``points_per_meter`` field is interpreted in this pixel sense for
PNG/JPEG uploads (documented in the form copy).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

# Codex P20-A R1 P0: every length-like CV constant is expressed in
# METERS (physical units) and converted to pixels at runtime using
# ppm. Otherwise the same plan rendered at 150 / 200 / 300 / 600 DPI
# yields different topology because the heuristics fire on raw pixel
# distances. Ratio constants (intensity threshold, aspect tolerance)
# stay scale-free.

# Pixel-intensity threshold for "this is an ink stroke" — scale-free.
INK_THRESHOLD = 200
# Erosion kernel (px) thins multi-pixel-wide strokes so each wall
# yields ONE Hough hit instead of pairs from each stroke edge. But
# at low DPI the strokes are already 1 px wide and erosion would
# erase them. Only erode when the source resolution is high enough
# that strokes are likely 2+ px wide.
EROSION_KERNEL_SIZE = 3
EROSION_PPM_THRESHOLD = 150.0  # don't erode below ~200 DPI metric (ppm < 150)
# Hough probabilistic params (physical units).
HOUGH_RHO = 1
HOUGH_THETA_DEG = 1.0
# Walls below this length aren't worth detecting (≈15 cm).
HOUGH_MIN_LINE_LENGTH_M = 0.15
# A single Hough fragment can leap small gaps (≈4 cm) — slightly
# larger than typical wall stroke jitter, much smaller than any door.
HOUGH_MAX_LINE_GAP_M = 0.04
# Vote threshold: in HoughLinesP roughly equals the contributing
# pixel count along the line. Tying to ``HOUGH_MIN_LINE_LENGTH_M``
# means "any line we'd accept has voted enough."
HOUGH_VOTE_THRESHOLD_M = HOUGH_MIN_LINE_LENGTH_M
# Walls within this perpendicular distance share a Hough bin
# (typical CAD wall thickness ≈ 6 cm).
PERP_BIN_M = 0.06
# Within a bin, merge collinear intervals only if their gap is below
# this physical size. Real doors are 0.7-1.0 m, so this is well
# below door gap → ``bridge_door_gaps`` still detects doors.
INTERVAL_MERGE_GAP_M = 0.40
# Snap line endpoints to the perpendicular wall within this distance
# (~20 cm typical wall thickness times a hierarchy fudge factor).
ENDPOINT_SNAP_TOL_M = 0.20
# Reject lines whose perpendicular axis is not roughly horizontal /
# vertical — diagonal walls aren't supported (scale-free).
ORTHOGONAL_ASPECT_TOL = 4


def extract(
    image_path: Path,
    *,
    points_per_meter: float = 50.0,
) -> Primitives:
    """Run the raster ingest pipeline on a single PNG/JPEG file.

    ``points_per_meter`` is interpreted in PIXELS for raster inputs.
    The default 50.0 is rarely correct for raster — callers should
    set it from the source DPI.
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(
            f"Could not read image at {image_path}; supported formats are "
            "PNG, JPEG, BMP, TIFF (anything cv2.imread accepts)."
        )
    height_px, width_px = img.shape[:2]

    line_primitives = _detect_walls(img, points_per_meter)

    page = PagePrimitives(
        page_index=0,
        width_pt=float(width_px),
        height_pt=float(height_px),
        lines=line_primitives,
        texts=[],  # OCR deferred to v1.4
    )
    return Primitives(
        source_pdf=str(image_path),
        points_per_meter=points_per_meter,
        pages=[page],
    )


def _detect_walls(
    image: NDArray[Any],
    points_per_meter: float,
) -> list[LinePrimitive]:
    """Threshold → thin → Hough → dedupe orthogonal wall segments.

    Phase 20-A R1 P0: all length-like Hough/dedupe parameters are
    derived from ``points_per_meter`` so the same plan rendered at
    different DPIs produces the same topology.
    """
    min_length_px = max(int(HOUGH_MIN_LINE_LENGTH_M * points_per_meter), 8)
    max_gap_px = max(int(HOUGH_MAX_LINE_GAP_M * points_per_meter), 2)
    vote_threshold = max(int(HOUGH_VOTE_THRESHOLD_M * points_per_meter), 8)

    _, binary = cv2.threshold(image, INK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    if points_per_meter >= EROSION_PPM_THRESHOLD:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (EROSION_KERNEL_SIZE, EROSION_KERNEL_SIZE)
        )
        thinned = cv2.erode(binary, kernel, iterations=1)
    else:
        thinned = binary

    raw = cv2.HoughLinesP(
        thinned,
        rho=HOUGH_RHO,
        theta=np.pi / 180 * HOUGH_THETA_DEG,
        threshold=vote_threshold,
        minLineLength=min_length_px,
        maxLineGap=max_gap_px,
    )
    if raw is None:
        return []

    perp_bin_px = max(int(PERP_BIN_M * points_per_meter), 2)
    interval_merge_gap_px = max(int(INTERVAL_MERGE_GAP_M * points_per_meter), 5)
    deduped = list(
        _dedupe_to_orthogonal_segments(raw, perp_bin_px, interval_merge_gap_px)
    )

    snap_tol_px = max(ENDPOINT_SNAP_TOL_M * points_per_meter, 2.0)
    return _snap_endpoints_to_perpendicular_walls(deduped, snap_tol_px)


def _snap_endpoints_to_perpendicular_walls(
    segments: list[LinePrimitive],
    snap_tol_px: float,
) -> list[LinePrimitive]:
    """Snap each segment's endpoints to the nearest perpendicular wall
    within :data:`ENDPOINT_SNAP_TOL_PX`. Hough often stops a few
    pixels short of true corners; without this pass, walls dangle
    and ``polygonize_segments`` cannot close the rooms.

    A horizontal segment's left/right endpoints are snapped to the
    x-coordinate of the nearest vertical wall whose y-span covers
    the segment's y. Vertical segments are snapped symmetrically.
    """
    h_segs = []
    v_segs = []
    for s in segments:
        if s.p0[1] == s.p1[1]:
            h_segs.append(s)
        elif s.p0[0] == s.p1[0]:
            v_segs.append(s)

    def snap_x(x: float, y: float) -> float:
        best_dx = snap_tol_px + 1
        best_x = x
        for v in v_segs:
            v_x = v.p0[0]
            v_y_lo = min(v.p0[1], v.p1[1])
            v_y_hi = max(v.p0[1], v.p1[1])
            if not (v_y_lo - snap_tol_px <= y <= v_y_hi + snap_tol_px):
                continue
            dx = abs(v_x - x)
            if dx < best_dx:
                best_dx = dx
                best_x = v_x
        return best_x

    def snap_y(x: float, y: float) -> float:
        best_dy = snap_tol_px + 1
        best_y = y
        for h in h_segs:
            h_y = h.p0[1]
            h_x_lo = min(h.p0[0], h.p1[0])
            h_x_hi = max(h.p0[0], h.p1[0])
            if not (h_x_lo - snap_tol_px <= x <= h_x_hi + snap_tol_px):
                continue
            dy = abs(h_y - y)
            if dy < best_dy:
                best_dy = dy
                best_y = h_y
        return best_y

    snapped: list[LinePrimitive] = []
    for s in h_segs:
        x0, y = s.p0
        x1, _ = s.p1
        new_x0 = snap_x(x0, y)
        new_x1 = snap_x(x1, y)
        snapped.append(LinePrimitive(p0=(new_x0, y), p1=(new_x1, y)))
    for s in v_segs:
        x, y0 = s.p0
        _, y1 = s.p1
        new_y0 = snap_y(x, y0)
        new_y1 = snap_y(x, y1)
        snapped.append(LinePrimitive(p0=(x, new_y0), p1=(x, new_y1)))
    return snapped


def _dedupe_to_orthogonal_segments(
    raw_lines: NDArray[Any],
    perp_bin_px: int,
    interval_merge_gap_px: int,
) -> Iterable[LinePrimitive]:
    """Bin Hough output by axis + perpendicular position, merge
    collinear intervals across small gaps but preserve door-sized
    gaps so ``bridge_door_gaps`` can detect doors downstream.

    Phase 20-A R1 P0: ``perp_bin_px`` and ``interval_merge_gap_px``
    are derived from ``points_per_meter`` by the caller, so the same
    plan rendered at different DPIs collapses into the same wall set.
    """
    bins: dict[tuple[str, int], list[tuple[int, int, int]]] = defaultdict(list)
    for line in raw_lines:
        x0, y0, x1, y1 = (int(c) for c in line[0])
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if dy < dx // ORTHOGONAL_ASPECT_TOL:
            y_avg = (y0 + y1) // 2
            bins[("h", y_avg // perp_bin_px)].append(
                (min(x0, x1), max(x0, x1), y_avg)
            )
        elif dx < dy // ORTHOGONAL_ASPECT_TOL:
            x_avg = (x0 + x1) // 2
            bins[("v", x_avg // perp_bin_px)].append(
                (min(y0, y1), max(y0, y1), x_avg)
            )
        # Diagonal lines are dropped (Phase 20-A limitation).

    for (axis, _), entries in bins.items():
        # Sort by interval start.
        entries.sort()
        perp_avg = sum(p for _, _, p in entries) // len(entries)

        cur_lo, cur_hi = entries[0][0], entries[0][1]
        for lo, hi, _ in entries[1:]:
            if lo - cur_hi <= interval_merge_gap_px:
                cur_hi = max(cur_hi, hi)
            else:
                yield _to_line_primitive(axis, cur_lo, cur_hi, perp_avg)
                cur_lo, cur_hi = lo, hi
        yield _to_line_primitive(axis, cur_lo, cur_hi, perp_avg)


def _to_line_primitive(
    axis: str, lo: int, hi: int, perp: int
) -> LinePrimitive:
    if axis == "h":
        return LinePrimitive(p0=(float(lo), float(perp)), p1=(float(hi), float(perp)))
    return LinePrimitive(p0=(float(perp), float(lo)), p1=(float(perp), float(hi)))


def wrap_image_as_pdf(image_path: Path, out_pdf: Path) -> Path:
    """Embed a raster image into a PDF whose page is exactly W x H points
    (1 pt = 1 px). This keeps the raster extractor's pixel-space line
    coordinates in lockstep with everything that consumes the wrapped
    PDF (overlay rendering, annotation, preview).

    Without the 1:1 mapping, ``fitz.open(image)`` defaults to ~96 DPI,
    which makes the page rect 4/3 smaller than the pixel grid and the
    overlay polygons land off-center.
    """
    import fitz

    src = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if src is None:
        raise ValueError(f"Could not read image at {image_path}")
    height, width = src.shape[:2]

    pdf = fitz.open()
    page = pdf.new_page(width=width, height=height)
    rect = fitz.Rect(0, 0, width, height)
    page.insert_image(rect, filename=str(image_path))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(str(out_pdf))
    pdf.close()
    return out_pdf


__all__ = ["extract", "wrap_image_as_pdf"]
