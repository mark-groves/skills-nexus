"""Human-readable reports for skill evaluation results."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .core import EvalError, EvaluationCondition


def _percent(value: object) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value * 100:.1f}%"


def _number(value: object, digits: int = 1) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value:.{digits}f}"


def _integer(value: object) -> str:
    return "—" if not isinstance(value, int) or isinstance(value, bool) else f"{value:,}"


def _signed(value: object, digits: int = 0) -> str:
    return (
        "—"
        if not isinstance(value, (int, float)) or isinstance(value, bool)
        else f"{value:+.{digits}f}"
    )


def _mark(value: object) -> str:
    return "✅" if value is True else "❌" if value is False else "❔"


def _markdown_label(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _check_text(value: object) -> str:
    if isinstance(value, dict):
        text = str(value.get("text", ""))
        check_id = str(value.get("id", ""))
        check_class = str(value.get("class", ""))
        gate = str(value.get("gate", ""))
        return f"`{check_id}` [{check_class}/{gate}] {text}"
    return str(value)


def _gate_mark(status: str) -> str:
    return "✅" if status == "pass" else "❌" if status == "fail" else "❔"


def _review_markdown(result: dict[str, Any]) -> list[str]:
    review = result.get("optimisation_review")
    if not review:
        return []
    lines = [
        "## Optimisation gates",
        "",
        f"Verdict **{review['verdict']}** · repository policy "
        f"`{review['policy']['status']}` · hard failure `{review['hard_failure']}` · "
        f"hard gate blocked `{review['hard_blocked']}`.",
        "",
        "Correctness, safety, triggering, context, and integrity are independent. "
        "No aggregate score can override a hard failure.",
        "",
        "| Dimension | Gate | Status | Observed | Required |",
        "|---|---|---:|---|---|",
    ]
    for dimension_name, dimension in review["dimensions"].items():
        gates = dimension["gates"]
        if not gates:
            lines.append(f"| {dimension_name} | — | not-applicable | — | — |")
            continue
        for gate in gates:
            observed = _markdown_label(
                json.dumps(gate["observed"], ensure_ascii=False, sort_keys=True)
            )
            required = _markdown_label(
                json.dumps(gate["required"], ensure_ascii=False, sort_keys=True)
            )
            lines.append(
                f"| {dimension_name} | `{gate['id']}` | "
                f"{_gate_mark(gate['status'])} {gate['status']} | {observed} | {required} |"
            )
    lines.extend(["", "### Effective review policy", "", "```json"])
    lines.append(
        json.dumps(
            review["policy"]["effective"],
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    lines.extend(["```", ""])
    return lines


def _review_html(result: dict[str, Any]) -> str:
    review = result.get("optimisation_review")
    if not review:
        return ""
    rows = ""
    for dimension_name, dimension in review["dimensions"].items():
        gates = dimension["gates"]
        if not gates:
            rows += (
                f"<tr><td>{html.escape(dimension_name)}</td><td>—</td>"
                "<td>not-applicable</td><td>—</td><td>—</td></tr>"
            )
            continue
        for gate in gates:
            rows += (
                "<tr>"
                f"<td>{html.escape(dimension_name)}</td>"
                f"<td><code>{html.escape(gate['id'])}</code></td>"
                f"<td>{_gate_mark(gate['status'])} {html.escape(gate['status'])}</td>"
                f"<td><code>{html.escape(json.dumps(gate['observed'], ensure_ascii=False, sort_keys=True))}</code></td>"
                f"<td><code>{html.escape(json.dumps(gate['required'], ensure_ascii=False, sort_keys=True))}</code></td>"
                "</tr>"
            )
    policy = html.escape(
        json.dumps(
            review["policy"]["effective"],
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return (
        "<section><h2>Optimisation gates</h2>"
        f"<p>Verdict <strong>{html.escape(review['verdict'])}</strong> · "
        f"repository policy <code>{html.escape(review['policy']['status'])}</code> · "
        f"hard failure <code>{review['hard_failure']}</code> · "
        f"hard gate blocked <code>{review['hard_blocked']}</code>.</p>"
        "<p>Correctness, safety, triggering, context, and integrity are independent. "
        "No aggregate score can override a hard failure.</p>"
        "<table><thead><tr><th>Dimension</th><th>Gate</th><th>Status</th>"
        f"<th>Observed</th><th>Required</th></tr></thead><tbody>{rows}</tbody></table>"
        f"<details><summary>Effective review policy</summary><pre>{policy}</pre></details>"
        "</section>"
    )


def _validated_conditions(
    conditions: tuple[EvaluationCondition, ...],
) -> tuple[EvaluationCondition, ...]:
    if len(conditions) not in {2, 3} or len({condition.id for condition in conditions}) != len(
        conditions
    ):
        raise EvalError("reports require two or three distinct conditions")
    return conditions


def _trigger_entries(
    result: dict[str, Any],
    conditions: tuple[EvaluationCondition, ...],
) -> list[tuple[EvaluationCondition, dict[str, Any]]]:
    entries: list[tuple[EvaluationCondition, dict[str, Any]]] = []
    if result.get("trigger"):
        entries.append((conditions[0], result["trigger"]))
    if len(conditions) == 3 and result.get("candidate_trigger"):
        entries.append((conditions[2], result["candidate_trigger"]))
    return entries


def _comparison_rows(summary: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for comparison in summary.get("comparisons", {}).values():
        paired = comparison["paired_checks"]
        rows.append(
            f"| {_markdown_label(comparison['left_label'])} vs "
            f"{_markdown_label(comparison['right_label'])} | "
            f"{_number(comparison['lift_percentage_points'])} pp | "
            f"{paired['left_wins']} | {paired['right_wins']} | "
            f"{paired['ties']} | {paired['unknown']} |"
        )
    return rows


def _static_markdown_rows(
    result: dict[str, Any],
    conditions: tuple[EvaluationCondition, ...],
) -> list[str]:
    footprints = result["context_footprint"]
    rows: list[str] = []
    for condition in conditions:
        footprint = footprints[condition.id]
        description = footprint["description"]
        body = footprint["skill_md_body"]
        package = footprint["runtime_package"]
        digest = package["digest_sha256"]
        digest_cell = f"`{digest[:12]}`" if digest else "—"
        rows.append(
            f"| {_markdown_label(condition.display_label)} | "
            f"{_integer(description['characters'])} / {_integer(description['utf8_bytes'])} | "
            f"{_integer(body['characters'])} / {_integer(body['utf8_bytes'])} | "
            f"{_integer(package['file_count'])} / {_integer(package['bytes'])} | "
            f"{digest_cell} |"
        )
    return rows


def _candidate_markdown(result: dict[str, Any]) -> list[str]:
    comparison = result.get("candidate_comparison")
    if not comparison:
        return []
    reductions = comparison["static_reductions"]
    paired = comparison["paired_checks"]
    return [
        "## Candidate change",
        "",
        "Quality is Candidate minus comparison; reductions are Current minus Candidate. "
        "Positive values therefore mean higher candidate quality or a smaller candidate context.",
        "",
        "| Measure | Candidate change |",
        "|---|---:|",
        f"| Quality vs Current | "
        f"{_signed(comparison['candidate_minus_current_quality_percentage_points'], 1)} pp |",
        f"| Lift over Baseline | "
        f"{_signed(comparison['candidate_lift_over_baseline_percentage_points'], 1)} pp |",
        f"| Description characters / UTF-8 bytes | "
        f"{_signed(reductions['description_characters'])} / "
        f"{_signed(reductions['description_utf8_bytes'])} |",
        f"| `SKILL.md` body characters / UTF-8 bytes | "
        f"{_signed(reductions['skill_md_body_characters'])} / "
        f"{_signed(reductions['skill_md_body_utf8_bytes'])} |",
        f"| Runtime-package files / bytes | "
        f"{_signed(reductions['runtime_package_files'])} / "
        f"{_signed(reductions['runtime_package_bytes'])} |",
        f"| Dynamic input tokens | {_signed(comparison['dynamic_input_token_reduction'])} |",
        "",
        f"Paired checks: {paired['wins']} candidate wins, "
        f"{paired['regressions']} regressions, {paired['ties']} ties, "
        f"{paired['unknown']} unknown.",
        "",
    ]


def render_markdown(
    result: dict[str, Any],
    conditions: tuple[EvaluationCondition, ...],
) -> str:
    conditions = _validated_conditions(conditions)
    primary, comparison = conditions[:2]
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
        "## Context footprint",
        "",
        "Portable static measurements are canonical; token counts come only from runner usage.",
        "",
        "| Condition | Description chars / bytes | Body chars / bytes | Package files / bytes | Digest |",
        "|---|---:|---:|---:|---|",
        *_static_markdown_rows(result, conditions),
        "",
    ]
    lines.extend(_candidate_markdown(result))
    lines.extend(_review_markdown(result))

    trigger_entries = _trigger_entries(result, conditions)
    if trigger_entries:
        lines.extend(["## Triggering", ""])
        for condition, trigger in trigger_entries:
            if len(trigger_entries) > 1:
                lines.extend([f"### {_markdown_label(condition.display_label)}", ""])
            summary = trigger["summary"]
            matrix = summary["confusion_matrix"]
            lines.extend(
                [
                    f"Balanced accuracy {_percent(summary['balanced_accuracy'])}; recall "
                    f"{_percent(summary['recall'])}; specificity "
                    f"{_percent(summary['specificity'])}; TP/FP/TN/FN = "
                    f"{matrix['tp']}/{matrix['fp']}/{matrix['tn']}/{matrix['fn']} "
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
        primary_label = _markdown_label(primary.display_label)
        comparison_label = _markdown_label(comparison.display_label)
        comparison_phrase = (
            f"without the {primary_label.lower()}"
            if comparison.runtime_skill_dir is None
            else f"for {comparison_label.lower()}"
        )
        lines.extend(
            [
                "## Behavior and lift",
                "",
                f"The {primary_label.lower()} passed "
                f"{_percent(summary[primary.id]['pass_rate'])} of checks versus "
                f"{_percent(summary[comparison.id]['pass_rate'])} {comparison_phrase} "
                f"({_number(summary['lift_percentage_points'])} percentage-point lift). "
                f"Paired checks: {pairs['skill_wins']} wins, {pairs['regressions']} regressions, "
                f"{pairs['ties']} ties, {pairs['unknown']} unknown.",
                "",
            ]
        )
        comparison_rows = _comparison_rows(summary)
        if comparison_rows:
            lines.extend(
                [
                    "### Pairwise comparisons",
                    "",
                    "| Comparison | Lift | Left wins | Right wins | Ties | Unknown |",
                    "|---|---:|---:|---:|---:|---:|",
                    *comparison_rows,
                    "",
                ]
            )
        lines.extend(
            [
                "| Condition | Check pass | Evidence | Input tokens | Output tokens | "
                "Total tokens | Median time | Tool calls | Runs complete / failed |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for condition in conditions:
            condition_summary = summary[condition.id]
            efficiency = summary["efficiency"][condition.id]
            lines.append(
                f"| {_markdown_label(condition.display_label)} | "
                f"{_percent(condition_summary['pass_rate'])} | "
                f"{_percent(condition_summary['evidence_coverage'])} | "
                f"{_integer(efficiency['input_tokens'])} | "
                f"{_integer(efficiency['output_tokens'])} | "
                f"{_integer(efficiency['total_tokens'])} | "
                f"{_number(efficiency['median_duration_seconds'])}s | "
                f"{_integer(efficiency['tool_calls'])} | "
                f"{efficiency['completed_runs']} / {efficiency['failed_runs']} |"
            )
        lines.append("")

        for case in behavior["results"]:
            activation_text = " · ".join(
                f"{_markdown_label(condition.display_label).lower()} activated: "
                f"`{case[f'{condition.id}_run'].get('activated')}`"
                for condition in conditions
                if condition.runtime_skill_dir is not None
            )
            labels = [_markdown_label(condition.display_label) for condition in conditions]
            lines.extend(
                [
                    f"### Behavior {case['case_id']} · repeat {case['repeat']}",
                    "",
                    f"Fixture fidelity: `{case['fixture_fidelity']}` · judge: "
                    f"`{case.get('judge', {}).get('status', 'not-run')}` · {activation_text}",
                    "",
                    (
                        f"| Check | {labels[0]} | {labels[1]} | {labels[0]} evidence |"
                        if len(conditions) == 2
                        else "| Check | " + " | ".join(labels) + " | Evidence |"
                    ),
                    (
                        "|---|---:|---:|---|"
                        if len(conditions) == 2
                        else "|---|" + "---:|" * len(conditions) + "---|"
                    ),
                ]
            )
            grades = case.get("grades", {})
            for index, check in enumerate(case["checks"]):
                condition_grades = [
                    grades.get(condition.id, [])[index]
                    if index < len(grades.get(condition.id, []))
                    else {}
                    for condition in conditions
                ]
                evidence = (
                    str(condition_grades[0].get("evidence", ""))
                    .replace("|", "\\|")
                    .replace("\n", " ")
                    if len(conditions) == 2
                    else " / ".join(
                        f"{labels[position]}: "
                        + str(grade.get("evidence", "")).replace("|", "\\|").replace("\n", " ")
                        for position, grade in enumerate(condition_grades)
                        if grade.get("evidence")
                    )
                )
                escaped_check = _check_text(check).replace("|", "\\|")
                lines.append(
                    f"| {escaped_check} | "
                    + " | ".join(_mark(grade.get("passed")) for grade in condition_grades)
                    + f" | {evidence} |"
                )
            lines.append("")

    integrity = result["integrity"]
    condition_labels = ", ".join(
        _markdown_label(condition.display_label) for condition in conditions
    )
    context_line = (
        f"- {_markdown_label(conditions[0].display_label)} and "
        f"{_markdown_label(conditions[1].display_label).lower()} ran in fresh "
        f"isolated contexts: `{integrity['fresh_contexts']}`"
        if len(conditions) == 2
        else f"- {condition_labels} ran in fresh isolated contexts: `{integrity['fresh_contexts']}`"
    )
    grading_line = (
        f"- Paired grading used randomized labels: `{integrity['blind_paired_grading']}`"
        if len(conditions) == 2
        else "- Multi-condition grading used randomized condition-blind labels: "
        f"`{integrity['blind_paired_grading']}`"
    )
    lines.extend(
        [
            "## Integrity and limitations",
            "",
            f"- Eval ground truth withheld from task agents: `{integrity['evals_withheld']}`",
            context_line,
            f"- Repository peer skills were held constant across conditions: "
            f"`{integrity['peer_skill_parity']}`",
            grading_line,
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


def render_html(
    result: dict[str, Any],
    conditions: tuple[EvaluationCondition, ...],
) -> str:
    conditions = _validated_conditions(conditions)
    profile = result["efficacy"]
    footprints = result["context_footprint"]
    footprint_rows = ""
    for condition in conditions:
        footprint = footprints[condition.id]
        description = footprint["description"]
        body = footprint["skill_md_body"]
        package = footprint["runtime_package"]
        digest = package["digest_sha256"]
        footprint_rows += (
            "<tr>"
            f"<td>{html.escape(condition.display_label)}</td>"
            f"<td>{_integer(description['characters'])} / "
            f"{_integer(description['utf8_bytes'])}</td>"
            f"<td>{_integer(body['characters'])} / {_integer(body['utf8_bytes'])}</td>"
            f"<td>{_integer(package['file_count'])} / {_integer(package['bytes'])}</td>"
            f"<td>{f'<code>{digest[:12]}</code>' if digest else '—'}</td>"
            "</tr>"
        )
    footprint_section = (
        "<section><h2>Context footprint</h2>"
        "<p>Portable static measurements are canonical; token counts come only "
        "from runner usage.</p>"
        "<table><thead><tr><th>Condition</th><th>Description chars / bytes</th>"
        "<th>Body chars / bytes</th><th>Package files / bytes</th><th>Digest</th>"
        f"</tr></thead><tbody>{footprint_rows}</tbody></table></section>"
    )
    candidate_section = ""
    candidate_comparison = result.get("candidate_comparison")
    if candidate_comparison:
        reductions = candidate_comparison["static_reductions"]
        paired = candidate_comparison["paired_checks"]
        candidate_rows = "".join(
            f"<tr><td>{html.escape(label)}</td><td>{value}</td></tr>"
            for label, value in (
                (
                    "Quality vs Current",
                    f"{_signed(candidate_comparison['candidate_minus_current_quality_percentage_points'], 1)} pp",
                ),
                (
                    "Lift over Baseline",
                    f"{_signed(candidate_comparison['candidate_lift_over_baseline_percentage_points'], 1)} pp",
                ),
                (
                    "Description characters / UTF-8 bytes",
                    f"{_signed(reductions['description_characters'])} / "
                    f"{_signed(reductions['description_utf8_bytes'])}",
                ),
                (
                    "SKILL.md body characters / UTF-8 bytes",
                    f"{_signed(reductions['skill_md_body_characters'])} / "
                    f"{_signed(reductions['skill_md_body_utf8_bytes'])}",
                ),
                (
                    "Runtime-package files / bytes",
                    f"{_signed(reductions['runtime_package_files'])} / "
                    f"{_signed(reductions['runtime_package_bytes'])}",
                ),
                (
                    "Dynamic input tokens",
                    _signed(candidate_comparison["dynamic_input_token_reduction"]),
                ),
            )
        )
        candidate_section = (
            "<section><h2>Candidate change</h2>"
            "<p>Quality is Candidate minus comparison; reductions are Current minus "
            "Candidate. Positive values mean higher candidate quality or smaller "
            "candidate context.</p>"
            "<table><thead><tr><th>Measure</th><th>Candidate change</th></tr></thead>"
            f"<tbody>{candidate_rows}</tbody></table>"
            f"<p>Paired checks: {paired['wins']} candidate wins, "
            f"{paired['regressions']} regressions, {paired['ties']} ties, "
            f"{paired['unknown']} unknown.</p></section>"
        )
    review_section = _review_html(result)
    trigger_sections = ""
    trigger_entries = _trigger_entries(result, conditions)
    for condition, trigger in trigger_entries:
        rows = ""
        for case in trigger["summary"]["cases"]:
            rows += (
                "<tr>"
                f"<td>{html.escape(str(case['id']))}</td>"
                f"<td>{'trigger' if case['expected'] else 'skip'}</td>"
                f"<td>{_percent(case['activation_rate'])}</td>"
                f"<td>{_mark(case['passed'])}</td>"
                f"<td>{html.escape(case['query'])}</td>"
                "</tr>"
            )
        summary = trigger["summary"]
        condition_heading = (
            f"<h3>{html.escape(condition.display_label)}</h3>" if len(trigger_entries) > 1 else ""
        )
        trigger_sections += (
            condition_heading + f"<p>Balanced accuracy {_percent(summary['balanced_accuracy'])}; "
            f"recall {_percent(summary['recall'])}; "
            f"specificity {_percent(summary['specificity'])}.</p>"
            "<table><thead><tr><th>Case</th><th>Expected</th><th>Activation</th>"
            f"<th>Result</th><th>Query</th></tr></thead><tbody>{rows}</tbody></table>"
        )

    behavior = result.get("behavior")
    behavior_intro = ""
    behavior_sections = ""
    if behavior:
        summary = behavior["summary"]
        condition_metrics = " · ".join(
            f"{html.escape(condition.display_label)} {_percent(summary[condition.id]['pass_rate'])}"
            for condition in conditions
        )
        behavior_intro = (
            f"<p>{html.escape(conditions[0].display_label)} check pass "
            f"{_percent(summary[conditions[0].id]['pass_rate'])}; "
            f"{html.escape(conditions[1].display_label.lower())} "
            f"{_percent(summary[conditions[1].id]['pass_rate'])}; lift "
            f"{_number(summary['lift_percentage_points'])} percentage points.</p>"
            if len(conditions) == 2
            else f"<p>Check pass rates: {condition_metrics}.</p>"
        )
        comparisons = summary.get("comparisons", {})
        if comparisons:
            comparison_rows = "".join(
                "<tr>"
                f"<td>{html.escape(item['left_label'])} vs "
                f"{html.escape(item['right_label'])}</td>"
                f"<td>{_number(item['lift_percentage_points'])} pp</td>"
                f"<td>{item['paired_checks']['left_wins']}</td>"
                f"<td>{item['paired_checks']['right_wins']}</td>"
                f"<td>{item['paired_checks']['ties']}</td>"
                f"<td>{item['paired_checks']['unknown']}</td>"
                "</tr>"
                for item in comparisons.values()
            )
            behavior_intro += (
                "<h3>Pairwise comparisons</h3><table><thead><tr><th>Comparison</th>"
                "<th>Lift</th><th>Left wins</th><th>Right wins</th><th>Ties</th>"
                f"<th>Unknown</th></tr></thead><tbody>{comparison_rows}</tbody></table>"
            )
        efficiency_rows = ""
        for condition in conditions:
            condition_summary = summary[condition.id]
            efficiency = summary["efficiency"][condition.id]
            efficiency_rows += (
                "<tr>"
                f"<td>{html.escape(condition.display_label)}</td>"
                f"<td>{_percent(condition_summary['pass_rate'])}</td>"
                f"<td>{_percent(condition_summary['evidence_coverage'])}</td>"
                f"<td>{_integer(efficiency['input_tokens'])}</td>"
                f"<td>{_integer(efficiency['output_tokens'])}</td>"
                f"<td>{_integer(efficiency['total_tokens'])}</td>"
                f"<td>{_number(efficiency['median_duration_seconds'])}s</td>"
                f"<td>{_integer(efficiency['tool_calls'])}</td>"
                f"<td>{efficiency['completed_runs']} / {efficiency['failed_runs']}</td>"
                "</tr>"
            )
        behavior_intro += (
            "<table><thead><tr><th>Condition</th><th>Check pass</th><th>Evidence</th>"
            "<th>Input tokens</th><th>Output tokens</th><th>Total tokens</th>"
            "<th>Median time</th><th>Tool calls</th><th>Runs complete / failed</th>"
            f"</tr></thead><tbody>{efficiency_rows}</tbody></table>"
        )
        for case in behavior["results"]:
            grades = case.get("grades", {})
            header = "".join(
                f"<th>{html.escape(condition.display_label)}</th>" for condition in conditions
            )
            evidence_header = (
                f"{html.escape(conditions[0].display_label)} evidence"
                if len(conditions) == 2
                else "Evidence"
            )
            rows = ""
            for index, check in enumerate(case["checks"]):
                marks = ""
                evidence_parts: list[str] = []
                for condition in conditions:
                    condition_grades = grades.get(condition.id, [])
                    grade = condition_grades[index] if index < len(condition_grades) else {}
                    marks += f"<td>{_mark(grade.get('passed'))}</td>"
                    if grade.get("evidence"):
                        evidence_parts.append(
                            f"{condition.display_label}: {grade.get('evidence', '')}"
                        )
                evidence = (
                    str(grades.get(conditions[0].id, [])[index].get("evidence", ""))
                    if len(conditions) == 2 and index < len(grades.get(conditions[0].id, []))
                    else " / ".join(evidence_parts)
                )
                rows += (
                    f"<tr><td>{html.escape(_check_text(check))}</td>{marks}"
                    f"<td>{html.escape(evidence)}</td></tr>"
                )
            responses = "".join(
                f"<div><h4>{html.escape(condition.display_label)} response</h4>"
                f"<pre>{html.escape(case[f'{condition.id}_run'].get('final_response', ''))}</pre>"
                "</div>"
                for condition in conditions
            )
            behavior_sections += f"""
            <details>
              <summary>Behavior {html.escape(str(case["case_id"]))} · repeat {case["repeat"]} · fidelity {html.escape(case["fixture_fidelity"])}</summary>
              <table><thead><tr><th>Check</th>{header}<th>{evidence_header}</th></tr></thead><tbody>{rows}</tbody></table>
              <div class="columns">{responses}</div>
            </details>
            """

    warnings = (
        "".join(
            f"<li>{html.escape(warning)}</li>"
            for warning in result["integrity"].get("warnings", [])
        )
        or "<li>No framework integrity warnings.</li>"
    )
    cards = "".join(
        f'<div class="card"><span>{html.escape(label)}</span><strong>{value}</strong></div>'
        for label, value in (
            ("Absolute efficacy", _percent(profile["absolute_efficacy"])),
            ("Activation quality", _percent(profile["activation_quality"])),
            ("Execution quality", _percent(profile["execution_quality"])),
            ("Incremental lift", _percent(profile["incremental_lift"])),
            ("Evidence coverage", _percent(profile["evidence_coverage"])),
        )
    )
    trigger_section = (
        f"<section><h2>Triggering</h2>{trigger_sections}</section>" if trigger_sections else ""
    )

    grading_integrity_label = (
        "randomized paired grading"
        if len(conditions) == 2
        else "randomized condition-blind grading"
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
.columns{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}code{{background:#e7e3d8;padding:.12rem .35rem;border-radius:4px}}
</style></head><body><main>
<div class="eyebrow">Skills Nexus evaluation</div><h1>{html.escape(result["skill"]["name"])}</h1>
<p><span class="verdict">{html.escape(profile["verdict"])}</span> Run <code>{html.escape(result["run_id"])}</code> · {html.escape(result["generated_at"])}</p>
<div class="cards">{cards}</div><p>{html.escape(profile["formula"])} {html.escape(profile["note"])}</p>
{footprint_section}
{candidate_section}
{review_section}
{trigger_section}
<section><h2>Behavior and lift</h2>{behavior_intro}{behavior_sections or "<p>Behavior suite was not selected.</p>"}</section>
<section><h2>Integrity and limitations</h2><ul>{warnings}</ul><p>Eval ground truth withheld: <code>{result["integrity"]["evals_withheld"]}</code> · fresh contexts: <code>{result["integrity"]["fresh_contexts"]}</code> · peer parity: <code>{result["integrity"]["peer_skill_parity"]}</code> · {grading_integrity_label}: <code>{result["integrity"]["blind_paired_grading"]}</code></p></section>
<section><h2>Reproduce</h2><pre>{html.escape(result["reproduce_command"])}</pre></section>
</main></body></html>"""


def write_reports(
    output_dir: Path,
    result: dict[str, Any],
    conditions: tuple[EvaluationCondition, ...],
) -> tuple[Path, Path]:
    markdown_path = output_dir / "report.md"
    html_path = output_dir / "report.html"
    markdown_path.write_text(render_markdown(result, conditions), encoding="utf-8")
    html_path.write_text(render_html(result, conditions), encoding="utf-8")
    return markdown_path, html_path
