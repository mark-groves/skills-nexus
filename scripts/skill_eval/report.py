"""Human-readable reports for skill evaluation results."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _percent(value: object) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value * 100:.1f}%"


def _number(value: object, digits: int = 1) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value:.{digits}f}"


def _mark(value: object) -> str:
    return "✅" if value is True else "❌" if value is False else "❔"


def render_markdown(result: dict[str, Any]) -> str:
    profile = result["efficacy"]
    lines = [
        f"# Skill efficacy report: `{result['skill']['name']}`",
        "",
        f"Run `{result['run_id']}` · {result['generated_at']} · verdict **{profile['verdict']}**",
        "",
        "## Efficacy profile",
        "",
        "| Dimension | Result |",
        "|---|---:|",
        f"| Absolute efficacy | {_percent(profile['absolute_efficacy'])} |",
        f"| Activation quality | {_percent(profile['activation_quality'])} |",
        f"| Execution quality | {_percent(profile['execution_quality'])} |",
        f"| Incremental skill lift | {_percent(profile['incremental_lift'])} |",
        f"| Behavior evidence coverage | {_percent(profile['evidence_coverage'])} |",
        "",
        f"> {profile['formula']} {profile['note']}",
        "",
    ]

    trigger = result.get("trigger")
    if trigger:
        summary = trigger["summary"]
        matrix = summary["confusion_matrix"]
        lines.extend(
            [
                "## Triggering",
                "",
                f"Balanced accuracy {_percent(summary['balanced_accuracy'])}; recall "
                f"{_percent(summary['recall'])}; specificity {_percent(summary['specificity'])}; "
                f"TP/FP/TN/FN = {matrix['tp']}/{matrix['fp']}/{matrix['tn']}/{matrix['fn']} "
                f"with {matrix.get('unscored', 0)} unscored.",
                "",
                "| Case | Expected | Activation rate | Result | Query |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for case in summary["cases"]:
            query = case["query"].replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {case['id']} | {'trigger' if case['expected'] else 'skip'} | "
                f"{_percent(case['activation_rate'])} | {_mark(case['passed'])} | {query} |"
            )
        lines.append("")

    behavior = result.get("behavior")
    if behavior:
        summary = behavior["summary"]
        pairs = summary["paired_checks"]
        skill_efficiency = summary["efficiency"]["skill"]
        baseline_efficiency = summary["efficiency"]["baseline"]
        lines.extend(
            [
                "## Behavior and lift",
                "",
                f"The skill passed {_percent(summary['skill']['pass_rate'])} of checks versus "
                f"{_percent(summary['baseline']['pass_rate'])} without the skill "
                f"({_number(summary['lift_percentage_points'])} percentage-point lift). "
                f"Paired checks: {pairs['skill_wins']} wins, {pairs['regressions']} regressions, "
                f"{pairs['ties']} ties, {pairs['unknown']} unknown.",
                "",
                "| Condition | Check pass | Evidence | Median time | Median tokens | Tool calls |",
                "|---|---:|---:|---:|---:|---:|",
                f"| Skill | {_percent(summary['skill']['pass_rate'])} | "
                f"{_percent(summary['skill']['evidence_coverage'])} | "
                f"{_number(skill_efficiency['median_duration_seconds'])}s | "
                f"{_number(skill_efficiency['median_tokens'], 0)} | {skill_efficiency['tool_calls']} |",
                f"| Baseline | {_percent(summary['baseline']['pass_rate'])} | "
                f"{_percent(summary['baseline']['evidence_coverage'])} | "
                f"{_number(baseline_efficiency['median_duration_seconds'])}s | "
                f"{_number(baseline_efficiency['median_tokens'], 0)} | {baseline_efficiency['tool_calls']} |",
                "",
            ]
        )
        for case in behavior["results"]:
            lines.extend(
                [
                    f"### Behavior {case['case_id']} · repeat {case['repeat']}",
                    "",
                    f"Fixture fidelity: `{case['fixture_fidelity']}` · judge: "
                    f"`{case.get('judge', {}).get('status', 'not-run')}` · skill activated: "
                    f"`{case['skill_run'].get('activated')}`",
                    "",
                    "| Check | Skill | Baseline | Skill evidence |",
                    "|---|---:|---:|---|",
                ]
            )
            skill_grades = case.get("grades", {}).get("skill", [])
            baseline_grades = case.get("grades", {}).get("baseline", [])
            for index, check in enumerate(case["checks"]):
                skill_grade = skill_grades[index] if index < len(skill_grades) else {}
                base_grade = baseline_grades[index] if index < len(baseline_grades) else {}
                escaped_check = check.replace("|", "\\|")
                evidence = (
                    str(skill_grade.get("evidence", "")).replace("|", "\\|").replace("\n", " ")
                )
                lines.append(
                    f"| {escaped_check} | {_mark(skill_grade.get('passed'))} | "
                    f"{_mark(base_grade.get('passed'))} | {evidence} |"
                )
            lines.append("")

    integrity = result["integrity"]
    lines.extend(
        [
            "## Integrity and limitations",
            "",
            f"- Eval ground truth withheld from task agents: `{integrity['evals_withheld']}`",
            f"- Skill and baseline ran in fresh isolated contexts: `{integrity['fresh_contexts']}`",
            f"- Repository peer skills were held constant across conditions: `{integrity['peer_skill_parity']}`",
            f"- Paired grading used randomized labels: `{integrity['blind_paired_grading']}`",
        ]
    )
    for warning in integrity.get("warnings", []):
        lines.append(f"- Warning: {warning}")
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            f"```bash\n{result['reproduce_command']}\n```",
            "",
            "Machine-readable evidence is in `results.json`; raw task and judge events are under `runs/`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(result: dict[str, Any]) -> str:
    profile = result["efficacy"]
    trigger = result.get("trigger")
    behavior = result.get("behavior")

    trigger_rows = ""
    if trigger:
        for case in trigger["summary"]["cases"]:
            trigger_rows += (
                "<tr>"
                f"<td>{html.escape(str(case['id']))}</td>"
                f"<td>{'trigger' if case['expected'] else 'skip'}</td>"
                f"<td>{_percent(case['activation_rate'])}</td>"
                f"<td>{_mark(case['passed'])}</td>"
                f"<td>{html.escape(case['query'])}</td>"
                "</tr>"
            )

    behavior_sections = ""
    if behavior:
        for case in behavior["results"]:
            rows = ""
            skill_grades = case.get("grades", {}).get("skill", [])
            baseline_grades = case.get("grades", {}).get("baseline", [])
            for index, check in enumerate(case["checks"]):
                skill_grade = skill_grades[index] if index < len(skill_grades) else {}
                baseline_grade = baseline_grades[index] if index < len(baseline_grades) else {}
                rows += (
                    "<tr>"
                    f"<td>{html.escape(check)}</td>"
                    f"<td>{_mark(skill_grade.get('passed'))}</td>"
                    f"<td>{_mark(baseline_grade.get('passed'))}</td>"
                    f"<td>{html.escape(str(skill_grade.get('evidence', '')))}</td>"
                    "</tr>"
                )
            skill_final = html.escape(case["skill_run"].get("final_response", ""))
            baseline_final = html.escape(case["baseline_run"].get("final_response", ""))
            behavior_sections += f"""
            <details>
              <summary>Behavior {html.escape(str(case["case_id"]))} · repeat {case["repeat"]} · fidelity {html.escape(case["fixture_fidelity"])}</summary>
              <table><thead><tr><th>Check</th><th>Skill</th><th>Baseline</th><th>Skill evidence</th></tr></thead><tbody>{rows}</tbody></table>
              <div class="columns"><div><h4>Skill response</h4><pre>{skill_final}</pre></div><div><h4>Baseline response</h4><pre>{baseline_final}</pre></div></div>
            </details>
            """

    warnings = (
        "".join(
            f"<li>{html.escape(warning)}</li>"
            for warning in result["integrity"].get("warnings", [])
        )
        or "<li>No framework integrity warnings.</li>"
    )
    summary_cards = [
        ("Absolute efficacy", _percent(profile["absolute_efficacy"])),
        ("Activation quality", _percent(profile["activation_quality"])),
        ("Execution quality", _percent(profile["execution_quality"])),
        ("Incremental lift", _percent(profile["incremental_lift"])),
        ("Evidence coverage", _percent(profile["evidence_coverage"])),
    ]
    cards = "".join(
        f'<div class="card"><span>{html.escape(label)}</span><strong>{value}</strong></div>'
        for label, value in summary_cards
    )
    trigger_section = (
        f"""
        <section><h2>Triggering</h2>
        <p>Balanced accuracy {_percent(trigger["summary"]["balanced_accuracy"])}; recall {_percent(trigger["summary"]["recall"])}; specificity {_percent(trigger["summary"]["specificity"])}.</p>
        <table><thead><tr><th>Case</th><th>Expected</th><th>Activation</th><th>Result</th><th>Query</th></tr></thead><tbody>{trigger_rows}</tbody></table></section>
        """
        if trigger
        else ""
    )
    behavior_intro = ""
    if behavior:
        summary = behavior["summary"]
        behavior_intro = (
            f"<p>Skill check pass {_percent(summary['skill']['pass_rate'])}; baseline "
            f"{_percent(summary['baseline']['pass_rate'])}; lift "
            f"{_number(summary['lift_percentage_points'])} percentage points.</p>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skill efficacy · {html.escape(result["skill"]["name"])}</title>
<style>
:root{{--ink:#182126;--muted:#607078;--paper:#f5f2ea;--panel:#fffdf8;--accent:#006f62;--line:#d8d4ca}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:44px 24px 80px}}h1{{font-size:2.2rem;margin:.2rem 0}}h2{{margin-top:2.2rem}}.eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.verdict{{display:inline-block;background:var(--accent);color:white;border-radius:99px;padding:.25rem .75rem}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column}}.card span{{color:var(--muted)}}.card strong{{font-size:1.7rem}}
table{{width:100%;border-collapse:collapse;background:var(--panel);margin:12px 0 24px}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:10px}}th{{color:var(--muted);font-size:.82rem;text-transform:uppercase}}
details{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:12px 0;padding:12px}}summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;word-break:break-word;background:#182126;color:#ecf3ef;padding:14px;border-radius:8px;max-height:420px;overflow:auto}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}code{{background:#e7e3d8;padding:.12rem .35rem;border-radius:4px}}@media(max-width:760px){{.columns{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="eyebrow">Skills Nexus evaluation</div><h1>{html.escape(result["skill"]["name"])}</h1>
<p><span class="verdict">{html.escape(profile["verdict"])}</span> Run <code>{html.escape(result["run_id"])}</code> · {html.escape(result["generated_at"])}</p>
<div class="cards">{cards}</div><p>{html.escape(profile["formula"])} {html.escape(profile["note"])}</p>
{trigger_section}
<section><h2>Behavior and lift</h2>{behavior_intro}{behavior_sections or "<p>Behavior suite was not selected.</p>"}</section>
<section><h2>Integrity and limitations</h2><ul>{warnings}</ul><p>Eval ground truth withheld: <code>{result["integrity"]["evals_withheld"]}</code> · fresh contexts: <code>{result["integrity"]["fresh_contexts"]}</code> · peer parity: <code>{result["integrity"]["peer_skill_parity"]}</code> · randomized paired grading: <code>{result["integrity"]["blind_paired_grading"]}</code></p></section>
<section><h2>Reproduce</h2><pre>{html.escape(result["reproduce_command"])}</pre></section>
</main></body></html>"""


def write_reports(output_dir: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    markdown_path = output_dir / "report.md"
    html_path = output_dir / "report.html"
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    html_path.write_text(render_html(result), encoding="utf-8")
    return markdown_path, html_path
