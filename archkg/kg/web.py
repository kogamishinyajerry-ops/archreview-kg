"""Local Flask web UI for the ArchReview-KG knowledge graph (M5.D).

Five reviewer flows:
1. Project list (`GET /api/projects`)
2. Drawing browser per project (`GET /api/projects/<slug>/drawings`)
3. Rule trigger heatmap (`GET /api/heatmap`)
4. Issue lineage (`GET /api/issues/<id>`)
5. Reviewer annotation (`POST /api/issues/<id>/feedback`)

The UI is vanilla JS, no build step, no React. `run_e2e_smoke()` exercises
all five flows via Flask's test client and returns timings consumed by the
`web_ui_e2e` scoring dimension.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from archkg.kg.feedback import add_feedback
from archkg.kg.pdf_render import render_page, resolve_pdf_for_drawing
from archkg.kg.store import KGStore, default_db_path

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ArchReview-KG Workbench</title>
  <style>
    :root {
      --bg: #f5f5f7; --surface: #ffffff; --border: #d2d2d7;
      --text: #1d1d1f; --muted: #6e6e73; --accent: #0071e3; --accent-dim: #e8f1fc;
      --ok: #28a745; --warn: #ff9500; --bad: #ff3b30; --info: #5e5ce6;
    }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
           margin: 0; padding: 0; background: var(--bg); color: var(--text);
           font-size: 14px; line-height: 1.5; }
    header { background: #1d1d1f; color: white; padding: 14px 28px;
             display: flex; align-items: center; justify-content: space-between; }
    header h1 { font-size: 16px; margin: 0; font-weight: 600; letter-spacing: -0.01em; }
    header .brand { display: flex; align-items: center; gap: 12px; }
    header .logo { width: 28px; height: 28px; border-radius: 6px; background: linear-gradient(135deg, #0071e3 0%, #5e5ce6 100%); }
    nav a { color: rgba(255,255,255,0.85); margin-left: 20px; text-decoration: none; font-size: 13px; }
    nav a:hover { color: white; }
    .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 20px 28px; }
    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
             overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .panel-h { padding: 12px 16px; border-bottom: 1px solid var(--border);
               font-size: 12px; font-weight: 600; color: var(--muted);
               text-transform: uppercase; letter-spacing: 0.06em;
               display: flex; align-items: center; justify-content: space-between; }
    .panel-h .meta { font-weight: 400; text-transform: none; letter-spacing: 0; }
    table { border-collapse: collapse; width: 100%; }
    th, td { padding: 8px 14px; text-align: left; font-size: 13px;
             border-bottom: 1px solid #f0f0f3; }
    th { background: #fafafa; font-weight: 600; color: var(--muted); font-size: 11px;
         text-transform: uppercase; letter-spacing: 0.06em; }
    tbody tr { cursor: pointer; transition: background 0.1s; }
    tbody tr:hover { background: var(--accent-dim); }
    tbody tr.active { background: var(--accent-dim); }
    .status { display: inline-block; padding: 2px 8px; border-radius: 12px;
              font-size: 11px; font-weight: 600; }
    .status.candidate { background: rgba(255, 149, 0, 0.15); color: #b25800; }
    .status.confirmed { background: rgba(40, 167, 69, 0.15); color: #1d6f30; }
    .status.rejected  { background: rgba(255, 59, 48, 0.15); color: #b51910; }
    .status.needs_info{ background: rgba(94, 92, 230, 0.15); color: #3530a8; }
    .status.resolved  { background: rgba(0, 113, 227, 0.15); color: #004b96; }
    .status.superseded{ background: rgba(110, 110, 115, 0.15); color: #3a3a3c; }
    /* Issue drawer */
    .drawer-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.35);
                   opacity: 0; pointer-events: none; transition: opacity 0.2s; z-index: 10; }
    .drawer-mask.open { opacity: 1; pointer-events: auto; }
    .drawer { position: fixed; top: 0; right: 0; height: 100vh; width: 560px;
              background: var(--surface); border-left: 1px solid var(--border);
              box-shadow: -8px 0 24px rgba(0,0,0,0.12);
              transform: translateX(100%); transition: transform 0.25s ease;
              z-index: 11; overflow-y: auto; }
    .drawer.open { transform: translateX(0); }
    .drawer-h { padding: 18px 22px; border-bottom: 1px solid var(--border);
                position: sticky; top: 0; background: var(--surface); z-index: 1; }
    .drawer-h .close { position: absolute; top: 18px; right: 22px;
                       background: none; border: none; font-size: 22px;
                       color: var(--muted); cursor: pointer; }
    .drawer-h h3 { margin: 0 0 6px 0; font-size: 16px; font-weight: 600; }
    .drawer-h .sub { color: var(--muted); font-size: 12px; font-family: ui-monospace, "SF Mono", monospace; }
    .drawer-body { padding: 18px 22px; }
    .drawer-body .row { display: grid; grid-template-columns: 110px 1fr; gap: 12px;
                        padding: 8px 0; border-bottom: 1px solid #f0f0f3; }
    .drawer-body .row .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    .drawer-body .row .v { font-size: 13px; word-break: break-word; }
    .drawer-body .row .v code { background: #f5f5f7; padding: 1px 5px; border-radius: 4px;
                                font-family: ui-monospace, "SF Mono", monospace; font-size: 12px; }
    .evidence { background: #1d1d1f; color: #f5f5f7; padding: 14px;
                border-radius: 8px; font-family: ui-monospace, "SF Mono", monospace;
                font-size: 11px; white-space: pre-wrap; overflow-x: auto;
                max-height: 220px; overflow-y: auto; }
    .feedback-h { margin: 22px 0 10px 0; font-size: 12px; color: var(--muted);
                  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
    .feedback-list { list-style: none; padding: 0; margin: 0; }
    .feedback-list li { padding: 8px 0; border-bottom: 1px solid #f0f0f3; font-size: 13px;
                        display: flex; gap: 8px; align-items: baseline; }
    .feedback-list .who { font-family: ui-monospace, "SF Mono", monospace; font-size: 12px;
                         color: var(--muted); min-width: 130px; }
    .feedback-list .what { font-weight: 500; }
    .feedback-list .when { font-size: 11px; color: var(--muted); margin-left: auto; font-variant-numeric: tabular-nums; }
    .actions { display: flex; gap: 8px; margin: 18px 0 8px 0; }
    .btn { padding: 8px 14px; font-size: 13px; font-weight: 500; border-radius: 8px;
           border: 1px solid var(--border); background: var(--surface); cursor: pointer;
           transition: all 0.1s; }
    .btn:hover { background: #f5f5f7; }
    .btn.confirm { border-color: var(--ok); color: var(--ok); }
    .btn.confirm:hover { background: var(--ok); color: white; }
    .btn.reject { border-color: var(--bad); color: var(--bad); }
    .btn.reject:hover { background: var(--bad); color: white; }
    .btn.needs_info { border-color: var(--info); color: var(--info); }
    .btn.needs_info:hover { background: var(--info); color: white; }
    .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(20px);
             background: #1d1d1f; color: white; padding: 10px 18px; border-radius: 8px;
             font-size: 13px; opacity: 0; transition: all 0.2s; z-index: 20;
             box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
    .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    .empty { padding: 28px; color: var(--muted); text-align: center; font-size: 13px; }
    .full-row { grid-column: 1 / -1; }
    .badge-row { display: flex; gap: 6px; flex-wrap: wrap; }
    .badge-row span { background: #f5f5f7; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
    /* PDF viewport — M7.W1 */
    #viewport_panel { grid-column: 1 / -1; }
    .viewport-wrap { position: relative; padding: 12px;
                     background: #fafafa; max-height: 720px; overflow: auto;
                     display: flex; align-items: flex-start; justify-content: center; }
    .viewport-stack { position: relative; display: inline-block; max-width: 100%; }
    .viewport-stack img { display: block; max-width: 100%; max-height: 680px; width: auto; height: auto; }
    .viewport-stack svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
    .viewport-stack svg rect { pointer-events: auto; cursor: pointer; transition: stroke-width 0.1s, fill-opacity 0.1s; }
    .viewport-stack svg rect.bbox-candidate  { fill: rgba(255,149,0,0.10); stroke: var(--warn); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-confirmed  { fill: rgba(40,167,69,0.10); stroke: var(--ok); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-rejected   { fill: rgba(255,59,48,0.10); stroke: var(--bad); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-needs_info { fill: rgba(94,92,230,0.10); stroke: var(--info); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-resolved   { fill: rgba(0,113,227,0.10); stroke: var(--accent); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-superseded { fill: rgba(110,110,115,0.10); stroke: var(--muted); stroke-width: 1.6; }
    .viewport-stack svg rect.bbox-hot { stroke-width: 4; fill-opacity: 0.28; }
    .viewport-stack svg text.bbox-label { font: 600 12px ui-monospace, "SF Mono", monospace;
                                          fill: white; paint-order: stroke; stroke: rgba(0,0,0,0.6); stroke-width: 3; }
    .viewport-header { padding: 10px 16px; display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--muted); border-bottom: 1px solid var(--border); }
    .viewport-header .bbox-count { font-weight: 600; color: var(--text); }
    .viewport-header code { font-family: ui-monospace, "SF Mono", monospace; font-size: 11px; }
    .viewport-empty { padding: 60px 28px; text-align: center; color: var(--muted); font-size: 13px; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo"></div>
      <h1>ArchReview-KG Workbench</h1>
    </div>
    <nav>
      <a href="#projects">Projects</a>
      <a href="#heatmap">Rule Heatmap</a>
      <a href="/api/projects" target="_blank">Raw API</a>
    </nav>
  </header>

  <div class="layout">
    <section class="panel">
      <div class="panel-h">
        <span>Projects</span>
        <span class="meta" id="proj_meta">loading…</span>
      </div>
      <table id="projects_table">
        <thead><tr><th>Slug</th><th>Name</th><th style="text-align:right">Drawings</th><th style="text-align:right">Issues</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-h">
        <span>Rule Trigger Heatmap</span>
        <span class="meta" id="heat_meta">loading…</span>
      </div>
      <table id="heatmap_table">
        <thead><tr><th>Rule</th><th style="text-align:right">Total</th><th style="text-align:right">Confirmed</th><th style="text-align:right">Rejected</th><th style="text-align:right">Candidate</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>

    <section class="panel" id="viewport_panel" style="display: none;">
      <div class="panel-h">
        <span>Drawing viewport · <code id="vp_slug"></code></span>
        <span class="meta" id="vp_meta">no drawing loaded</span>
      </div>
      <div class="viewport-header" id="vp_header_inline" style="display:none">
        <span class="bbox-count" id="vp_bbox_count">0 bboxes</span>
        <span>·</span>
        <span>page <code id="vp_page_label">0</code></span>
        <span>·</span>
        <span>native <code id="vp_dim_label">?×?</code> pts</span>
        <span style="margin-left:auto">click a bbox or an issue row to sync</span>
      </div>
      <div class="viewport-wrap" id="vp_wrap">
        <div class="viewport-empty" id="vp_empty">Select a project to load its drawing.</div>
        <div class="viewport-stack" id="vp_stack" style="display: none;">
          <img id="vp_img" alt="drawing">
          <svg id="vp_svg" preserveAspectRatio="xMidYMid meet"></svg>
        </div>
      </div>
    </section>

    <section class="panel full-row" id="issues_panel" style="grid-column: 1 / -1; display: none;">
      <div class="panel-h">
        <span>Issues for project <code id="issues_slug"></code></span>
        <span class="meta" id="issues_meta"></span>
      </div>
      <table id="issues_table">
        <thead><tr><th>#</th><th>Rule</th><th>Severity</th><th>Status</th><th>Message</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>
  </div>

  <div class="drawer-mask" id="mask"></div>
  <aside class="drawer" id="drawer">
    <div class="drawer-h">
      <button class="close" aria-label="close" onclick="closeDrawer()">×</button>
      <h3 id="d_title">Issue</h3>
      <div class="sub" id="d_sub"></div>
    </div>
    <div class="drawer-body" id="d_body"></div>
  </aside>

  <div class="toast" id="toast"></div>

  <script>
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    async function fetchJSON(url, opts) {
      const res = await fetch(url, opts);
      if (!res.ok) throw new Error(`${url} → ${res.status}`);
      return await res.json();
    }

    function toast(msg) {
      const t = $('#toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 1800);
    }

    function statusBadge(s) {
      return `<span class="status ${s}">${s}</span>`;
    }

    let projectsData = [];
    let currentSlug = null;

    async function loadProjects() {
      projectsData = await fetchJSON('/api/projects');
      const tbody = $('#projects_table tbody');
      tbody.innerHTML = '';
      let totalIssues = 0;
      for (const p of projectsData) {
        totalIssues += p.issue_count;
        const tr = document.createElement('tr');
        tr.dataset.slug = p.slug;
        tr.innerHTML = `<td><code>${p.slug}</code></td><td>${p.name || ''}</td>
                        <td style="text-align:right">${p.drawing_count}</td>
                        <td style="text-align:right">${p.issue_count}</td>`;
        tr.onclick = () => openProject(p.slug);
        tbody.appendChild(tr);
      }
      $('#proj_meta').textContent = `${projectsData.length} projects · ${totalIssues} issues`;
    }

    async function loadHeatmap() {
      const data = await fetchJSON('/api/heatmap');
      const tbody = $('#heatmap_table tbody');
      tbody.innerHTML = '';
      let totalRules = 0;
      let totalCandidate = 0, totalConfirmed = 0, totalRejected = 0;
      for (const row of data) {
        totalRules++;
        totalCandidate += row.candidate;
        totalConfirmed += row.confirmed;
        totalRejected += row.rejected;
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${row.rule_id}</code></td>
                        <td style="text-align:right">${row.total}</td>
                        <td style="text-align:right; color: var(--ok); font-weight: 600">${row.confirmed}</td>
                        <td style="text-align:right; color: var(--bad); font-weight: 600">${row.rejected}</td>
                        <td style="text-align:right; color: var(--warn); font-weight: 600">${row.candidate}</td>`;
        tbody.appendChild(tr);
      }
      $('#heat_meta').textContent = `${totalRules} rules · ${totalConfirmed} confirmed · ${totalRejected} rejected · ${totalCandidate} candidate`;
    }

    // Viewport state — set when openProject loads a drawing.
    let currentDrawingId = null;
    let currentPageIndex = 0;
    let currentPageW = null;
    let currentPageH = null;
    let issueRowByIssueId = new Map();   // issue_id -> <tr>
    let bboxRectByIssueId = new Map();   // issue_id -> <rect>

    async function openProject(slug) {
      currentSlug = slug;
      $$('#projects_table tbody tr').forEach((tr) => {
        tr.classList.toggle('active', tr.dataset.slug === slug);
      });
      // Load issues
      const data = await fetchJSON(`/api/projects/${slug}/issues`);
      const panel = $('#issues_panel');
      panel.style.display = 'block';
      $('#issues_slug').textContent = slug;
      const tbody = panel.querySelector('tbody');
      tbody.innerHTML = '';
      issueRowByIssueId = new Map();
      const counts = { candidate: 0, confirmed: 0, rejected: 0, needs_info: 0, resolved: 0, superseded: 0 };
      for (const i of data.issues) {
        counts[i.status] = (counts[i.status] || 0) + 1;
        const tr = document.createElement('tr');
        tr.dataset.issueId = String(i.id);
        tr.innerHTML = `<td><code>${i.source_issue_id || i.id}</code></td>
                        <td><code>${i.rule_id || '<none>'}</code></td>
                        <td>${i.severity || ''}</td>
                        <td>${statusBadge(i.status)}</td>
                        <td>${(i.message || '').slice(0, 120)}</td>`;
        tr.onclick = () => { highlightBboxForIssue(i.id); openIssue(i.id); };
        tr.onmouseenter = () => highlightBboxForIssue(i.id, /*scroll=*/false);
        tr.onmouseleave = () => unhighlightAllBboxes();
        tbody.appendChild(tr);
        issueRowByIssueId.set(i.id, tr);
      }
      const parts = Object.entries(counts).filter(([_,v]) => v>0)
        .map(([k,v]) => `${v} ${k}`).join(' · ');
      $('#issues_meta').textContent = `${data.issues.length} issues · ${parts}`;
      // Load drawing viewport
      await loadViewportForProject(slug);
      $('#viewport_panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function loadViewportForProject(slug) {
      // Find the drawing_id for this project (first drawing).
      const draws = await fetchJSON(`/api/projects/${slug}/drawings`);
      $('#vp_slug').textContent = slug;
      const stack = $('#vp_stack');
      const empty = $('#vp_empty');
      const panel = $('#viewport_panel');
      panel.style.display = 'block';
      bboxRectByIssueId = new Map();
      if (!draws.drawings || draws.drawings.length === 0) {
        stack.style.display = 'none';
        empty.style.display = 'block';
        empty.textContent = 'This project has no drawings registered.';
        $('#vp_meta').textContent = 'no drawings';
        $('#vp_header_inline').style.display = 'none';
        return;
      }
      const d = draws.drawings[0];
      currentDrawingId = d.id;
      currentPageIndex = 0;
      // Probe the bbox endpoint first — if PDF isn't resolvable we surface a clear empty state.
      let bboxData;
      try {
        bboxData = await fetchJSON(`/api/drawings/${d.id}/page/0/bboxes`);
      } catch (e) {
        stack.style.display = 'none';
        empty.style.display = 'block';
        empty.innerHTML = `<strong>No source PDF for this drawing.</strong><br>
          Commit a PDF to <code>samples/real_plans/${slug}.pdf</code> to enable the viewport.<br>
          <small style="color:var(--muted)">drawing_id=${d.id} · path=${d.source_path || '(unset)'}</small>`;
        $('#vp_meta').textContent = `drawing #${d.id} · no source PDF`;
        $('#vp_header_inline').style.display = 'none';
        return;
      }
      currentPageW = bboxData.page_width_pts;
      currentPageH = bboxData.page_height_pts;
      // Image
      $('#vp_img').src = `/api/drawings/${d.id}/page/0.png`;
      // SVG overlay
      const svg = $('#vp_svg');
      svg.setAttribute('viewBox', `0 0 ${currentPageW} ${currentPageH}`);
      svg.innerHTML = '';
      const xmlns = 'http://www.w3.org/2000/svg';
      for (const bb of bboxData.bboxes) {
        const rect = document.createElementNS(xmlns, 'rect');
        rect.setAttribute('x', bb.x0);
        rect.setAttribute('y', bb.y0);
        rect.setAttribute('width', Math.max(2, bb.x1 - bb.x0));
        rect.setAttribute('height', Math.max(2, bb.y1 - bb.y0));
        rect.setAttribute('class', `bbox-${bb.status}`);
        rect.dataset.issueId = String(bb.issue_id);
        rect.dataset.ruleId = bb.rule_id || '';
        rect.dataset.status = bb.status;
        rect.addEventListener('mouseenter', () => highlightIssueRowForBbox(bb.issue_id));
        rect.addEventListener('mouseleave', () => unhighlightAllIssueRows());
        rect.addEventListener('click', () => { highlightBboxForIssue(bb.issue_id); openIssue(bb.issue_id); });
        svg.appendChild(rect);
        bboxRectByIssueId.set(bb.issue_id, rect);
      }
      stack.style.display = 'inline-block';
      empty.style.display = 'none';
      $('#vp_meta').textContent =
        `drawing #${d.id} · page ${0 + 1} · ${bboxData.bboxes.length} bboxes`;
      $('#vp_bbox_count').textContent = `${bboxData.bboxes.length} bboxes`;
      $('#vp_page_label').textContent = '0';
      $('#vp_dim_label').textContent =
        `${Math.round(currentPageW)}×${Math.round(currentPageH)}`;
      $('#vp_header_inline').style.display = 'flex';
    }

    function highlightBboxForIssue(issueId, scroll = true) {
      unhighlightAllBboxes();
      const r = bboxRectByIssueId.get(issueId);
      if (!r) return;
      r.classList.add('bbox-hot');
      if (scroll) {
        // Scroll the rect into view inside the viewport-wrap.
        const wrap = $('#vp_wrap');
        const stack = $('#vp_stack');
        const img = $('#vp_img');
        if (currentPageW && img.naturalWidth) {
          // Estimate visible y of rect center in wrap-scroll coords.
          const yCenterPts = (parseFloat(r.getAttribute('y')) +
            parseFloat(r.getAttribute('height')) / 2);
          const imgRect = img.getBoundingClientRect();
          const wrapRect = wrap.getBoundingClientRect();
          const ratio = yCenterPts / currentPageH;
          const yCenterPx = (imgRect.top - wrapRect.top + wrap.scrollTop) +
                            ratio * imgRect.height;
          wrap.scrollTo({ top: yCenterPx - wrap.clientHeight / 2, behavior: 'smooth' });
        }
      }
    }

    function unhighlightAllBboxes() {
      $$('#vp_svg rect').forEach((r) => r.classList.remove('bbox-hot'));
    }

    function highlightIssueRowForBbox(issueId) {
      unhighlightAllIssueRows();
      const tr = issueRowByIssueId.get(issueId);
      if (!tr) return;
      tr.classList.add('active');
      tr.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function unhighlightAllIssueRows() {
      $$('#issues_table tbody tr.active').forEach((t) => t.classList.remove('active'));
    }

    async function openIssue(id) {
      const data = await fetchJSON(`/api/issues/${id}`);
      $('#d_title').innerHTML = `${statusBadge(data.status)} <code>${data.rule_id || ''}</code>`;
      $('#d_sub').textContent = `issue #${data.source_issue_id || data.id} · project ${data.project_slug}`;
      const body = $('#d_body');
      const ev = data.evidence ? JSON.stringify(data.evidence, null, 2) : '(no evidence payload)';
      const fbList = (data.feedback_events || []).map((fe) => {
        const when = fe.created_at ? new Date(fe.created_at).toISOString().slice(0,16).replace('T',' ') : '';
        return `<li><span class="who">${fe.reviewer_id || '<system>'}</span>
                    <span class="what">${fe.event_type}</span>
                    <span class="when">${when}</span></li>`;
      }).join('');
      body.innerHTML = `
        <div class="row"><div class="k">Severity</div><div class="v">${data.severity || ''}</div></div>
        <div class="row"><div class="k">Source</div><div class="v"><code>${data.source_path || '(unspecified)'}</code></div></div>
        <div class="row"><div class="k">Message</div><div class="v">${data.message || ''}</div></div>
        <div class="row"><div class="k">Bbox</div><div class="v"><code>${data.bbox ? JSON.stringify(data.bbox) : '—'}</code></div></div>
        <div class="feedback-h">Evidence</div>
        <pre class="evidence">${ev}</pre>
        <div class="feedback-h">Reviewer feedback (${(data.feedback_events||[]).length})</div>
        <ul class="feedback-list">${fbList || '<li style="color:var(--muted)">no events yet</li>'}</ul>
        <div class="feedback-h">Record verdict</div>
        <div class="actions">
          <button class="btn confirm" onclick="postFeedback(${data.id}, 'confirm')">✓ Confirm</button>
          <button class="btn reject" onclick="postFeedback(${data.id}, 'reject')">✗ Reject</button>
          <button class="btn needs_info" onclick="postFeedback(${data.id}, 'needs_info')">? Needs info</button>
        </div>
      `;
      $('#mask').classList.add('open');
      $('#drawer').classList.add('open');
    }

    function closeDrawer() {
      $('#mask').classList.remove('open');
      $('#drawer').classList.remove('open');
    }

    async function postFeedback(issueId, eventType) {
      try {
        await fetchJSON(`/api/issues/${issueId}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reviewer: 'demo-reviewer-live', event: eventType }),
        });
        toast(`Recorded: ${eventType}`);
        await openIssue(issueId);  // refresh detail
        if (currentSlug) await openProject(currentSlug);  // refresh list status
      } catch (e) {
        toast(`Error: ${e.message}`);
      }
    }

    $('#mask').onclick = closeDrawer;
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

    // ----- Auto-driven demo (?demo=1) for the M6 screencapture --------------
    // Sequences a deterministic walkthrough so ffmpeg AVFoundation can capture
    // real product interaction without a human at the keyboard.
    function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

    function flashRow(tr, ms) {
      tr.classList.add('active');
      tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return sleep(ms);
    }

    function captionOverlay(text, ms) {
      let el = document.querySelector('#demo-caption');
      if (!el) {
        el = document.createElement('div');
        el.id = 'demo-caption';
        el.style.cssText = 'position:fixed;left:50%;bottom:32px;transform:translateX(-50%);' +
          'background:rgba(29,29,31,0.92);color:white;padding:14px 24px;border-radius:12px;' +
          'font-size:18px;font-weight:500;letter-spacing:0.01em;z-index:30;' +
          'box-shadow:0 8px 24px rgba(0,0,0,0.28);max-width:900px;text-align:center;' +
          'opacity:0;transition:opacity 0.3s;';
        document.body.appendChild(el);
      }
      el.textContent = text;
      el.style.opacity = '1';
      return sleep(ms).then(() => { el.style.opacity = '0'; });
    }

    async function runDemo() {
      await sleep(1200);
      await captionOverlay('ArchReview-KG Workbench — 33 plans, 148 issues, 25 rules', 4000);
      await sleep(600);

      // Drill into the demo project.
      const targetSlug = 'cambridge-343medford-overview';
      const row = document.querySelector(`#projects_table tbody tr[data-slug="${targetSlug}"]`);
      if (row) {
        await captionOverlay('Drill into a project — workbench loads its drawing + issues', 3800);
        await flashRow(row, 1000);
        row.click();
        await sleep(3500); // wait for PDF render
      }

      // Linger on the viewport so the audience sees the real plan with bbox overlays.
      await captionOverlay('Real public-record plan PDF · bbox overlays linked to issue rows', 4500);
      await sleep(2000);

      // Hover sync — pick an issue row, watch the bbox light up.
      const issueRows = document.querySelectorAll('#issues_table tbody tr');
      let targetIssueRow = null;
      for (const tr of issueRows) {
        if (tr.textContent.includes('RC-CORRIDOR-WIDTH')) { targetIssueRow = tr; break; }
      }
      if (!targetIssueRow) targetIssueRow = issueRows[0];
      if (targetIssueRow) {
        await captionOverlay('Click an issue → the matching bbox lights up on the plan', 4200);
        targetIssueRow.dispatchEvent(new Event('mouseenter'));
        await sleep(2000);
        targetIssueRow.click();
        await sleep(3000);
      }

      await captionOverlay('Issue drawer: rule + clause + evidence + reviewer feedback history', 4800);
      await sleep(2200);
      await captionOverlay('Reviewer disagreements preserved — never overwritten', 4500);
      await sleep(1500);

      // Record a confirm verdict — real POST to /api/issues/<id>/feedback.
      const confirmBtn = document.querySelector('#drawer .btn.confirm');
      if (confirmBtn) {
        await captionOverlay('Record a verdict — writes a feedback_event into the live KG', 3800);
        confirmBtn.click();
        await sleep(2800);
      }

      await captionOverlay('Verdict committed · audit trail preserved · heatmap count ticks up', 4500);
      await sleep(2000);
      closeDrawer();
      await sleep(900);

      window.scrollTo({ top: 0, behavior: 'smooth' });
      await captionOverlay('Open source · Offline · Honest · Every finding traces to its evidence', 5500);
      await sleep(2500);
      await captionOverlay('archreview-kg · M7 product demo', 3500);
    }

    const params = new URLSearchParams(location.search);
    if (params.get('demo') === '1') {
      // Wait for the project + heatmap tables to be populated before starting.
      const start = async () => {
        // Poll for projects to load
        for (let i = 0; i < 50; i++) {
          if (document.querySelectorAll('#projects_table tbody tr').length > 0) break;
          await sleep(120);
        }
        runDemo();
      };
      start();
    }

    loadProjects();
    loadHeatmap();
  </script>
</body>
</html>"""


def create_app(db_path: Path | None = None) -> Flask:
    """Build the Flask app. Each request opens its own KGStore connection."""

    app = Flask(__name__)
    app.config["KG_DB_PATH"] = str(db_path or default_db_path(Path.cwd()))

    def _store() -> KGStore:
        return KGStore(Path(app.config["KG_DB_PATH"]), create=False)

    @app.get("/")
    def index() -> tuple[str, int, dict[str, str]]:
        return INDEX_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/api/projects")
    def list_projects() -> Any:
        with _store() as store:
            rows = store._conn.execute(
                "SELECT p.slug, p.name, "
                "(SELECT COUNT(*) FROM drawing d WHERE d.project_id = p.id) AS drawing_count, "
                "(SELECT COUNT(*) FROM issue i JOIN run rn ON i.run_id = rn.id WHERE rn.project_id = p.id) AS issue_count "
                "FROM project p ORDER BY p.slug"
            ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/api/projects/<slug>/drawings")
    def project_drawings(slug: str) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT id FROM project WHERE slug = ?", (slug,)
            ).fetchone()
            if not row:
                return jsonify({"error": "project not found", "slug": slug}), 404
            project_id = int(row["id"])
            drawings = [
                dict(r)
                for r in store._conn.execute(
                    "SELECT id, source_path, page_count, created_at FROM drawing WHERE project_id = ? ORDER BY id",
                    (project_id,),
                ).fetchall()
            ]
        return jsonify({"project": slug, "drawings": drawings})

    @app.get("/api/projects/<slug>/issues")
    def project_issues(slug: str) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT id FROM project WHERE slug = ?", (slug,)
            ).fetchone()
            if not row:
                return jsonify({"error": "project not found", "slug": slug}), 404
            project_id = int(row["id"])
            issues = [
                {
                    "id": int(r["id"]),
                    "source_issue_id": r["source_issue_id"],
                    "rule_id": r["rule_label"],
                    "status": r["status"],
                    "severity": r["severity"],
                    "message": r["message"],
                }
                for r in store._conn.execute(
                    "SELECT i.id, i.source_issue_id, i.status, i.severity, i.message, "
                    "r.rule_id AS rule_label "
                    "FROM issue i "
                    "JOIN run rn ON i.run_id = rn.id "
                    "LEFT JOIN rule r ON i.rule_id = r.id "
                    "WHERE rn.project_id = ? "
                    "ORDER BY i.id",
                    (project_id,),
                ).fetchall()
            ]
        return jsonify({"project": slug, "issues": issues})

    # M7.W1 — PDF viewport endpoints.
    @app.get("/api/drawings/<int:drawing_id>/page/<int:page_index>.png")
    def drawing_page_png(drawing_id: int, page_index: int) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT d.source_path AS source_path, p.slug AS slug "
                "FROM drawing d JOIN project p ON d.project_id = p.id "
                "WHERE d.id = ?",
                (drawing_id,),
            ).fetchone()
            if not row:
                return jsonify({"error": "drawing not found", "id": drawing_id}), 404
        repo_root = Path(app.config["KG_DB_PATH"]).parent.parent
        pdf = resolve_pdf_for_drawing(repo_root, row["slug"], row["source_path"])
        if not pdf:
            return (
                jsonify(
                    {
                        "error": "no committed source PDF for this drawing",
                        "drawing_id": drawing_id,
                        "project_slug": row["slug"],
                        "hint": "commit a PDF to samples/real_plans/{slug}.pdf",
                    }
                ),
                404,
            )
        try:
            rp = render_page(pdf, page_index)
        except (IndexError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 404
        # Cache-Control: rendered PNGs are content-addressed, safe to cache.
        return Response(
            rp.image_bytes,
            mimetype="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @app.get("/api/drawings/<int:drawing_id>/page/<int:page_index>/bboxes")
    def drawing_page_bboxes(drawing_id: int, page_index: int) -> Any:
        """Return bbox + issue metadata for SVG overlay sync with the PNG.

        Response shape:
          {
            "drawing_id": N,
            "page_index": N,
            "page_width_pts":  float,   # PDF coordinate space — use as SVG viewBox width
            "page_height_pts": float,   # PDF coordinate space — use as SVG viewBox height
            "image_width_px":  int,     # rendered PNG dimensions (informational)
            "image_height_px": int,
            "bboxes": [{ "issue_id", "source_issue_id", "rule_id", "status",
                         "severity", "x0", "y0", "x1", "y1" }, ...]
          }
        """

        with _store() as store:
            drow = store._conn.execute(
                "SELECT d.source_path AS source_path, p.slug AS slug "
                "FROM drawing d JOIN project p ON d.project_id = p.id "
                "WHERE d.id = ?",
                (drawing_id,),
            ).fetchone()
            if not drow:
                return jsonify({"error": "drawing not found", "id": drawing_id}), 404
            # Issues on this drawing with bbox + matching page_index in evidence_json.
            irows = store._conn.execute(
                "SELECT i.id, i.source_issue_id, i.status, i.severity, i.bbox_json, "
                "i.evidence_json, r.rule_id AS rule_id "
                "FROM issue i "
                "JOIN run rn ON i.run_id = rn.id "
                "LEFT JOIN rule r ON i.rule_id = r.id "
                "WHERE rn.drawing_id = ? AND i.bbox_json IS NOT NULL "
                "ORDER BY i.id",
                (drawing_id,),
            ).fetchall()
        repo_root = Path(app.config["KG_DB_PATH"]).parent.parent
        pdf = resolve_pdf_for_drawing(repo_root, drow["slug"], drow["source_path"])
        if not pdf:
            return (
                jsonify(
                    {
                        "error": "no committed source PDF for this drawing",
                        "drawing_id": drawing_id,
                        "project_slug": drow["slug"],
                    }
                ),
                404,
            )
        try:
            rp = render_page(pdf, page_index)
        except (IndexError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 404

        bboxes: list[dict[str, Any]] = []
        for r in irows:
            try:
                bb = json.loads(r["bbox_json"])
                ev = json.loads(r["evidence_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(bb, list) or len(bb) < 4:
                continue
            evidence_page = ev.get("page_index", 0)
            if evidence_page != page_index:
                continue
            bboxes.append(
                {
                    "issue_id": int(r["id"]),
                    "source_issue_id": r["source_issue_id"],
                    "rule_id": r["rule_id"],
                    "status": r["status"],
                    "severity": r["severity"],
                    "x0": float(bb[0]),
                    "y0": float(bb[1]),
                    "x1": float(bb[2]),
                    "y1": float(bb[3]),
                }
            )
        return jsonify(
            {
                "drawing_id": drawing_id,
                "page_index": page_index,
                "page_width_pts": rp.page_width_pts,
                "page_height_pts": rp.page_height_pts,
                "image_width_px": rp.image_width_px,
                "image_height_px": rp.image_height_px,
                "bboxes": bboxes,
            }
        )

    @app.get("/api/heatmap")
    def heatmap() -> Any:
        with _store() as store:
            rows = store._conn.execute(
                "SELECT r.rule_id AS rule_id, "
                "COUNT(i.id) AS total, "
                "SUM(CASE WHEN i.status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed, "
                "SUM(CASE WHEN i.status = 'rejected' THEN 1 ELSE 0 END) AS rejected, "
                "SUM(CASE WHEN i.status = 'candidate' THEN 1 ELSE 0 END) AS candidate "
                "FROM rule r LEFT JOIN issue i ON i.rule_id = r.id "
                "GROUP BY r.rule_id "
                "HAVING total > 0 "
                "ORDER BY total DESC, r.rule_id"
            ).fetchall()
        return jsonify(
            [
                {
                    "rule_id": r["rule_id"],
                    "total": int(r["total"]),
                    "confirmed": int(r["confirmed"] or 0),
                    "rejected": int(r["rejected"] or 0),
                    "candidate": int(r["candidate"] or 0),
                }
                for r in rows
            ]
        )

    @app.get("/api/issues/<int:issue_id>")
    def issue_detail(issue_id: int) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT i.*, r.rule_id AS rule_label, p.slug AS project_slug, "
                "d.source_path AS source_path "
                "FROM issue i "
                "JOIN run rn ON i.run_id = rn.id "
                "JOIN project p ON rn.project_id = p.id "
                "LEFT JOIN drawing d ON rn.drawing_id = d.id "
                "LEFT JOIN rule r ON i.rule_id = r.id "
                "WHERE i.id = ?",
                (issue_id,),
            ).fetchone()
            if not row:
                return jsonify({"error": "issue not found", "id": issue_id}), 404
            feedback_rows = store._conn.execute(
                "SELECT fe.event_type, fe.created_at, fe.payload_json, rv.reviewer_id "
                "FROM feedback_event fe LEFT JOIN reviewer rv ON fe.reviewer_id = rv.id "
                "WHERE fe.issue_id = ? ORDER BY fe.id",
                (issue_id,),
            ).fetchall()
        return jsonify(
            {
                "id": int(row["id"]),
                "source_issue_id": row["source_issue_id"],
                "status": row["status"],
                "severity": row["severity"],
                "message": row["message"],
                "rule_id": row["rule_label"],
                "project_slug": row["project_slug"],
                "source_path": row["source_path"],
                "bbox": json.loads(row["bbox_json"]) if row["bbox_json"] else None,
                "evidence": json.loads(row["evidence_json"]) if row["evidence_json"] else None,
                "feedback_events": [
                    {
                        "event_type": fr["event_type"],
                        "reviewer_id": fr["reviewer_id"],
                        "created_at": fr["created_at"],
                        "payload": json.loads(fr["payload_json"] or "{}"),
                    }
                    for fr in feedback_rows
                ],
            }
        )

    @app.post("/api/issues/<int:issue_id>/feedback")
    def post_feedback(issue_id: int) -> Any:
        data: Mapping[str, Any] = request.get_json(silent=True) or {}
        reviewer = data.get("reviewer")
        event = data.get("event")
        if not reviewer or not event:
            return jsonify({"error": "reviewer and event are required"}), 400
        with _store() as store:
            try:
                fb_id = add_feedback(
                    store,
                    issue_id=issue_id,
                    reviewer_id=str(reviewer),
                    event_type=str(event),
                    payload=data.get("payload"),
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        return jsonify({"feedback_event_id": fb_id})

    # M6.W4 — pilot deployment error handlers. Surface 404/500 as friendly
    # JSON for API routes and an HTML stub for the SPA root.
    @app.errorhandler(404)
    def _not_found(err):  # type: ignore[no-untyped-def]
        from flask import request as _request

        if _request.path.startswith("/api/"):
            return jsonify({"error": "not_found", "detail": str(err)}), 404
        return _error_response(
            "Not Found",
            404,
            "请求的资源不存在 / Requested resource not found.",
        )

    @app.errorhandler(500)
    def _server_error(err):  # type: ignore[no-untyped-def]
        return _error_response(
            "Internal Server Error",
            500,
            "服务器内部错误，请查看终端日志 / Internal error; check the server log.",
        )

    return app


def _error_response(title: str, status: int, message: str):  # type: ignore[no-untyped-def]
    """Render a minimal HTML error page for the pilot UI (M6.W4)."""

    body = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:-apple-system,system-ui,sans-serif;"
        "max-width:560px;margin:80px auto;padding:0 24px;color:#1d1d1f}"
        "h1{font-size:2rem;margin-bottom:0.5rem}p{color:#86868b;line-height:1.5}"
        "a{color:#0071e3;text-decoration:none}a:hover{text-decoration:underline}</style>"
        f"</head><body><h1>{status} — {title}</h1><p>{message}</p>"
        "<p><a href='/'>← 返回首页 / Back to home</a></p></body></html>"
    )
    return body, status, {"Content-Type": "text/html; charset=utf-8"}


def _time_flow(name: str, fn: Any) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        resp = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = int(resp.status_code) if hasattr(resp, "status_code") else 500
        return {
            "name": name,
            "p95_ms": round(elapsed_ms, 3),
            "passed": 200 <= status < 300,
            "status_code": status,
        }
    except Exception as exc:
        return {
            "name": name,
            "p95_ms": round((time.perf_counter() - start) * 1000, 3),
            "passed": False,
            "status_code": 0,
            "error": repr(exc),
        }


def run_e2e_smoke(db_path: Path | None = None) -> dict[str, Any]:
    """Exercise all five flows via Flask's test client. Used by scorer."""

    app = create_app(db_path)
    client = app.test_client()

    flows: list[dict[str, Any]] = []
    flows.append(_time_flow("index_html", lambda: client.get("/")))
    flows.append(_time_flow("project_list", lambda: client.get("/api/projects")))

    # Discover one project + one issue to drive remaining flows
    proj_resp = client.get("/api/projects")
    project_slug = None
    if proj_resp.status_code == 200:
        data = proj_resp.get_json() or []
        if data:
            project_slug = data[0]["slug"]
    if project_slug:
        flows.append(
            _time_flow(
                "project_drawings",
                lambda: client.get(f"/api/projects/{project_slug}/drawings"),
            )
        )
    else:
        flows.append({"name": "project_drawings", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no projects in KG"})

    flows.append(_time_flow("heatmap", lambda: client.get("/api/heatmap")))

    # Find any issue id
    issue_id = None
    db = db_path or default_db_path(Path.cwd())
    if db.exists():
        with KGStore(db, create=False) as store:
            row = store._conn.execute("SELECT id FROM issue LIMIT 1").fetchone()
            if row:
                issue_id = int(row["id"])
    if issue_id:
        flows.append(_time_flow("issue_detail", lambda: client.get(f"/api/issues/{issue_id}")))
        flows.append(
            _time_flow(
                "annotate_feedback",
                lambda: client.post(
                    f"/api/issues/{issue_id}/feedback",
                    json={"reviewer": "smoke-runner", "event": "needs_info"},
                ),
            )
        )
    else:
        flows.append({"name": "issue_detail", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no issues in KG"})
        flows.append({"name": "annotate_feedback", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no issues in KG"})

    return {"db_path": str(db_path or default_db_path(Path.cwd())), "flows": flows}


__all__ = ["INDEX_HTML", "create_app", "run_e2e_smoke"]
