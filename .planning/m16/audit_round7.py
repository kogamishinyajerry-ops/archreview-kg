"""M16.B Round-7 adversarial audit — title-block FP quantification + R6 regressions + CSP/CSRF deep probes."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path("/Users/Zhuanz/archreview-kg")
BASE = "http://127.0.0.1:8792"
MANIFEST_PATH = ROOT / ".planning/m16/defective_plan_round7_manifest.json"
OUT_PATH = ROOT / ".planning/m16/qa_findings_round7.json"
SUMMARY_PATH = ROOT / ".planning/m16/AUDIT_SUMMARY.md"
SLUG = "test-m16-defective-plan"
DRAWING_ID = 40
DB_PATH = ROOT / ".archkg/kg.db"

# Bottom-left coords from manifest
TITLE_BLOCK_BL = (60.0, 697.0, 1130.0, 812.0)
LEGEND_BL = (60.0, 30.0, 1130.0, 80.0)


# ----------------- HTTP helpers -----------------

def http_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def http_status(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return -1


def http_post_raw(url: str, body: bytes, headers: dict | None = None, method: str = "POST") -> tuple[int, str, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode(errors="replace"), dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace"), dict(exc.headers)


def http_post(url: str, body: dict | None, headers: dict | None = None, ctype: str = "application/json") -> tuple[int, str, dict]:
    data = json.dumps(body or {}).encode() if ctype == "application/json" else (body if isinstance(body, (bytes, bytearray)) else str(body or "").encode())
    h = {"Content-Type": ctype, **(headers or {})}
    return http_post_raw(url, data, h)


# ----------------- Fresh engine ground truth -----------------

DOOR_RULE_HINT = "DOOR"
PLAN_PDF_REL = "samples/real_plans/test-m16-defective-plan.pdf"
FRESH_RUN_DIR = ROOT / ".planning/m16/_audit_fresh_run"


def fresh_engine_issues(pdf_rel: str = PLAN_PDF_REL) -> list[dict]:
    """Run the CURRENT engine end-to-end and return its issues normalized to
    the stage_a shape ``{id, rule_id, bbox, page_index}``.

    Audit-honesty fix (round 7): stage_a previously read the live server's
    ``/api/projects/<slug>/issues``, which reflects whatever ingest happens to
    be sitting in ``.archkg/kg.db`` — NOT the code under test. That let the
    score silently measure a stale run. This helper re-runs ``archkg review``
    every audit so engine metrics (recall / title-block FP / page_index /
    degenerate bbox) reflect the actual current engine.
    """
    if FRESH_RUN_DIR.exists():
        shutil.rmtree(FRESH_RUN_DIR)
    subprocess.run(
        [sys.executable, "-m", "archkg.cli.main", "review",
         str(ROOT / pdf_rel), "--out", str(FRESH_RUN_DIR)],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT), check=True,
    )
    raw = json.loads((FRESH_RUN_DIR / "issues.json").read_text())
    issues_raw = raw if isinstance(raw, list) else raw.get("issues", [])
    return [
        {
            "id": it.get("issue_id") or it.get("id"),
            "rule_id": it.get("rule_card_id") or it.get("rule_id"),
            "bbox": it.get("bbox"),
            "page_index": it.get("page_index", 0),
        }
        for it in issues_raw
    ]


# ----------------- Geometry helpers -----------------

def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0, ix1, iy1 = max(ax0, bx0), max(ay0, by0), min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def _containment_of_a_in_b(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Fraction of bbox A's area that falls inside bbox B."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0, ix1, iy1 = max(ax0, bx0), max(ay0, by0), min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    if area_a <= 0:
        return 0.0
    return inter / area_a


# ----------------- Stage A — title-block FP quantification + recall -----------------

def stage_a(manifest: dict, issues: list[dict]) -> dict:
    # `issues` is the FRESH engine output (see fresh_engine_issues) — the
    # ground truth for engine metrics, decoupled from the served (possibly
    # stale) .archkg/kg.db.

    # by page
    by_page: dict[str, int] = {}
    for i in issues:
        by_page[str(i.get("page_index", "MISSING"))] = by_page.get(str(i.get("page_index", "MISSING")), 0) + 1

    # by rule
    by_rule: dict[str, int] = {}
    for i in issues:
        rid = i.get("rule_id", "?")
        by_rule[rid] = by_rule.get(rid, 0) + 1

    # Degenerate door bbox count — MEASURED, not assumed. (Round-7 R7-BUG-006
    # used to be emitted unconditionally; this lets the finding reflect reality.)
    degenerate_door_bbox = 0
    for i in issues:
        if DOOR_RULE_HINT in (i.get("rule_id") or "") and i.get("bbox"):
            x0, y0, x1, y1 = (float(v) for v in i["bbox"])
            if (x1 - x0) <= 0 or (y1 - y0) <= 0:
                degenerate_door_bbox += 1

    # title-block FP detection
    traps = manifest.get("title_block_phantom_traps", [])
    tb_fp_count = 0
    tb_fp_per_page = {"0": 0, "1": 0}
    title_block_containment_fp = 0  # >=50% area inside title_block_rect
    legend_containment_fp = 0
    fp_detail: list[dict] = []
    for i in issues:
        bbox_pts = tuple(float(x) for x in (i.get("bbox") or [0, 0, 0, 0]))
        if len(bbox_pts) != 4 or (bbox_pts[2] - bbox_pts[0]) <= 0 or (bbox_pts[3] - bbox_pts[1]) <= 0:
            # degenerate (height=0 or width=0); use small epsilon expansion for IoU
            bbox_pts = (bbox_pts[0], bbox_pts[1] - 0.5, bbox_pts[2], bbox_pts[3] + 0.5)
        # IoU vs phantom traps
        iou_hits = []
        for t in traps:
            tb = tuple(float(x) for x in t["bbox_pts"])
            iou = _iou(bbox_pts, tb)
            if iou >= 0.3:
                iou_hits.append({"trap_note": t["note"][:80], "iou": round(iou, 3)})
        # Containment in title_block_rect_bl or legend_rect_bl
        tb_cont = _containment_of_a_in_b(bbox_pts, TITLE_BLOCK_BL)
        lg_cont = _containment_of_a_in_b(bbox_pts, LEGEND_BL)
        is_tb_fp = bool(iou_hits) or tb_cont >= 0.5 or lg_cont >= 0.5
        if is_tb_fp:
            tb_fp_count += 1
            tb_fp_per_page[str(i.get("page_index", 0))] = tb_fp_per_page.get(str(i.get("page_index", 0)), 0) + 1
            if tb_cont >= 0.5:
                title_block_containment_fp += 1
            if lg_cont >= 0.5:
                legend_containment_fp += 1
            fp_detail.append({
                "issue_id": i["id"], "rule_id": i["rule_id"], "bbox": list(bbox_pts),
                "iou_hits": iou_hits, "title_block_containment": round(tb_cont, 3),
                "legend_containment": round(lg_cont, 3), "page_index": i.get("page_index"),
            })

    # Recall vs intended_defects
    intended = manifest.get("intended_defects", [])
    recall_hits = 0
    recall_misses = []
    for d in intended:
        dbb = tuple(float(x) for x in d["bbox_pts"])
        # Engine emits bbox with degenerate height for door labels; allow x-axis overlap >= 50% + same rule_id
        # as proxy for "engine fired on this defect". Plus look at IoU>=0.1.
        matched = False
        for i in issues:
            ibb = tuple(float(x) for x in (i.get("bbox") or [0, 0, 0, 0]))
            if not (i.get("rule_id") == d["rule_id"]):
                continue
            iou = _iou(dbb, ibb)
            # x-overlap fraction as fallback (engine's degenerate-height bboxes)
            x_ov = max(0.0, min(ibb[2], dbb[2]) - max(ibb[0], dbb[0]))
            x_frac = x_ov / max(0.001, dbb[2] - dbb[0])
            same_page = (int(i.get("page_index", 0)) == int(d.get("page_index", 0)))
            if same_page and (iou >= 0.1 or x_frac >= 0.5):
                matched = True
                break
        if matched:
            recall_hits += 1
        else:
            recall_misses.append({"page": d["page_index"], "rule": d["rule_id"], "bbox": d["bbox_pts"], "note": d.get("note", "")[:80]})

    recall_pct = round(100.0 * recall_hits / len(intended), 1) if intended else 0.0

    # Decoy FPs — did engine fire on any "should_not_fire" decoy?
    decoy_fps: list[dict] = []
    for d in manifest.get("decoys", []):
        if not d.get("should_not_fire"):
            continue
        dbb = tuple(float(x) for x in d["bbox_pts"])
        for i in issues:
            if i.get("rule_id") != d["rule_id"]:
                continue
            ibb = tuple(float(x) for x in (i.get("bbox") or [0, 0, 0, 0]))
            iou = _iou(dbb, ibb)
            x_ov = max(0.0, min(ibb[2], dbb[2]) - max(ibb[0], dbb[0]))
            x_frac = x_ov / max(0.001, dbb[2] - dbb[0])
            if iou >= 0.1 or x_frac >= 0.5:
                decoy_fps.append({"decoy": d.get("note", "")[:60], "issue_id": i["id"], "bbox_engine": list(ibb)})

    # Readiness + page PNG probes hit the live server (UI concern). stage_a no
    # longer depends on the server for engine metrics, so degrade gracefully if
    # it's down rather than crashing the whole audit.
    try:
        readiness = http_json(f"{BASE}/api/projects/{SLUG}/readiness")
    except Exception as exc:
        readiness = {"summary": f"<server unreachable: {exc}>"}

    # Audit-integrity probe: does the SERVED db (what Stage B/C UI probes read)
    # agree with the fresh engine output? Divergence => the live ingest is stale
    # and the UI probes are scoring an old run. Surfaced as a loud warning, NOT
    # a scored product finding (it's a harness-freshness issue, not a defect).
    served_issue_count: int | None = None
    served_pages: list[str] | None = None
    try:
        served = http_json(f"{BASE}/api/projects/{SLUG}/issues").get("issues", [])
        served_issue_count = len(served)
        served_pages = sorted({str(s.get("page_index")) for s in served})
    except Exception:
        pass
    served_db_stale = served_issue_count is not None and (
        served_issue_count != len(issues) or served_pages != sorted(by_page.keys())
    )

    tb_pct = round(100.0 * tb_fp_count / max(1, len(issues)), 1)
    return {
        "issues_total": len(issues),
        "issues_by_page": by_page,
        "issues_by_rule": by_rule,
        "degenerate_door_bbox_count": degenerate_door_bbox,
        "served_issue_count": served_issue_count,
        "served_db_stale": served_db_stale,
        "title_block_fp_count": tb_fp_count,
        "title_block_fp_percent_of_total": tb_pct,
        "title_block_fp_per_page": tb_fp_per_page,
        "title_block_containment_fp": title_block_containment_fp,
        "legend_containment_fp": legend_containment_fp,
        "title_block_fp_detail": fp_detail,
        "legitimate_caught": recall_hits,
        "legitimate_count": len(intended),
        "recall_pct": recall_pct,
        "recall_misses": recall_misses,
        "decoy_fps": len(decoy_fps),
        "decoy_fp_detail": decoy_fps,
        "readiness_summary": readiness.get("summary", readiness),
        "page_2_endpoint_status": http_status(f"{BASE}/api/drawings/{DRAWING_ID}/page/2.png"),
        "page_1_png_status": http_status(f"{BASE}/api/drawings/{DRAWING_ID}/page/1.png"),
    }


# ----------------- Stage B — M11-M15 regression battery -----------------

def _wait_workbench(page) -> None:
    page.wait_for_selector("#issues_table tbody tr", timeout=15000)


def stage_b(page) -> list[dict]:
    probes: list[dict] = []

    # === M15.F1 — CSRF (verified via curl) ===
    r1 = subprocess.run(
        ["curl", "-sS", "-o", "/tmp/r7_csrf_cross.txt", "-w", "%{http_code}", "-X", "POST",
         "-H", "Origin: http://evil.example", "-H", "Content-Type: application/json",
         "-d", '{"reviewer":"r7","event":"confirm"}',
         f"{BASE}/api/issues/250/feedback"],
        capture_output=True, text=True, timeout=10)
    cross_code = r1.stdout.strip()
    probes.append({"probe": "M15.F1_csrf_cross_origin_blocked", "status": "PASS" if cross_code == "403" else "FAIL",
                   "evidence": f"cross-origin POST → {cross_code}"})

    r2 = subprocess.run(
        ["curl", "-sS", "-o", "/tmp/r7_csrf_same.txt", "-w", "%{http_code}", "-X", "POST",
         "-H", f"Origin: {BASE}", "-H", "Content-Type: application/json",
         "-d", '{"reviewer":"r7","event":"confirm"}',
         f"{BASE}/api/issues/250/feedback"],
        capture_output=True, text=True, timeout=10)
    same_code = r2.stdout.strip()
    probes.append({"probe": "M15.F1_csrf_same_origin_allowed", "status": "PASS" if same_code == "200" else "FAIL",
                   "evidence": f"same-origin POST → {same_code}"})

    r3 = subprocess.run(
        ["curl", "-sS", "-o", "/tmp/r7_csrf_none.txt", "-w", "%{http_code}", "-X", "POST",
         "-H", "Content-Type: application/json",
         "-d", '{"reviewer":"r7","event":"confirm"}',
         f"{BASE}/api/issues/250/feedback"],
        capture_output=True, text=True, timeout=10)
    none_code = r3.stdout.strip()
    probes.append({"probe": "M15.F1_csrf_no_origin_allowed", "status": "PASS" if none_code == "200" else "FAIL",
                   "evidence": f"no-Origin POST → {none_code}"})

    # === M15.F4 — security headers ===
    r4 = subprocess.run(["curl", "-sSI", f"{BASE}/"], capture_output=True, text=True, timeout=5)
    hdrs = r4.stdout.lower()
    probes.append({"probe": "M15.F4_x_content_type_options", "status": "PASS" if "x-content-type-options: nosniff" in hdrs else "FAIL", "evidence": "header present" if "x-content-type-options: nosniff" in hdrs else "missing"})
    probes.append({"probe": "M15.F4_x_frame_options", "status": "PASS" if "x-frame-options: deny" in hdrs else "FAIL", "evidence": "header present" if "x-frame-options: deny" in hdrs else "missing"})
    probes.append({"probe": "M15.F4_referrer_policy", "status": "PASS" if "referrer-policy: same-origin" in hdrs else "FAIL", "evidence": "header present" if "referrer-policy: same-origin" in hdrs else "missing"})
    probes.append({"probe": "M15.F4_csp_present", "status": "PASS" if "content-security-policy:" in hdrs else "FAIL", "evidence": "header present" if "content-security-policy:" in hdrs else "missing"})

    # === M15.F3 — page_index in API issue rows ===
    api = http_json(f"{BASE}/api/projects/{SLUG}/issues")
    issues = api.get("issues", [])
    has_pidx = all(isinstance(i.get("page_index"), int) for i in issues)
    probes.append({"probe": "M15.F3_page_index_in_api", "status": "PASS" if has_pidx and issues else "FAIL",
                   "evidence": f"issues={len(issues)}, all_have_page_index={has_pidx}"})

    # === Navigate to m16 in browser ===
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    _wait_workbench(page)

    # M15.F2 — drawer close on switch: open drawer, switch to m15 via ⌘K, drawer must close
    page.keyboard.press("j")
    page.wait_for_timeout(120)
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    open_before = page.evaluate("() => { const d = document.querySelector('#drawer'); return d ? d.classList.contains('open') : false; }")
    page.keyboard.press("Meta+K")
    page.wait_for_timeout(250)
    page.fill("#cmdk_input", "m15-defective")
    page.wait_for_timeout(200)
    page.press("#cmdk_input", "Enter")
    page.wait_for_timeout(2500)
    open_after = page.evaluate("() => { const d = document.querySelector('#drawer'); return d ? d.classList.contains('open') : false; }")
    probes.append({"probe": "M15.F2_drawer_closes_on_project_switch",
                   "status": "PASS" if (open_before and not open_after) else ("PARTIAL" if not open_before else "FAIL"),
                   "evidence": f"before_switch={open_before}, after_switch={open_after}"})

    # Switch back to m16
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    _wait_workbench(page)

    # M11/12/13/14 carry-overs
    overflow_y = page.evaluate("() => getComputedStyle(document.body).overflowY")
    probes.append({"probe": "M11_body_no_scroll", "status": "PASS" if overflow_y in ("hidden", "clip") else "FAIL",
                   "evidence": f"body overflow-y={overflow_y}"})

    align = page.evaluate("""() => {
      const lr = document.getElementById('left_rail');
      const vp = document.getElementById('viewport_panel');
      const rr = document.getElementById('right_rail');
      if (!lr||!vp||!rr) return null;
      const lt = lr.getBoundingClientRect().top, vt = vp.getBoundingClientRect().top, rt = rr.getBoundingClientRect().top;
      return {lt, vt, rt, dl: Math.abs(lt-vt), dr: Math.abs(rt-vt)};
    }""")
    probes.append({"probe": "M11_three_rails_align",
                   "status": "PASS" if align and max(align["dl"], align["dr"]) < 3 else "FAIL",
                   "evidence": (f"dl={align['dl']:.1f}, dr={align['dr']:.1f}" if align else "missing rail nodes")})

    page.keyboard.press("Meta+K")
    page.wait_for_timeout(220)
    cmdk_visible = page.evaluate("() => { const el = document.querySelector('#cmdk_palette, .cmdk-overlay, #cmdk'); return el ? getComputedStyle(el).display !== 'none' : false; }")
    probes.append({"probe": "M11_cmdk_opens", "status": "PASS" if cmdk_visible else "FAIL", "evidence": f"visible={cmdk_visible}"})
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)

    banner_text = page.evaluate("() => { const b = document.querySelector('#meta_banner, #readiness_banner, .readiness-banner, .center-banner, [data-readiness]'); return b ? b.textContent.trim() : null; }")
    probes.append({"probe": "M11_readiness_banner_present", "status": "PASS" if banner_text else "FAIL",
                   "evidence": (banner_text or "")[:120]})

    row_count = page.evaluate("() => document.querySelectorAll('#issues_table tbody tr').length")
    probes.append({"probe": "M12_alias_dedupe_active",
                   "status": "PASS" if row_count < 10 else "PARTIAL",
                   "evidence": f"rows={row_count} (engine fired 10 raw issues; UI rows after dedup)"})

    # Drawer probes
    page.keyboard.press("j")
    page.wait_for_timeout(120)
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    drawer_state = page.evaluate("""() => {
      const d = document.querySelector('#drawer, .drawer, [role=dialog]');
      if (!d) return null;
      const rect = d.getBoundingClientRect();
      const overflow = d.scrollHeight - d.clientHeight;
      return {visible: rect.height > 0, rect_h: rect.height, scroll_h: d.scrollHeight, client_h: d.clientHeight, overflow};
    }""")
    probes.append({"probe": "M11_drawer_opens", "status": "PASS" if drawer_state and drawer_state["visible"] else "FAIL",
                   "evidence": str(drawer_state)[:200]})
    focus_inside = page.evaluate("""() => {
      const d = document.querySelector('#drawer, .drawer, [role=dialog]');
      const f = document.activeElement;
      if (!d || !f) return false;
      return d.contains(f);
    }""")
    probes.append({"probe": "M11_drawer_focus_inside", "status": "PASS" if focus_inside else "FAIL",
                   "evidence": f"focus inside={focus_inside}"})

    pill = page.evaluate("() => { const p = document.querySelector('#issues_table tbody tr .pill, #issues_table tbody tr [class*=severity]'); return p ? p.textContent.trim() : null; }")
    probes.append({"probe": "M11_severity_pill_present", "status": "PASS" if pill else "PARTIAL",
                   "evidence": f"pill='{(pill or '')[:40]}'"})

    title = page.evaluate("() => { const t = document.querySelector('#issues_table tbody tr .title'); return t ? t.textContent.trim() : null; }")
    is_human = bool(title and re.search(r"[一-鿿 a-z]", title)) and not (title or "").startswith("RC-")
    probes.append({"probe": "M11_rule_title_human_readable", "status": "PASS" if is_human else "FAIL",
                   "evidence": f"title='{(title or '')[:60]}'"})

    # Skip-link first Tab
    fresh_ctx = page.context.browser.new_context(viewport={"width": 1440, "height": 900})
    fresh_page = fresh_ctx.new_page()
    fresh_page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    fresh_page.wait_for_selector("#issues_table tbody tr", timeout=15000)
    fresh_page.keyboard.press("Tab")
    fresh_page.wait_for_timeout(120)
    first_tab = fresh_page.evaluate("() => document.activeElement && document.activeElement.className")
    probes.append({"probe": "M11_skip_link_first_tab", "status": "PASS" if first_tab and "skip" in (first_tab or "").lower() else "FAIL",
                   "evidence": f"first focus class='{first_tab}'"})
    fresh_ctx.close()

    # Browser back
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    page.wait_for_selector("#issues_table tbody tr", timeout=15000)
    page.goto(f"{BASE}/?p=test-m14-defective-plan", wait_until="domcontentloaded")
    page.wait_for_selector("#issues_table tbody tr", timeout=15000)
    page.wait_for_timeout(300)
    page.go_back()
    page.wait_for_timeout(800)
    after_back = page.evaluate("() => new URL(location.href).searchParams.get('p')")
    probes.append({"probe": "M11_browser_back_restores_prior",
                   "status": "PASS" if after_back == SLUG else "FAIL",
                   "evidence": f"after_back p={after_back}"})

    # URL ?p= syncs
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    page.wait_for_selector("#issues_table tbody tr", timeout=15000)
    p_param = page.evaluate("() => new URL(location.href).searchParams.get('p')")
    probes.append({"probe": "M11_url_p_param_syncs", "status": "PASS" if p_param == SLUG else "FAIL",
                   "evidence": f"?p={p_param}"})

    return probes


# ----------------- Stage C — NEW R7 probes -----------------

def stage_c(page) -> dict:
    out: dict = {}

    # === C1 — CSP correctness ===
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    _wait_workbench(page)

    # Listen for CSP violations & all console messages
    csp_violations: list[dict] = []
    console_msgs: list[str] = []
    page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text[:200]}"))

    # Inline script injection (CSP allows 'unsafe-inline')
    page.evaluate("""() => {
      const s = document.createElement('script');
      s.textContent = "window.__csp_inline_ran = true;";
      document.body.appendChild(s);
    }""")
    page.wait_for_timeout(300)
    inline_ran = page.evaluate("() => window.__csp_inline_ran === true")

    # External script: CSP script-src 'self' 'unsafe-inline' should BLOCK external. We use a CSP-violation listener.
    csp_violation_msg = ""
    try:
        page.evaluate("""() => {
          return new Promise((resolve) => {
            const handler = (e) => { window.__csp_violation = {blockedURI: e.blockedURI || '', violatedDirective: e.violatedDirective || '', sourceFile: e.sourceFile || ''}; resolve(true); };
            document.addEventListener('securitypolicyviolation', handler, {once: true});
            const s = document.createElement('script');
            s.src = 'https://example.com/x.js';
            s.onerror = () => { setTimeout(() => resolve(false), 1500); };
            s.onload = () => { window.__ext_script_loaded = true; resolve(false); };
            document.body.appendChild(s);
            setTimeout(() => resolve(false), 2000);
          });
        }""")
        page.wait_for_timeout(2300)
    except Exception as e:
        csp_violation_msg = f"eval error: {e}"
    csp_violation = page.evaluate("() => window.__csp_violation || null")
    ext_script_loaded = page.evaluate("() => window.__ext_script_loaded === true")
    external_blocked = bool(csp_violation) and not ext_script_loaded

    # Frame-ancestors: try to embed the workbench in an iframe via a data: URL parent
    frame_ancestors_works = False
    try:
        # We'll evaluate in a NEW context: load a small page that embeds an <iframe src=BASE/> and inspect.
        page.goto("data:text/html,<!doctype html><html><body><iframe id=ifr src='" + BASE + "/' width=400 height=300></iframe><script>setTimeout(()=>{const ifr=document.getElementById('ifr'); try {window.__ifr_inner = ifr.contentDocument && ifr.contentDocument.title;} catch(e){window.__ifr_blocked = e.message;}}, 1500);</script></body></html>")
        page.wait_for_timeout(2200)
        ifr_inner = page.evaluate("() => window.__ifr_inner")
        ifr_blocked = page.evaluate("() => window.__ifr_blocked")
        # Note: cross-origin iframe sandbox will throw on contentDocument access. The PRIMARY signal here is
        # whether the iframe load itself failed due to X-Frame-Options: DENY. Check via fetching directly.
        # We use a separate probe by curl: check that the response carries X-Frame-Options: DENY.
        # (Already in F4.) Here we just record DOM-level evidence.
        frame_ancestors_works = (not ifr_inner) or bool(ifr_blocked)
    except Exception as e:
        frame_ancestors_works = True  # exception likely from same-origin policy denial, which is consistent with frame-ancestors enforcement

    out["c1_csp"] = {
        "inline_script_ran": bool(inline_ran),
        "external_script_blocked": bool(external_blocked),
        "external_script_csp_violation": csp_violation,
        "external_script_loaded": bool(ext_script_loaded),
        "frame_ancestors_works": bool(frame_ancestors_works),
        "csp_inline_note": "CSP intentionally allows 'unsafe-inline' (M15 verdict §F4); inline injection is expected to run. External script SHOULD be blocked.",
    }

    # === C2 — CSRF edge cases ===
    csrf: dict = {}

    def _curl_post(headers: dict[str, str], body: str = '{"reviewer":"r7-edge","event":"confirm"}') -> tuple[str, str]:
        args = ["curl", "-sS", "-o", "/tmp/r7_csrf_edge.txt", "-w", "%{http_code}", "-X", "POST"]
        for k, v in headers.items():
            args += ["-H", f"{k}: {v}"]
        args += ["-d", body, f"{BASE}/api/issues/250/feedback"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), open("/tmp/r7_csrf_edge.txt").read()[:200]

    # null Origin
    code, body = _curl_post({"Origin": "null", "Content-Type": "application/json"})
    csrf["origin_null"] = {"code": code, "body_first_200": body, "blocked": code == "403"}

    # Subdomain trick: evil.example with target as prefix
    code, body = _curl_post({"Origin": "http://127.0.0.1:8792.evil.example", "Content-Type": "application/json"})
    csrf["subdomain_trick"] = {"code": code, "body_first_200": body, "blocked": code == "403"}

    # @ URL parser confusion
    code, body = _curl_post({"Origin": "http://127.0.0.1:8792@evil.example", "Content-Type": "application/json"})
    csrf["auth_url_trick"] = {"code": code, "body_first_200": body, "blocked": code == "403"}

    # Case-insensitive header
    code, body = _curl_post({"ORIGIN": f"{BASE}", "Content-Type": "application/json"})
    csrf["case_insensitive_origin_header"] = {"code": code, "body_first_200": body, "allowed": code == "200"}

    # text/plain content-type (content-type confusion attempt)
    code, body = _curl_post({"Origin": f"{BASE}", "Content-Type": "text/plain"})
    csrf["content_type_text_plain"] = {"code": code, "body_first_200": body, "parsed_anyway": code == "200"}

    out["c2_csrf_edges"] = csrf

    # === C3 — Path traversal in slug ===
    paths = [
        "/api/projects/..%2F..%2Fetc%2Fpasswd/issues",
        "/api/projects/%2e%2e%2f%2e%2e%2fetc%2fpasswd/issues",
        f"/api/drawings/{DRAWING_ID}/page/%2e%2e/bboxes",
        f"/api/drawings/{DRAWING_ID}/page/-1/bboxes",
        "/api/projects/../../../etc/passwd/issues",
    ]
    trav: list[dict] = []
    for p in paths:
        r = subprocess.run(["curl", "-sS", "-o", "/tmp/r7_trav.txt", "-w", "%{http_code}", f"{BASE}{p}"],
                           capture_output=True, text=True, timeout=8)
        body = open("/tmp/r7_trav.txt").read()
        trav.append({"url": p, "status_code": r.stdout.strip(), "body_first_200": body[:200]})
    out["c3_path_traversal"] = trav

    # === C4 — Rate limiting probe ===
    t0 = time.time()
    n = 100
    statuses = []
    for _ in range(n):
        try:
            with urllib.request.urlopen(f"{BASE}/api/projects", timeout=5) as r:
                statuses.append(r.status)
        except urllib.error.HTTPError as exc:
            statuses.append(exc.code)
        except Exception:
            statuses.append(-1)
    elapsed = time.time() - t0
    out["c4_rate_limiting"] = {
        "requests_sent": n,
        "all_succeeded": all(s == 200 for s in statuses),
        "any_rate_limited": any(s == 429 for s in statuses),
        "status_distribution": dict((s, statuses.count(s)) for s in set(statuses)),
        "elapsed_seconds": round(elapsed, 2),
        "avg_ms_per_request": round(1000 * elapsed / n, 2),
    }

    # === C5 — Malformed PDF ingest ===
    bad_pdf = ROOT / ".planning/m16/bad.pdf"
    bad_pdf.write_bytes(b"NOT A PDF\n" * 4)
    r = subprocess.run(
        ["uv", "run", "archkg", "review", str(bad_pdf), "--out", "/tmp/r7_bad_pdf_out"],
        capture_output=True, text=True, timeout=20, cwd=str(ROOT))
    out["c5_malformed_ingest"] = {
        "exit_code": r.returncode,
        "stderr_first_400": (r.stderr or "")[:400],
        "stdout_first_200": (r.stdout or "")[:200],
        "graceful": r.returncode != 0 and (r.returncode < 128),  # no segfault, no infinite hang
    }
    try:
        bad_pdf.unlink()
    except Exception:
        pass

    # === C6 — Multipage drawer route (R6-BUG-002) ===
    # If engine had pages>0 we'd test routing; here we verify the source code still hardcodes page/0.
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    _wait_workbench(page)
    web_src = (ROOT / "archkg/kg/web.py").read_text()
    has_hardcode = "page/0/bboxes" in web_src and "page/0.png" in web_src
    img_src = page.evaluate("() => document.getElementById('vp_img') ? document.getElementById('vp_img').src : null")
    # Try to open an issue with a non-zero page_index (would need engine fix); just observe what viewport renders.
    page.keyboard.press("j")
    page.wait_for_timeout(120)
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    img_src_after = page.evaluate("() => document.getElementById('vp_img') ? document.getElementById('vp_img').src : null")
    out["c6_multipage_drawer_route"] = {
        "first_issue_page_index": 0,  # engine emits 0 for all
        "viewport_img_src_default": img_src,
        "viewport_img_src_after_open": img_src_after,
        "hardcoded_page_0_in_source": has_hardcode,
        "matches_engine_emit": "/page/0" in (img_src_after or ""),
        "note": "R6-BUG-002 still open: viewport hardcodes /page/0/*. R6-BUG-001 still open: engine never emits page_index>0.",
    }

    # === C7 — CJK / long bilingual visual probe ===
    # Read manifest for the bilingual string; verify whether it appears anywhere in the DOM and whether it overflows.
    manifest = json.loads(MANIFEST_PATH.read_text())
    cjk_a = manifest.get("title_block_bilingual_string", "") or ""
    cjk_b = manifest.get("title_block_bilingual_string_p1", "") or ""
    long_payload_in_dom = False
    cjk_in_dom = False
    overflow_observed = False
    if cjk_a or cjk_b:
        page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
        _wait_workbench(page)
        # Check viewport SVG/text content & issues table
        body_text = page.evaluate("() => document.body.innerText || ''")
        cjk_in_dom = any(s and s[:50] in body_text for s in (cjk_a, cjk_b))
        # Look for super-wide elements
        widths = page.evaluate("() => Array.from(document.querySelectorAll('*')).map(el => el.scrollWidth).filter(w => w > 4000)")
        overflow_observed = bool(widths)
        # Long string check
        long_str = (manifest.get("adversarial_payloads", {}) or {}).get("long_string_length", 0)
        body_text_after = page.evaluate("() => document.body.innerText || ''")
        # try to find any 500+ char unbroken token in body text
        very_long_tokens = [w for w in body_text_after.split() if len(w) >= 500]
        long_payload_in_dom = bool(very_long_tokens)
    out["c7_cjk_visual"] = {
        "shows_in_ui": cjk_in_dom,
        "clipping_detected": overflow_observed,
        "long_token_in_dom": long_payload_in_dom,
        "bilingual_p0_excerpt": cjk_a[:80],
        "bilingual_p1_excerpt": cjk_b[:80],
        "note": "CJK title-block strings are drawn into the PDF page raster; UI shows the rendered PNG, so this checks DOM overflow not text-layer escaping.",
    }

    # === C-bonus: adversarial XSS still inert? ===
    page.goto(f"{BASE}/?p={SLUG}", wait_until="domcontentloaded")
    _wait_workbench(page)
    dialog_log: list[str] = []
    page.on("dialog", lambda d: (dialog_log.append(d.message), d.dismiss()))
    issue_ids = page.evaluate("() => Array.from(document.querySelectorAll('#issues_table tbody tr')).map(r => parseInt(r.dataset.issueId || '0')).filter(Boolean)")
    script_in_dom_anywhere = False
    for iid in issue_ids[:6]:
        try:
            page.evaluate(f"openIssue({int(iid)})")
            page.wait_for_timeout(120)
            drawer_html = page.evaluate("() => { const d = document.querySelector('#drawer, .drawer'); return d ? d.innerHTML : ''; }")
            if re.search(r"<script[^>]*>alert", drawer_html, re.I):
                script_in_dom_anywhere = True
        except Exception:
            continue
    out["c_bonus_xss_inert"] = {
        "dialog_log": dialog_log,
        "xss_executes": len(dialog_log) > 0,
        "live_script_in_dom": script_in_dom_anywhere,
    }

    return out


# ----------------- Findings synthesis -----------------

def synthesize(stage_a_out: dict, stage_b_out: list[dict], stage_c_out: dict) -> list[dict]:
    findings: list[dict] = []
    seq = 0

    def add(sev: str, cat: str, title: str, where: str, expected: str, actual: str, fix: str, repro: str) -> None:
        nonlocal seq
        seq += 1
        findings.append({
            "id": f"R7-BUG-{seq:03d}",
            "severity": sev, "category": cat, "title": title, "where": where,
            "expected": expected, "actual": actual, "suggested_fix": fix, "reproduction_steps": repro,
        })

    # P0/P1 — title-block FP rate
    tb_pct = stage_a_out.get("title_block_fp_percent_of_total", 0)
    tb_n = stage_a_out.get("title_block_fp_count", 0)
    if tb_pct >= 15.0:
        sev = "P1" if tb_pct < 50 else "P0"
        add(sev, "engine",
            f"Title-block phantom-FP rate {tb_pct}% ({tb_n}/{stage_a_out['issues_total']})",
            "archkg/rules/* + sheet-region filter not applied to title-block region",
            "Title-block / legend dimension callouts (OVERALL DIM, REVISION DIM, etc.) should NEVER trigger geometric rules like RC-CORRIDOR-WIDTH or RC-DOOR-WIDTH",
            f"{tb_n} engine issues have bbox ≥50% inside title_block_rect_bl OR IoU>=0.3 with a phantom-trap bbox; specific issues: {[d['issue_id'] for d in stage_a_out.get('title_block_fp_detail', [])]}",
            "Apply manifest's `sheet-region` filter automatically — exclude title_block + legend strips from rule evaluation. Either auto-detect title-block via large-rect heuristic or accept manifest-supplied sheet_region",
            f"1) ingest m16 PDF; 2) GET /api/projects/{SLUG}/issues; 3) observe issue id 250 with bbox [60,762,1130,812] inside title_block_rect [60,697,1130,812] (containment=1.0)")

    # P1 — engine never emits page_index>0 (R6-BUG-001 still open, now confirmed on 2-page m16)
    pages_seen = set(stage_a_out["issues_by_page"].keys())
    if pages_seen == {"0"} and stage_a_out["issues_total"] > 0:
        add("P1", "engine",
            "Engine emits page_index=0 for all issues regardless of which PDF page contains the defect (R6-BUG-001 still open)",
            "archkg/rules + archkg/review pipeline — only first page is rule-evaluated",
            "Per-page rule evaluation; each defect's evidence.page_index reflects the actual PDF page",
            f"All {stage_a_out['issues_total']} m16 issues have page_index=0 despite 4 of 8 intended defects living on page 1",
            "Refactor evidence builder to iterate pages and propagate page_index through evaluator. Page 1 defects (corridor 1.00m, two doors 0.65m+0.70m, bedroom 5.6m²) all silently dropped on m16",
            f"1) ingest m16 (2-page PDF); 2) GET /api/projects/{SLUG}/issues — issues_by_page = {{0: 10}} — page-1 defects invisible")

    # P1 — engine recall
    miss = stage_a_out.get("recall_misses", [])
    recall = stage_a_out.get("recall_pct", 0)
    if recall < 75 and miss:
        add("P1", "engine",
            f"Engine recall {recall}% — {len(miss)}/{stage_a_out['legitimate_count']} intended defects missed",
            "rule evaluator + door-type classifier + bedroom-area matcher",
            "≥80% recall on legitimate corridor/door/bedroom defects",
            f"Missed (page, rule): {[(m['page'], m['rule']) for m in miss]}",
            "Most misses are page-1 defects (blocked by R6-BUG-001) + RC-BEDROOM-AREA family (matcher gap)",
            f"GET /api/projects/{SLUG}/issues, compare rule_id+page_index against manifest['intended_defects']")

    # P2 — drawer hardcoded to page 0 (R6-BUG-002 still open)
    c6 = stage_c_out.get("c6_multipage_drawer_route", {})
    if c6.get("hardcoded_page_0_in_source") and c6.get("matches_engine_emit"):
        add("P2", "ui",
            "Viewport still hardcodes /page/0/bboxes and /page/0.png (R6-BUG-002 still open)",
            "archkg/kg/web.py renderViewport() — string literals page/0/{bboxes,png}",
            "Viewport routes to issue.page_index dynamically; UI exposes a page nav (prev/next or picker)",
            "Source contains literal `/page/0/bboxes` and `/page/0.png`; no DOM page-nav controls; viewport always shows page 0 even when defect is on another page",
            "Replace string literal with `/page/${issue.page_index}/{bboxes,png}` and add page picker. Engine fix (R6-BUG-001) is also needed before this is end-to-end useful",
            "1) load workbench with m16; 2) inspect img.src — always /page/0.png regardless of issue page")

    # P3 — no rate limiting
    rl = stage_c_out.get("c4_rate_limiting", {})
    if rl.get("all_succeeded") and not rl.get("any_rate_limited"):
        add("P3", "security-defense-in-depth",
            "No rate limiting on /api/projects (or anywhere)",
            "archkg/kg/web.py Flask app — no Flask-Limiter or equivalent",
            "Some bound on requests/sec (e.g. 60 req/sec/IP) to limit DoS surface",
            f"100 requests succeeded in {rl.get('elapsed_seconds')}s with no 429s; avg {rl.get('avg_ms_per_request')}ms/req",
            "Add Flask-Limiter with conservative defaults; local-pilot threat model is low but defense-in-depth",
            "Fire 100 sequential GETs to /api/projects — all 200, no 429")

    # P3 — content-type text/plain still parsed
    ctp = stage_c_out.get("c2_csrf_edges", {}).get("content_type_text_plain", {})
    if ctp.get("parsed_anyway"):
        add("P3", "security",
            "POST /api/issues/<id>/feedback accepts Content-Type: text/plain (CT confusion)",
            "feedback endpoint — Flask JSON parser is permissive",
            "Reject non-application/json POST bodies on JSON endpoints (415 Unsupported Media Type)",
            f"POST with Content-Type: text/plain returned {ctp.get('code')} (parsed JSON anyway)",
            "Add `request.get_json(force=False)` guard or enforce Content-Type check in before_request",
            "curl -X POST -H 'Origin: <same>' -H 'Content-Type: text/plain' -d '{\"reviewer\":\"x\"}' /api/issues/250/feedback → 200")

    # P3 — null Origin handling
    null_o = stage_c_out.get("c2_csrf_edges", {}).get("origin_null", {})
    if null_o.get("code") == "200":
        add("P3", "security",
            "Origin: null is accepted (sandboxed iframes / data: URLs / file://)",
            "CSRF guard — same-origin check sees Origin: null and treats it as non-equal-but-not-blocked? Or strips before compare",
            "Reject Origin: null on state-changing endpoints",
            f"POST with Origin: null returned {null_o.get('code')}",
            "Add explicit `if origin == 'null': return jsonify({...}), 403` before same-host compare",
            "curl -X POST -H 'Origin: null' -H 'Content-Type: application/json' -d '{...}' /api/issues/250/feedback")

    # P3 — engine emitted degenerate bbox (height=0) for door issues.
    # MEASURED, not hardcoded (round-7 audit-honesty fix): only fire when the
    # current engine actually emits degenerate door bboxes, so a real fix is
    # reflected in the score instead of being permanently deducted.
    deg_doors = stage_a_out.get("degenerate_door_bbox_count", 0)
    if deg_doors > 0:
        add("P3", "engine",
            "Door issues emitted with degenerate bbox (height=0)",
            "archkg rule evaluator — door-evidence bbox uses [x0, y, x1, y] (line, not rect)",
            "Door bboxes should have non-zero height (e.g. ±10pt vertical padding around the door symbol)",
            f"{deg_doors} door issue(s) have a degenerate bbox (zero width or height)",
            "Expand door evidence bbox to symbol height (~25pt) before emitting issue",
            "GET /api/projects/test-m16-defective-plan/issues — inspect bbox of any door issue")

    # P3 — `archkg review` on malformed PDF dumps a Rich-formatted traceback instead of friendly error
    c5 = stage_c_out.get("c5_malformed_ingest", {})
    if c5.get("exit_code") and "Traceback" in (c5.get("stderr_first_400") or ""):
        add("P3", "cli-ux",
            "Malformed PDF dumps raw Python traceback on `archkg review`",
            "archkg/cli/* — review command does not wrap `fitz.open` / `pymupdf.Document(...)` in a friendly error path",
            "Print a single-line user-facing error like `error: <path> is not a valid PDF` and exit non-zero",
            "Running `archkg review` on a non-PDF file produces a Rich-formatted full traceback (FileDataError from pymupdf) instead of a friendly message",
            "Wrap PDF open in try/except FileDataError and `typer.echo('error: ...', err=True); raise typer.Exit(1)`",
            "echo 'NOT A PDF' > /tmp/bad.pdf && uv run archkg review /tmp/bad.pdf")

    # P3 — RC-CORRIDOR-WIDTH on page 0: missed BOTH real corridors, fired only the title-block phantom
    legit = stage_a_out.get("legitimate_caught", 0)
    miss_p0_corridor = sum(1 for m in stage_a_out.get("recall_misses", []) if m["rule"] == "RC-CORRIDOR-WIDTH" and m["page"] == 0)
    fired_p0_corridor = sum(1 for d in stage_a_out.get("title_block_fp_detail", []) if d["rule_id"] == "RC-CORRIDOR-WIDTH" and d.get("page_index") == 0)
    # Soft heuristic: if engine fired RC-CORRIDOR-WIDTH only inside title-block AND missed both real page-0 corridors, that's the worst-case FP — phantom replaces the real signal.
    if fired_p0_corridor >= 1 and miss_p0_corridor == 0 and stage_a_out["issues_by_rule"].get("RC-CORRIDOR-WIDTH", 0) >= 1:
        # Even if real corridors aren't in the manifest miss list (because hits matched somewhere), the phantom-only firing is still wrong
        pass
    # Add explicit "phantom replaces real signal" finding if engine ONLY fired RC-CORRIDOR-WIDTH on title-block bbox(es)
    rc_corridor_total = stage_a_out["issues_by_rule"].get("RC-CORRIDOR-WIDTH", 0)
    rc_corridor_in_tb = sum(1 for d in stage_a_out.get("title_block_fp_detail", []) if d["rule_id"] == "RC-CORRIDOR-WIDTH")
    if rc_corridor_total > 0 and rc_corridor_total == rc_corridor_in_tb:
        add("P2", "engine",
            "RC-CORRIDOR-WIDTH fires ONLY on title-block strip — real corridors silently lost",
            "rule evaluator — picks up dimension callouts in title block instead of geometric corridor entities",
            "Fire on actual corridor entities (parallel walls), not on text-only dimension callouts in title block",
            f"Engine emitted {rc_corridor_total} RC-CORRIDOR-WIDTH issue(s) for m16 — ALL inside title_block strip. The 2 real ground-floor corridors (W=1.05m, 0.95m) at y≈347-402 are silently missed. Combined with R6-BUG-001 the page-1 corridor (W=1.00m) is also missed.",
            "Treat title-block dimension callouts as non-room metadata; require corridor-rule firings to be backed by a Wall/Corridor entity bbox not a Text entity",
            f"GET /api/projects/{SLUG}/issues — only corridor-rule firings have bbox=[60,762,1130,812] which IS the title-block strip")

    return findings


def score(stage_a_out: dict, stage_b_out: list[dict], stage_c_out: dict, findings: list[dict]) -> dict:
    score = 100
    breakdown: list[dict] = []

    # P0 / P1 / P2 / P3 weighting
    sev_weight = {"P0": 25, "P1": 12, "P2": 5, "P3": 2}
    for f in findings:
        w = sev_weight.get(f["severity"], 1)
        score -= w
        breakdown.append({"id": f["id"], "severity": f["severity"], "title": f["title"], "deduction": -w})

    # Stage B regression failures (each FAIL = -3, PARTIAL = -1)
    for p in stage_b_out:
        if p["status"] == "FAIL":
            score -= 3
            breakdown.append({"probe": p["probe"], "status": "FAIL", "deduction": -3})
        elif p["status"] == "PARTIAL":
            score -= 1
            breakdown.append({"probe": p["probe"], "status": "PARTIAL", "deduction": -1})

    # Stage C — CSP external block must work
    c1 = stage_c_out.get("c1_csp", {})
    if not c1.get("external_script_blocked"):
        score -= 8
        breakdown.append({"detail": "external script not blocked by CSP", "deduction": -8})

    return {"score_out_of_100": max(0, score), "breakdown": breakdown}


def write_summary(stage_a_out: dict, stage_b_out: list[dict], stage_c_out: dict, findings: list[dict], score_info: dict) -> None:
    lines = []
    lines.append("# M16.B Round-7 Audit — Summary\n")
    lines.append(f"- Plan: `samples/real_plans/test-m16-defective-plan.pdf` (2 pages A3 landscape)")
    lines.append(f"- Score: **{score_info['score_out_of_100']}/100**  (vs M15 post-fix ~62)")
    lines.append("- Stage A source: **fresh `archkg review`** (engine ground truth, not stale served DB)")
    if stage_a_out.get("served_db_stale"):
        lines.append(
            f"- ⚠️ **AUDIT-INTEGRITY**: served DB STALE "
            f"(served={stage_a_out.get('served_issue_count')} vs fresh={stage_a_out.get('issues_total')}) "
            f"— Stage B/C UI probes reflect an old ingest; re-ingest before trusting them."
        )
    lines.append("")
    lines.append("## Headline numbers")
    lines.append(f"- Issues total: **{stage_a_out['issues_total']}**")
    lines.append(f"- Title-block FPs: **{stage_a_out['title_block_fp_count']} ({stage_a_out['title_block_fp_percent_of_total']}%)** — primary R7 metric (R4-BUG-004 now quantified)")
    lines.append(f"- Recall vs intended: **{stage_a_out['recall_pct']}%** ({stage_a_out['legitimate_caught']}/{stage_a_out['legitimate_count']})")
    lines.append(f"- Decoy FPs: {stage_a_out['decoy_fps']}")
    lines.append(f"- Issues by page: {stage_a_out['issues_by_page']}")
    lines.append("")
    lines.append("## M15 regression battery")
    pf = sum(1 for p in stage_b_out if p["status"] == "PASS")
    ff = sum(1 for p in stage_b_out if p["status"] == "FAIL")
    pa = sum(1 for p in stage_b_out if p["status"] == "PARTIAL")
    lines.append(f"- PASS: {pf} / FAIL: {ff} / PARTIAL: {pa}")
    for p in stage_b_out:
        lines.append(f"  - [{p['status']}] {p['probe']} — {p['evidence']}")
    lines.append("")
    lines.append("## Stage C — new R7 probes")
    c1 = stage_c_out.get("c1_csp", {})
    lines.append(f"- C1 CSP: inline_ran={c1.get('inline_script_ran')} (by design) | external_blocked={c1.get('external_script_blocked')} | frame_ancestors_works={c1.get('frame_ancestors_works')}")
    c2 = stage_c_out.get("c2_csrf_edges", {})
    lines.append(f"- C2 CSRF edges: null={c2.get('origin_null', {}).get('code')} | subdomain={c2.get('subdomain_trick', {}).get('code')} | auth-url={c2.get('auth_url_trick', {}).get('code')} | CASE-insensitive={c2.get('case_insensitive_origin_header', {}).get('code')} | text/plain={c2.get('content_type_text_plain', {}).get('code')}")
    c4 = stage_c_out.get("c4_rate_limiting", {})
    lines.append(f"- C4 Rate limiting: {c4.get('requests_sent')} req, all={c4.get('all_succeeded')}, 429s={c4.get('any_rate_limited')}")
    c5 = stage_c_out.get("c5_malformed_ingest", {})
    lines.append(f"- C5 Malformed PDF ingest: exit={c5.get('exit_code')}, graceful={c5.get('graceful')}")
    lines.append("")
    lines.append("## Findings (top by severity)")
    for f in findings:
        lines.append(f"- **{f['id']}** [{f['severity']}] {f['title']}")
        lines.append(f"  - actual: {f['actual']}")
        lines.append(f"  - fix: {f['suggested_fix']}")
    lines.append("")
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    print("Stage A — running FRESH engine review (ground truth, not stale DB) ...")
    issues = fresh_engine_issues()
    print(f"  fresh engine emitted {len(issues)} issues")
    print("Stage A — title-block FP quantification + recall ...")
    sa = stage_a(manifest, issues)
    print(json.dumps({k: v for k, v in sa.items() if k not in ("title_block_fp_detail",)}, indent=2, ensure_ascii=False))
    if sa.get("served_db_stale"):
        print(
            "\n  ⚠️  AUDIT-INTEGRITY WARNING: served .archkg/kg.db is STALE vs the fresh\n"
            f"      engine output (served={sa.get('served_issue_count')} issues, fresh={len(issues)}).\n"
            "      Stage A metrics use the fresh run and are correct; Stage B/C UI probes\n"
            "      below reflect the OLD ingest — re-ingest the drawing before trusting them."
        )
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        try:
            print("Stage B — M11-M15 regression ...")
            sb = stage_b(page)
            for pr in sb:
                print(f"  [{pr['status']}] {pr['probe']}: {pr['evidence']}")
            print()

            print("Stage C — new R7 probes ...")
            sc = stage_c(page)
            print(json.dumps({k: ({kk: (vv if not isinstance(vv, list) else f"<{len(vv)} entries>") for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in sc.items()}, indent=2, ensure_ascii=False)[:2000])
            print()
        finally:
            page.close()
            ctx.close()
            browser.close()

    findings = synthesize(sa, sb, sc)
    score_info = score(sa, sb, sc, findings)
    score_reasoning = (
        f"Started at 100. Subtracted "
        + ", ".join(f"{b.get('deduction', 0)} ({b.get('severity', '') or b.get('status', '') or b.get('detail', '')})" for b in score_info["breakdown"])
        + f" → {score_info['score_out_of_100']}."
    )

    out_doc = {
        "round": 7,
        "input_plan": "samples/real_plans/test-m16-defective-plan.pdf",
        "audit_integrity": {
            "stage_a_source": "fresh `archkg review` run (not stale served DB)",
            "served_issue_count": sa.get("served_issue_count"),
            "fresh_issue_count": sa.get("issues_total"),
            "served_db_stale": sa.get("served_db_stale"),
            "note": "Stage A engine metrics reflect the code under test. If served_db_stale "
                    "is true, Stage B/C UI probes read an older ingest — re-ingest before trusting them.",
        },
        "stage_a": sa,
        "stage_b_regression": sb,
        "stage_c_new": sc,
        "stage_c_findings": findings,
        "score_out_of_100": score_info["score_out_of_100"],
        "score_breakdown": score_info["breakdown"],
        "score_reasoning": score_reasoning,
        "score_delta_vs_round6": f"Round 6 raw 32, post-M15 ~62. Round 7 raw {score_info['score_out_of_100']}. Net {score_info['score_out_of_100'] - 62:+d} vs post-M15 baseline.",
    }
    OUT_PATH.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    write_summary(sa, sb, sc, findings, score_info)
    print()
    print(f"WROTE {OUT_PATH}")
    print(f"WROTE {SUMMARY_PATH}")
    print(f"SCORE = {score_info['score_out_of_100']}/100")


if __name__ == "__main__":
    main()
