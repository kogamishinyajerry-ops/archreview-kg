"""L1 deterministic-from-seed examiner (Phase 18-D).

Generates a flawed 4-room residential plan + project meta + room/stair
schedules + a ground_truth declaring which rule cards the candidate
*should* flag. Parameters are sampled from a fixed RNG seed so every
case is byte-reproducible and the same seed always produces the same
case (critical for diff-investigating regressions).

Coverage today (rule cards that can be deterministically tripped or
left compliant):

  AUTODETECTABLE:
    RC-CORRIDOR-WIDTH                   corridor net width < 1.20
    RC-DOOR-WIDTH                       door net width < 0.90
    RC-BEDROOM-AREA                     bedroom floor area < 5.0
    RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20  same corridor metric

  PROJECT_META_DRIVEN:
    RC-ACCESSIBLE-RESIDENTIAL-RATIO     accessible_units/total_units < 0.02

  PARTIAL_AUTODETECT (via room schedule):
    RC-LIVING-BEDROOM-NETHEIGHT-2.4     bedroom/living net_height < 2.40
    RC-NO-LIVING-IN-BASEMENT            bedroom in level=basement
    RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0 basement room net_height < 2.0
    (RC-PITCHED-ROOF deliberately skipped — tied to majority_net_height_m
     which the candidate's evidence reporting still misuses; track sepately)

  STAIR_PENDING (via stair schedule):
    RC-STAIR-{TREAD,RISER,FLIGHT,HANDRAIL,WELL}

Out of scope here: the 18 REMINDER_BY_DESIGN rules (severity=info project
reminders). They fire based on project_meta context; their P/R isn't a
useful signal because they're surface-the-clause-for-manual-check rather
than rule-decided.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
import yaml

PT_PER_M = 50.0


@dataclass(frozen=True)
class ExpectedViolation:
    """One rule card the examiner expects the candidate to flag for this case."""

    rule_id: str
    entity_hint: str  # e.g. "corridor", "door:0", "bedroom-1", "stair-1", "project"
    note: str


@dataclass
class CaseParameters:
    """All sampled parameters for one generated case. Each field maps to
    either a PDF-drawn dimension, a project meta field, or a schedule
    metric, and each maps to a deterministic predicate over which rules
    will fire."""

    seed: int
    corridor_width_m: float
    door_widths_m: tuple[float, float, float, float]
    bedroom_w_m: float
    bedroom_h_m: float
    floors: int
    height_m: float
    total_units: int
    accessible_units: int
    bedroom_net_height_m: float
    bedroom_level: Literal["basement", "ground", "upper", "mezzanine"]
    include_stair_schedule: bool
    # When stair schedule is included, every metric is tripped to keep
    # the L1 contract simple (one stair → 5 expected stair rule fires).
    stair_metrics_below_threshold: bool


@dataclass
class GeneratedCase:
    case_id: str
    case_dir: Path
    pdf_path: Path
    project_meta_path: Path
    room_schedule_path: Path
    stair_schedule_path: Path | None
    parameters: CaseParameters
    expected_violations: list[ExpectedViolation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parameter sampling
# ---------------------------------------------------------------------------

# Each parameter has a discrete sampling distribution where some samples
# trip a rule and others are compliant. Mixing both is the point — we
# also need compliant cases to measure false-positive rate.
_CORRIDOR_WIDTHS = [0.95, 1.05, 1.15, 1.20, 1.25, 1.50]  # 3 fail, 3 pass
# Door widths are gap sizes the builder bridges. The builder's bridge
# contract is strict 0.70 < gap < 1.00 (archkg/graph/builder.py +
# geometry.py). 1.00 m gaps are NOT bridged → broken graph topology and
# the candidate fails to even see those doors. Codex P18-D R1 caught
# this contaminating the recall signal — keep samples strictly inside
# the bridge range. RC-DOOR-WIDTH threshold is 0.90 m so 0.80/0.85
# fail and 0.90/0.95 pass.
_DOOR_WIDTHS = [0.80, 0.85, 0.90, 0.95]  # 2 fail, 2 pass
# Bedroom dims kept ≥ 3 m on each side so the bedroom polygon stays
# large enough for the corridor-side door (≥0.85 m) to fit, and the
# floor area sweep covers below-and-above the 5 m² RC-BEDROOM-AREA
# threshold without producing a degenerate 2x2 box that breaks the
# builder's polygonizer at the page corner. Codex P18-D R1.
_BEDROOM_DIMS = [(3.0, 1.6), (3.0, 1.8), (3.0, 2.5), (4.0, 4.0)]  # area 4.8/5.4/7.5/16
_FLOORS = [3, 5, 6, 7, 12, 18]
_NET_HEIGHTS = [2.20, 2.30, 2.40, 2.50, 2.80]  # 2 fail (<2.40), 3 pass
_LEVELS: list[Literal["basement", "ground", "upper", "mezzanine"]] = [
    "basement",
    "ground",
    "upper",
]
_TOTAL_UNITS = [50, 100, 200, 500]


def sample_parameters(seed: int) -> CaseParameters:
    rng = random.Random(seed)
    bw, bh = rng.choice(_BEDROOM_DIMS)
    floors = rng.choice(_FLOORS)
    total = rng.choice(_TOTAL_UNITS)
    # 50% chance of below-2% accessible ratio.
    if rng.random() < 0.5:
        accessible = max(0, int(total * 0.01))  # below threshold
    else:
        accessible = max(2, int(total * 0.03))  # above threshold
    return CaseParameters(
        seed=seed,
        corridor_width_m=rng.choice(_CORRIDOR_WIDTHS),
        door_widths_m=tuple(rng.choice(_DOOR_WIDTHS) for _ in range(4)),  # type: ignore[arg-type]
        bedroom_w_m=bw,
        bedroom_h_m=bh,
        floors=floors,
        height_m=floors * rng.choice([2.8, 3.0]) + 0.5,
        total_units=total,
        accessible_units=accessible,
        bedroom_net_height_m=rng.choice(_NET_HEIGHTS),
        bedroom_level=rng.choice(_LEVELS),
        include_stair_schedule=rng.random() < 0.5,
        stair_metrics_below_threshold=True,
    )


# ---------------------------------------------------------------------------
# Predicate: parameters → expected violation list
# ---------------------------------------------------------------------------

def predict_expected_violations(p: CaseParameters) -> list[ExpectedViolation]:
    """The single source of truth for what each case ought to flag.

    Mirrors rule_cards.yaml logic verbatim — keep the conditions tight
    so any divergence is the rule's bug, not the examiner's.
    """
    expected: list[ExpectedViolation] = []

    # RC-CORRIDOR-WIDTH: corridor < 1.20
    if p.corridor_width_m < 1.20:
        expected.append(
            ExpectedViolation(
                rule_id="RC-CORRIDOR-WIDTH",
                entity_hint="corridor",
                note=f"corridor {p.corridor_width_m:.2f} m < 1.20 m",
            )
        )
        # Same metric drives the accessible-corridor rule.
        expected.append(
            ExpectedViolation(
                rule_id="RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20",
                entity_hint="corridor",
                note=f"corridor {p.corridor_width_m:.2f} m < 1.20 m (accessible)",
            )
        )

    # RC-DOOR-WIDTH: each door < 0.90
    for i, w in enumerate(p.door_widths_m):
        if w < 0.90:
            expected.append(
                ExpectedViolation(
                    rule_id="RC-DOOR-WIDTH",
                    entity_hint=f"door:{i}",
                    note=f"door {i} {w:.2f} m < 0.90 m",
                )
            )

    # RC-BEDROOM-AREA: bedroom < 5.0 m²
    bedroom_area = p.bedroom_w_m * p.bedroom_h_m
    if bedroom_area < 5.0:
        expected.append(
            ExpectedViolation(
                rule_id="RC-BEDROOM-AREA",
                entity_hint="bedroom",
                note=f"bedroom area {bedroom_area:.1f} m² < 5.0 m²",
            )
        )

    # RC-ACCESSIBLE-RESIDENTIAL-RATIO: accessible/total < 0.02
    if p.total_units >= 1 and p.accessible_units / p.total_units < 0.02:
        expected.append(
            ExpectedViolation(
                rule_id="RC-ACCESSIBLE-RESIDENTIAL-RATIO",
                entity_hint="project",
                note=f"{p.accessible_units}/{p.total_units} = {p.accessible_units/p.total_units:.3f} < 0.02",
            )
        )

    # Room schedule rules. Bedroom label in our generator is always
    # 'bedroom', so:
    # RC-LIVING-BEDROOM-NETHEIGHT-2.4
    if p.bedroom_net_height_m < 2.40:
        expected.append(
            ExpectedViolation(
                rule_id="RC-LIVING-BEDROOM-NETHEIGHT-2.4",
                entity_hint="bedroom",
                note=f"bedroom net height {p.bedroom_net_height_m:.2f} < 2.40",
            )
        )

    # RC-NO-LIVING-IN-BASEMENT: bedroom + level=basement
    if p.bedroom_level == "basement":
        expected.append(
            ExpectedViolation(
                rule_id="RC-NO-LIVING-IN-BASEMENT",
                entity_hint="bedroom",
                note="bedroom in basement (forbidden)",
            )
        )
        # Combined with low net height, RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0
        # would also fire (basement room < 2.0 m).
        if p.bedroom_net_height_m < 2.0:
            expected.append(
                ExpectedViolation(
                    rule_id="RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0",
                    entity_hint="bedroom",
                    note=f"basement room net height {p.bedroom_net_height_m:.2f} < 2.0",
                )
            )

    # Stair schedule rules: when included with adversarial values, all
    # 5 fire on stair-1.
    if p.include_stair_schedule and p.stair_metrics_below_threshold:
        for rule_id in (
            "RC-STAIR-FLIGHT-WIDTH-1.10",
            "RC-STAIR-TREAD-WIDTH-0.26",
            "RC-STAIR-RISER-HEIGHT-0.175",
            "RC-STAIR-HANDRAIL-0.90",
            "RC-STAIR-WELL-WIDTH-0.11",
        ):
            expected.append(
                ExpectedViolation(
                    rule_id=rule_id,
                    entity_hint="stair-1",
                    note="adversarial stair entry, all metrics over/under threshold",
                )
            )

    return expected


# ---------------------------------------------------------------------------
# PDF + meta + schedule writing
# ---------------------------------------------------------------------------

def _m_to_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return x_m * PT_PER_M, y_m * PT_PER_M


def _line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line(_m_to_pt(x0, y0), _m_to_pt(x1, y1), color=(0, 0, 0), width=1.2)


def _label(page: fitz.Page, x_m: float, y_m: float, text: str) -> None:
    page.insert_text(_m_to_pt(x_m, y_m), text, fontsize=8, color=(0, 0, 0))


def _write_pdf(pdf_path: Path, p: CaseParameters) -> None:
    """Write a 4-room plan whose dimensions encode the sampled parameters.

    Layout matches samples/make_sample.py so the entity graph builder
    can read it the same way: top strip (BEDROOM, LIVING) / corridor /
    bottom strip (BATHROOM, KITCHEN). Bedroom dimensions are tweaked
    per-case; corridor and door widths come from sampled parameters.
    """
    bw, bh = p.bedroom_w_m, p.bedroom_h_m
    # Living/kitchen strip is fixed 5 m wide so door widths up to 1.0 m
    # always fit. Bedroom shrinks/grows independently.
    right_w = 5.0
    page_w = bw + right_w
    page_h = bh * 2 + p.corridor_width_m + 1.0  # padding
    corridor_top_y = bh
    corridor_bot_y = bh + p.corridor_width_m

    doc = fitz.open()
    page = doc.new_page(width=page_w * PT_PER_M, height=page_h * PT_PER_M)

    # Outer rectangle
    _line(page, 0, 0, page_w, 0)
    _line(page, page_w, 0, page_w, page_h)
    _line(page, page_w, page_h, 0, page_h)
    _line(page, 0, page_h, 0, 0)

    # Vertical mid-wall: bedroom↔living and bathroom↔kitchen door gaps.
    # Codex P18-D R1: previously scaled the gap with bedroom height (bh*0.2)
    # which produced 0.4-0.8 m gaps for small bedrooms — outside the
    # builder's 0.70 < gap < 1.00 bridge contract, breaking topology.
    # Anchor the gap at a fixed compliant 0.95 m centered in the room so
    # (a) the builder always bridges (it falls inside 0.70-1.00) and
    # (b) it doesn't fire RC-DOOR-WIDTH (>= 0.90 → compliant). 0.85 m
    # was the original choice but it tripped RC-DOOR-WIDTH on every
    # case because the predictor only tracks the 4 corridor-side doors,
    # not the 2 mid-wall doors the builder also creates as Door entities
    # — every case had 2 unexpected FP. Surfaced by a 50-case battery.
    mid_gap = 0.95
    n_top = max(0.1, (bh - mid_gap) / 2)
    _line(page, bw, 0, bw, n_top)
    _line(page, bw, n_top + mid_gap, bw, corridor_top_y)
    _line(page, bw, corridor_bot_y, bw, corridor_bot_y + n_top)
    _line(page, bw, corridor_bot_y + n_top + mid_gap, bw, page_h)

    # Top corridor wall with gaps for bedroom/living doors.
    door_w0, door_w1, door_w2, door_w3 = p.door_widths_m
    bd_door_x0 = bw * 0.4
    bd_door_x1 = bd_door_x0 + door_w0
    lv_door_x0 = bw + right_w * 0.4
    lv_door_x1 = lv_door_x0 + door_w1
    _line(page, 0, corridor_top_y, bd_door_x0, corridor_top_y)
    _line(page, bd_door_x1, corridor_top_y, lv_door_x0, corridor_top_y)
    _line(page, lv_door_x1, corridor_top_y, page_w, corridor_top_y)

    # Bottom corridor wall with gaps for bathroom/kitchen doors.
    ba_door_x0 = bw * 0.4
    ba_door_x1 = ba_door_x0 + door_w2
    kt_door_x0 = bw + right_w * 0.4
    kt_door_x1 = kt_door_x0 + door_w3
    _line(page, 0, corridor_bot_y, ba_door_x0, corridor_bot_y)
    _line(page, ba_door_x1, corridor_bot_y, kt_door_x0, corridor_bot_y)
    _line(page, kt_door_x1, corridor_bot_y, page_w, corridor_bot_y)

    # Labels
    _label(page, bw * 0.3, bh * 0.5, "BEDROOM")
    _label(page, bw + right_w * 0.3, bh * 0.5, "LIVING")
    _label(page, bw * 0.3, corridor_bot_y + bh * 0.5, "BATHROOM")
    _label(page, bw + right_w * 0.3, corridor_bot_y + bh * 0.5, "KITCHEN")

    # Dimension annotations — must be readable by builder's regex.
    _label(
        page,
        page_w * 0.4,
        corridor_top_y + p.corridor_width_m * 0.5,
        f"CORRIDOR W={p.corridor_width_m:.2f}",
    )
    for x, y, w in [
        (bd_door_x0, corridor_top_y - 0.2, door_w0),
        (lv_door_x0, corridor_top_y - 0.2, door_w1),
        (ba_door_x0, corridor_bot_y + 0.2, door_w2),
        (kt_door_x0, corridor_bot_y + 0.2, door_w3),
    ]:
        _label(page, x, y, f"DOOR {w:.2f}")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(pdf_path))
    doc.close()


def _write_project_meta(meta_path: Path, p: CaseParameters, project_id: str) -> None:
    payload = {
        "project_id": project_id,
        "project_name": f"adversarial case (seed={p.seed})",
        "building_type": "residential",
        "height_class": "高层" if p.floors >= 7 else "多层",
        "fire_class": "二级",
        "climate_zone": "寒冷",
        "use_type": "住宅",
        "height_m": round(p.height_m, 1),
        "floors": p.floors,
        "total_units": p.total_units,
        "accessible_units": p.accessible_units,
    }
    meta_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_room_schedule(schedule_path: Path, p: CaseParameters, project_id: str) -> None:
    payload = {
        "project_id": project_id,
        "entries": [
            {
                "label": "bedroom",
                "level": p.bedroom_level,
                "net_height_m": round(p.bedroom_net_height_m, 2),
            },
            # Living always in upper level, normal height — keeps the
            # ground truth easy to predict.
            {
                "label": "living",
                "level": "upper",
                "net_height_m": 2.80,
            },
        ],
    }
    schedule_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_stair_schedule(schedule_path: Path, project_id: str) -> None:
    """Adversarial stair: every metric over/under its threshold.

    Mirrors samples/stair_schedule_demo.yaml so battery cases re-validate
    that same-fixture path repeatedly under different surrounding noise.
    """
    payload = {
        "project_id": project_id,
        "entries": [
            {
                "stair_id": "stair-1",
                "page_index": 0,
                "tread_width_m": 0.24,
                "riser_height_m": 0.18,
                "flight_width_m": 0.95,
                "handrail_height_m": 0.85,
                "well_width_m": 0.14,
            }
        ],
    }
    schedule_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_case(seed: int, out_dir: Path) -> GeneratedCase:
    """Generate one full case (pdf + meta + schedules + ground truth)
    deterministically from `seed`. `out_dir` becomes case_dir/."""
    p = sample_parameters(seed)
    project_id = f"ADV-{seed:06d}"
    case_id = f"case-{seed:06d}"
    case_dir = out_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = case_dir / "plan.pdf"
    meta_path = case_dir / "project_meta.yaml"
    room_schedule_path = case_dir / "room_schedule.yaml"
    stair_schedule_path = case_dir / "stair_schedule.yaml"

    _write_pdf(pdf_path, p)
    _write_project_meta(meta_path, p, project_id)
    _write_room_schedule(room_schedule_path, p, project_id)

    if p.include_stair_schedule:
        _write_stair_schedule(stair_schedule_path, project_id)
    else:
        stair_schedule_path = None  # type: ignore[assignment]

    expected = predict_expected_violations(p)
    ground_truth = {
        "case_id": case_id,
        "seed": seed,
        "parameters": {
            "corridor_width_m": p.corridor_width_m,
            "door_widths_m": list(p.door_widths_m),
            "bedroom_w_m": p.bedroom_w_m,
            "bedroom_h_m": p.bedroom_h_m,
            "floors": p.floors,
            "total_units": p.total_units,
            "accessible_units": p.accessible_units,
            "bedroom_net_height_m": p.bedroom_net_height_m,
            "bedroom_level": p.bedroom_level,
            "include_stair_schedule": p.include_stair_schedule,
        },
        "expected_violations": [
            {"rule_id": v.rule_id, "entity_hint": v.entity_hint, "note": v.note}
            for v in expected
        ],
    }
    (case_dir / "ground_truth.yaml").write_text(
        yaml.safe_dump(ground_truth, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return GeneratedCase(
        case_id=case_id,
        case_dir=case_dir,
        pdf_path=pdf_path,
        project_meta_path=meta_path,
        room_schedule_path=room_schedule_path,
        stair_schedule_path=stair_schedule_path,
        parameters=p,
        expected_violations=expected,
    )
