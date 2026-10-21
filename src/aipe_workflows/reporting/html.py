"""Render the review package as an AIPE-Doc styled HTML document (A4 print layout).

The page structure follows AIPE-Doc's ``templates/document.html`` (``.document-shell``,
``.doc-page`` articles with page header/footer, section labels, tables, figures and
callouts). AIPE-Doc's stylesheets, script and brand assets are copied next to the
report when an AIPE-Doc checkout is found (sibling ``AIPE-Doc`` or ``AIPE_DOC_DIR``);
otherwise a minimal built-in stylesheet keeps the document readable.
"""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from ..verification.gates import GATE_ORDER

ASSETS = ["base.css", "document.css", "template.js", "aipe-logo.svg", "spirit-connect.svg"]
FALLBACK_CSS = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;color:#0b0b0b;background:#fcfcfb;margin:0}
.document-pages{max-width:960px;margin:0 auto;padding:24px}
.doc-page{background:#fff;border:1px solid #e4e3df;padding:32px;margin:0 0 24px}
.page-header,.page-footer{display:flex;justify-content:space-between;font-size:11px;color:#52514e}
.section-label{font-size:11px;letter-spacing:.08em;color:#52514e;margin:16px 0 4px}
table{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0 16px}th,td{border-bottom:1px solid #e4e3df;padding:4px 6px;text-align:left;vertical-align:top}
.callout{border-left:3px solid #2a78d6;padding:8px 12px;background:#f3f6fb;margin:12px 0}.tag{border:1px solid #e4e3df;border-radius:12px;padding:2px 8px;font-size:11px}
figure{margin:12px 0}figure img{max-width:100%}figcaption{font-size:11px;color:#52514e}code{font-size:11px}
"""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _fmt(value: Any, digits: int = 5) -> str:
    if isinstance(value, bool) or value is None:
        return _esc(value)
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return _esc(value)


def _table(headers: list[str], rows: list[list[Any]], caption: str = "") -> str:
    head = "".join(f"<th scope=\"col\">{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_fmt(c)}</td>" for c in row) + "</tr>" for row in rows)
    cap = f"<caption>{_esc(caption)}</caption>" if caption else ""
    return f"<section class=\"table-scroll\"><table>{cap}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></section>"


def find_doc_dir(explicit: Optional[str | Path] = None, start: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("AIPE_DOC_DIR"):
        candidates.append(Path(os.environ["AIPE_DOC_DIR"]))
    here = (start or Path.cwd()).resolve()
    for parent in [here, *here.parents]:
        candidates.append(parent / "AIPE-Doc")
        candidates.append(parent / "repos" / "AIPE-Doc")
    for candidate in candidates:
        if (candidate / "assets" / "document.css").is_file():
            return candidate.resolve()
    return None


def render_html(report: dict, workflow: dict, out_dir: Path, doc_dir: Optional[Path] = None) -> str:
    out_dir = Path(out_dir)
    assets_dir = out_dir / "assets"
    doc_dir = doc_dir or find_doc_dir(start=out_dir)
    styled = False
    if doc_dir:
        assets_dir.mkdir(parents=True, exist_ok=True)
        for name in ASSETS:
            src = doc_dir / "assets" / name
            if src.is_file():
                shutil.copyfile(src, assets_dir / name)
        styled = (assets_dir / "document.css").is_file()
    run = report["run"]
    spec = report["specification"]
    pages: list[str] = []
    page_no = [0]

    def page(section_label: str, title: str, body: str, eyebrow: str = "ENGINEERING REVIEW PACKAGE") -> None:
        page_no[0] += 1
        pages.append(
            f"<article class=\"doc-page\" id=\"page-{page_no[0]}\">"
            f"<header class=\"page-header\"><img class=\"logo\" src=\"assets/aipe-logo.svg\" alt=\"AIPE\"><span class=\"eyebrow\">{_esc(eyebrow)}</span></header>"
            f"<div class=\"section-label\">{_esc(section_label)}</div><h2>{_esc(title)}</h2>{body}"
            f"<footer class=\"page-footer\"><span>AIPE Labs / AIPE-Workflows</span><span>{_esc(run['run_id'])} / {page_no[0]:02d}</span></footer></article>")

    # Cover
    req = spec.get("requirements", {})
    cover = (f"<div class=\"kicker\"><span class=\"eyebrow\">AIPE / WORKFLOW RUN</span><span class=\"tag\">status: {_esc(run['status'])}</span></div>"
             f"<h1>{_esc(workflow.get('name', run['workflow_id']))}</h1>"
             f"<p class=\"lead\">{_esc(spec.get('project', {}).get('name', ''))} — {_esc(req.get('nominal_power_W'))} W, {_esc(req.get('input_voltage_V'))} V → {_esc(req.get('output_voltage_V'))} V, {_esc(req.get('switching_frequency_Hz'))} Hz</p>"
             f"<dl class=\"cover-meta\"><div><dt>Run</dt><dd>{_esc(run['run_id'])}</dd></div><div><dt>Workflow</dt><dd>{_esc(run['workflow_id'])}</dd></div>"
             f"<div><dt>Created</dt><dd>{_esc(run['created_at'])}</dd></div><div><dt>Specification hash</dt><dd><code>{_esc(run['spec_sha256'][:16])}</code></dd></div></dl>"
             "<section class=\"callout\"><strong>Scope of this document</strong><p>Generated from the run directory only: executed solver results, "
             "their numerical checks, verification gate statuses and the Engineering State evidence. Nothing here is a measurement or a hardware qualification; "
             "gates that were not executed are shown as not run.</p></section>")
    page_no[0] += 1
    pages.append(f"<article class=\"doc-page cover\" id=\"cover\"><header class=\"page-header\"><img class=\"logo\" src=\"assets/aipe-logo.svg\" alt=\"AIPE\"><span class=\"eyebrow\">ENGINEERING REVIEW PACKAGE</span></header>{cover}"
                 f"<footer class=\"page-footer\"><span>AIPE Labs / AIPE-Workflows</span><span>{_esc(run['run_id'])} / 01</span></footer></article>")
    # Requirements
    body = _table(["Quantity", "Value"], [[k, v] for k, v in req.items()], "Requested ratings")
    if spec.get("constraints"):
        body += _table(["Id", "Description", "Basis"], [[c["id"], c["description"], c.get("basis", "assumption")] for c in spec["constraints"]],
                       "Constraints, ranges and assumptions with their stated basis")
    conv = spec.get("converter", {})
    if conv:
        body += _table(["Converter assumption", "Value"], [[k, v] for k, v in conv.items()], "Initial converter assumptions (not final component specifications)")
    page("01 / REQUIREMENTS", "Specification and labelled assumptions", body)
    # Environment
    env = report["environment"]
    rows = [[tid, t["found"], t.get("version") or "", "not tested" if t.get("qualified") is None else t.get("qualified"), t.get("path") or ""] for tid, t in env["tools"].items()]
    body = f"<p>{_esc(env['platform']['system'])} {_esc(env['platform']['release'])} ({_esc(env['platform']['machine'])}); Python {_esc(env['python']['version'])}.</p>"
    body += _table(["Tool", "Found", "Version", "Qualified", "Path"], rows, "Engineering software detected and qualified by aipe-workflows doctor")
    page("02 / ENVIRONMENT", "Local toolchain", body)
    # Tasks
    gate_of = {t["id"]: t["gate"] for t in workflow["tasks"]}
    rows = [[tid, gate_of.get(tid, ""), t["status"], f"{(t.get('tool') or {}).get('id', '')} {(t.get('tool') or {}).get('version', '')}", t.get("message", "")] for tid, t in report["tasks"].items()]
    body = _table(["Task", "Gate", "Status", "Tool", "Message"], rows, "Task execution")
    page("03 / EXECUTION", "Task graph results", body)
    for tid, t in report["tasks"].items():
        outputs = t.get("outputs") or {}
        if not outputs:
            continue
        body = ""
        scalar = {k: v for k, v in outputs.items() if isinstance(v, (int, float, str, bool)) or v is None}
        if scalar:
            body += _table(["Output", "Value"], [[k, v] for k, v in scalar.items()], "Scalar outputs")
        if outputs.get("switches"):
            rows = [[sid, s["i_rms_A"], s["i_avg_A"], s["i_turn_off_mean_abs_A"], s["i_peak_fwd_A"], s["i_peak_rev_A"], s["v_ds_max_V"], s["zvs_current_condition_all_events"], s["conduction_fraction"]]
                    for sid, s in outputs["switches"].items()]
            body += _table(["Switch", "I rms (A)", "I avg (A)", "I off |mean| (A)", "I pk fwd (A)", "I pk rev (A)", "V_ds max (V)", "ZVS cond.", "cond. fraction"], rows, "Per-switch waveform metrics")
        if outputs.get("comparison_vs_analytic"):
            cmp = outputs["comparison_vs_analytic"]
            rows = [[k, v["expected"], v["actual"], v["relative_error"], v["pass"]] for k, v in cmp["items"].items()]
            body += _table(["Quantity", "Expected (analytic)", "Simulated", "Relative error", "Pass"], rows, f"Comparison with the analytical SPS reference (tolerance {cmp['tolerance']:.1%}; overall {'pass' if cmp['pass'] else 'fail'})")
        if t.get("verification"):
            body += _table(["Verification metric", "Value"], [[k, v] for k, v in t["verification"].items()], "Numerical verification")
        model = t.get("model") or {}
        if model:
            body += f"<section class=\"callout compact\"><strong>Model</strong><p>{_esc(model.get('id'))} v{_esc(model.get('version'))}: {_esc(model.get('validity_range', ''))}</p></section>"
        page(f"04 / TASK {tid.upper()}", f"Results of {tid}", body)
    if report["figures"]:
        body = "".join(f"<figure><img src=\"{_esc(f['path'])}\" alt=\"{_esc(f['task'])} figure\"><figcaption>{_esc(f['path'])} — task {_esc(f['task'])}, sha256 {_esc(str(f.get('sha256'))[:16])}</figcaption></figure>" for f in report["figures"])
        page("05 / FIGURES", "Executed waveforms", body)
    gates = report["verification_gates"]["gates"]
    rows = [[g, gates[g]["status"], ", ".join(c["task"] + ": " + c["status"] for c in gates[g]["checks"]) or "—", " ".join(gates[g]["notes"])] for g in GATE_ORDER]
    body = _table(["Gate", "Status", "Checks", "Notes"], rows, "Verification gates (an earlier gate never implies a later one)")
    if report["blocked_items"] or report["failed_items"]:
        body += _table(["Task", "Kind", "Reason"], [[i["task"], "blocked", i["reason"]] for i in report["blocked_items"]] + [[i["task"], "failed", i["reason"]] for i in report["failed_items"]], "Blocked and failed items")
    final = report["engineering_state"]["final"]
    if final:
        body += (f"<section class=\"callout compact\"><strong>Engineering State</strong><p>{_esc(final['id'])}: validation {_esc(final['validation']['status'])}, simulation {_esc(final['simulation']['status'])}, "
                 f"architecture stage {_esc(final['architecture']['stage'])}; {len(final['evidence'])} evidence records, {len(report['engineering_state']['versions'])} versions preserved.</p></section>")
        body += _table(["Evidence id", "Kind", "Description"], [[e["id"], e["kind"], e["description"]] for e in final["evidence"]], "Evidence records")
    page("06 / VERIFICATION", "Gates, evidence and limitations", body)
    body = ("<pre><code>aipe-workflows doctor --qualify\naipe-workflows run &lt;specification.yaml&gt; --checkouts ..\n"
            f"aipe-workflows verify {_esc(run['run_id'])}\naipe-workflows report {_esc(run['run_id'])}</code></pre>"
            "<section class=\"callout compact\"><strong>Before sharing</strong><p>Check that every claim traces to an executed artefact, that assumptions remain labelled, and that no gate is read as passed when it is not run.</p></section>")
    page("07 / REPRODUCTION", "How to reproduce this run", body)
    head_links = ("<link rel=\"stylesheet\" href=\"assets/base.css\"><link rel=\"stylesheet\" href=\"assets/document.css\"><script defer src=\"assets/template.js\"></script>"
                  if styled else f"<style>{FALLBACK_CSS}</style>")
    document = (f"<!doctype html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                f"<title>{_esc(workflow.get('name', run['workflow_id']))} — {_esc(run['run_id'])}</title>{head_links}</head>\n<body>\n"
                f"<p class=\"print-tip\">A4 portrait · 100% scale · CSS default margins · Disable browser headers and footers · Enable background graphics</p>\n"
                f"<div class=\"document-shell\"><main class=\"document-pages\">\n" + "\n".join(pages) + "\n</main></div>\n</body></html>\n")
    path = out_dir / "report.html"
    path.write_text(document, encoding="utf-8")
    return str(path)
