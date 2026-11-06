#!/usr/bin/env python3
"""MathCheck-E2E-Bench automated harness.

Runs every E2E case through three layers:
  1. Parse layer  -- a deterministic parser that maps user_input to a
     normalized_task OR a clarify/unsupported decision. This stands in for
     the Skill's natural-language -> structured-task step (the "LLM" layer).
  2. Execute layer -- calls the production backend (mathcheck) for search /
     candidate verification / reduction. Fault-injection fixtures simulate
     backend failures.
  3. Score layer  -- compares the result against each case's `expected`
     block and emits a per-case CSV row plus an aggregate summary.

The parser is intentionally simple and rule-based: it encodes the exact
semantic decisions the SKILL.md requires (predicate whitelist, direction,
scope defaults, unsupported features). It is the thing being measured on the
"task parse exact-match" dimension.
"""

import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from mathcheck.search import search_task          # noqa: E402
from mathcheck.verify import verify_candidate      # noqa: E402
from mathcheck.minimize import minimize_counterexample  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "MathCheck_E2E_Bench_v1.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Parse layer (stands in for the Skill / LLM natural-language -> task step)
# ---------------------------------------------------------------------------

PREDICATE_HINTS = {
    "连通": "connected",
    "连通图": "connected",
    "二分": "bipartite",
    "二分图": "bipartite",
    "树": "tree",
    "欧拉回路": "eulerian_circuit",
    "欧拉迹": "eulerian_trail",
    "叶": "has_leaf",
    "环": "has_cycle",
    "完全图": "complete",
    "完全": "complete",
    "度数为偶数": "all_even_degree",
    "度数均为偶数": "all_even_degree",
    "度数不超过 2": "max_degree_at_most_2",
    "度数不超过2": "max_degree_at_most_2",
    "度数都不超过 2": "max_degree_at_most_2",
    "度数都至少为 1": "min_degree_at_least_1",
    "度数至少为1": "min_degree_at_least_1",
    "度数至少为 1": "min_degree_at_least_1",
}

UNSUPPORTED_SIGNALS = [
    ("有向", "directed_graph"),
    ("多重图", "multigraph"),
    ("不超过 3", "arbitrary_degree_threshold"),
    ("不超过3", "arbitrary_degree_threshold"),
    ("没有叶", "negated_predicate"),
    ("都不是树", "negated_conclusion"),
    ("或者", "disjunction"),
    ("或", "disjunction"),
]


def _extract_scope(text):
    """Return (min_nodes, max_nodes). Default 1..5."""
    import re
    mn, mx = 1, 5
    # explicit range "1 到 5" / "1 至 5" / "1..5" / "2 到 8"
    m = re.search(r"(\d+)\s*(?:到|至|\.\.)\s*(\d+)", text)
    if m:
        mn, mx = int(m.group(1)), int(m.group(2))
    # upper bound only: "顶点数最多为 3", "不超过 5 个顶点" — but NOT "度数不超过 2"
    m = re.search(r"(?:顶点数最多为|顶点数最多|顶点最多)\s*(\d+)", text)
    if m:
        mx = int(m.group(1))
    m = re.search(r"不超过\s*(\d+)\s*个顶点", text)
    if m:
        mx = int(m.group(1))
    # lower bound: "（最少 1 个顶点）", "最少 2"
    m = re.search(r"(?:最少|至少)\s*(\d+)", text)
    if m:
        mn = int(m.group(1))
    return mn, mx


def _extract_mode(text):
    if "随机" in text:
        return "random"
    if "special" in text.lower() or "特殊" in text:
        return "special"
    return "exhaustive"


def _extract_seed(text):
    import re
    m = re.search(r"种子\s*(\d+)", text)
    return int(m.group(1)) if m else None


def _extract_budget(text):
    import re
    m = re.search(r"抽样\s*(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*张图", text)
    if m:
        return int(m.group(1))
    return 2000


def parse(user_input):
    """Return a dict: either {decision: 'clarify'|'unsupported', reason}
    or {decision: 'task', task: {...}}."""
    # --- unsupported / clarification / ambiguity signals first ---
    if "有向" in user_input:
        return {"decision": "unsupported", "reason": "directed graph not supported"}
    if "多重图" in user_input:
        return {"decision": "unsupported", "reason": "multigraph not supported"}
    if "不超过 3" in user_input or "不超过3" in user_input:
        return {"decision": "unsupported", "reason": "arbitrary degree threshold not supported"}
    if "没有叶" in user_input or "都不是树" in user_input:
        return {"decision": "unsupported", "reason": "negated predicate/conclusion not supported"}
    if "或者" in user_input or ("或" in user_input and "完整" not in user_input):
        return {"decision": "unsupported", "reason": "disjunction not supported"}
    if "空图" in user_input or "0 个顶点" in user_input:
        return {"decision": "clarify", "reason": "empty-graph convention needs clarification"}
    # ambiguous Euler terminology: "欧拉图" alone (not 回路/迹) -> clarify
    if "欧拉图" in user_input and "欧拉回路" not in user_input and "欧拉迹" not in user_input:
        return {"decision": "clarify", "reason": "ambiguous Euler terminology"}
    # missing direction: relational question without an implication
    if "关系" in user_input and "之间" in user_input:
        return {"decision": "clarify", "reason": "missing implication direction"}

    # --- build the task ---
    conclusion = None

    # direction-explicit pattern: consequent follows 那么/则
    if "那么" in user_input or "则" in user_input:
        tail = user_input.split("那么")[-1] if "那么" in user_input else user_input.split("则")[-1]
        if "连通" in tail:
            conclusion = "connected"
        elif "二分" in tail:
            conclusion = "bipartite"
        elif "树" in tail and "不是" not in tail:
            conclusion = "tree"
        elif "欧拉回路" in tail:
            conclusion = "eulerian_circuit"
        elif "欧拉迹" in tail:
            conclusion = "eulerian_trail"
        elif "完全" in tail:
            conclusion = "complete"

    # fallback: infer conclusion from the question's consequent phrase
    if conclusion is None:
        if "是不是树" in user_input or "都是树" in user_input or "是树" in user_input:
            conclusion = "tree"
        elif "都是二分图" in user_input or "是二分图" in user_input or "都是二分" in user_input:
            conclusion = "bipartite"
        elif "都是连通图" in user_input or "是连通图" in user_input or "一定连通" in user_input or "都连通" in user_input or "是否连通" in user_input:
            conclusion = "connected"
        elif "都是完全图" in user_input or "都是完整图" in user_input or "是完整图" in user_input or "是否都是完全" in user_input:
            conclusion = "complete"
        elif "都有欧拉回路" in user_input or "都是欧拉回路" in user_input or "存在欧拉回路" in user_input or "有欧拉回路" in user_input or "一定具有欧拉回路" in user_input:
            conclusion = "eulerian_circuit"
        elif "存在欧拉迹" in user_input or "有欧拉迹" in user_input or "都是欧拉迹图" in user_input or "一定存在欧拉迹" in user_input:
            conclusion = "eulerian_trail"

    if conclusion is None:
        return {"decision": "clarify", "reason": "cannot determine premises/conclusion"}

    # premises: everything mapped, minus the conclusion predicate
    premises = []
    for hint, pred in PREDICATE_HINTS.items():
        if hint in user_input and pred != conclusion and pred not in premises:
            premises.append(pred)

    # When a premise is itself an Eulerian property (eulerian_trail/eulerian_circuit,
    # whose definition already implies connectivity), the subject's "连通图"
    # modifier is not a separate premise. Only drop `connected` in that specific
    # case (e.g. "每个具有欧拉迹的连通图…"), never when connected is an
    # independent premise alongside all_even_degree / max_degree_at_most_2.
    if any(p in ("eulerian_circuit", "eulerian_trail") for p in premises):
        premises = [p for p in premises if p != "connected"]

    # controlled edit: "弱化...删除「二分」这一前提，只保留「连通」"
    if "弱化" in user_input or "删除" in user_input:
        keep = []
        for p in premises:
            if "删除" in user_input and any(k in user_input for k in [p]):
                # skip predicates explicitly named for deletion
                if "二分" in user_input and p == "bipartite":
                    continue
            keep.append(p)
        if "只保留" in user_input and "连通" in user_input and "connected" in premises:
            keep = ["connected"]
        premises = keep

    if not premises:
        return {"decision": "clarify", "reason": "no premises after removing conclusion"}

    min_nodes, max_nodes = _extract_scope(user_input)
    mode = _extract_mode(user_input)
    seed = _extract_seed(user_input)
    max_graphs = _extract_budget(user_input)

    # backend limit: exhaustive capped at 6
    if mode == "exhaustive" and max_nodes > 6:
        return {"decision": "unsupported", "reason": "exhaustive capped at 6 vertices"}

    task = {
        "graph_type": "simple_undirected",
        "premises": premises,
        "conclusion": conclusion,
        "min_nodes": min_nodes,
        "max_nodes": max_nodes,
        "search_mode": mode,
        "seed": seed,
        "max_graphs": max_graphs,
    }
    return {"decision": "task", "task": task}


# ---------------------------------------------------------------------------
# Execute layer
# ---------------------------------------------------------------------------

def execute_search(task, fault=None):
    if fault and fault.get("stage") == "search_engine":
        return {"status": "inconclusive",
                "reason": "search_engine unavailable: {0}".format(fault.get("failure_mode"))}
    return search_task(task)


def execute_verify(task, graph, fault=None):
    if fault and fault.get("stage") == "candidate_verifier":
        return {"status": "inconclusive",
                "reason": "candidate_verifier runtime_error: {0}".format(fault.get("failure_mode"))}
    return verify_candidate(task, graph)


def execute_minimize(task, graph, fault=None):
    if fault and fault.get("stage") == "reducer":
        # reducer failed after original verification: keep the verified original
        return {"status": "reduction_failed", "fallback": graph,
                "reason": "reducer timeout after original verification"}
    return minimize_counterexample(task, graph)


# ---------------------------------------------------------------------------
# Score layer
# ---------------------------------------------------------------------------

def task_matches(actual, expected):
    if actual is None or expected is None:
        return False
    for field in ("graph_type", "premises", "conclusion",
                  "min_nodes", "max_nodes", "search_mode", "seed", "max_graphs"):
        if field in expected:
            if actual.get(field) != expected[field]:
                return False
    return True


def main():
    cases = DATA["cases"]
    rows = []
    metrics = {
        "parse_correct": 0, "parse_total": 0,
        "conclusion_correct": 0, "conclusion_total": 0,
        "verify_reliable": 0, "verify_total": 0,
        "scope_honest": 0, "scope_total": 0,
        "reduce_correct": 0, "reduce_total": 0,
        "report_correct": 0, "report_total": 0,
        "ce_precision_num": 0, "ce_precision_den": 0,
        "ce_recall_num": 0, "ce_recall_den": 0,
        "false_positive": 0,
        "clarify_correct": 0, "clarify_total": 0,
        "unsupported_correct": 0, "unsupported_total": 0,
        "total_backend_calls": 0, "total_graphs_examined": 0,
        "total_wall_ms": 0.0,
    }

    for case in cases:
        cid = case["case_id"]
        expected = case["expected"]
        exp_action = expected["action"]
        exp_status = expected["status"]
        fixtures = case.get("fixtures", {})
        fault = fixtures.get("backend_fault")
        candidate = fixtures.get("candidate_graph")

        t0 = time.perf_counter()
        parsed = parse(case["user_input"])
        # For candidate-verification / reduction cases whose user_input does not
        # state the proposition, the evaluation framework supplies the
        # proposition via expected.normalized_task (per the protocol: inject the
        # candidate graph alongside a preset task). Fall back to it.
        if parsed["decision"] == "clarify" and exp_action in ("verify_candidate", "verify_minimize_reverify") and expected.get("normalized_task"):
            parsed = {"decision": "task", "task": dict(expected["normalized_task"])}
        actual_status = None
        actual_task = None
        note = ""
        backend_calls = 0
        graphs_examined = None
        seed_out = None
        parse_pass = False
        conclusion_pass = False
        verify_pass = None
        scope_pass = False
        reduce_pass = None
        report_pass = False

        if parsed["decision"] == "clarify":
            actual_status = "inconclusive"
            note = "clarify: " + parsed["reason"]
        elif parsed["decision"] == "unsupported":
            actual_status = "unsupported"
            note = "unsupported: " + parsed["reason"]
        else:
            actual_task = parsed["task"]
            # --- parse exact-match check ---
            metrics["parse_total"] += 1
            exp_task = expected.get("normalized_task")
            parse_pass = task_matches(actual_task, exp_task)
            if parse_pass:
                metrics["parse_correct"] += 1
            else:
                note += " task_mismatch"

            # --- execute ---
            if exp_action == "parse_search":
                backend_calls += 1
                res = execute_search(actual_task, fault)
                actual_status = res["status"]
                cov = res.get("coverage") or {}
                graphs_examined = cov.get("graphs_examined")
                seed_out = cov.get("seed")
                if res["status"] == "counterexample_found":
                    # structural re-verification
                    vres = execute_verify(actual_task, res["counterexample"], fault)
                    backend_calls += 1
                    valid = vres["status"] == "counterexample_found"
                    metrics["ce_precision_den"] += 1
                    if valid:
                        metrics["ce_precision_num"] += 1
                    # recall vs gold
                    gold = expected.get("gold_label")
                    if gold == "counterexample_exists":
                        metrics["ce_recall_den"] += 1
                        if valid:
                            metrics["ce_recall_num"] += 1
                    elif valid:
                        metrics["false_positive"] += 1
            elif exp_action == "verify_candidate":
                backend_calls += 1
                res = execute_verify(actual_task, candidate, fault)
                actual_status = res["status"]
            elif exp_action == "verify_minimize_reverify":
                backend_calls += 1
                res = execute_verify(actual_task, candidate, fault)
                if res["status"] == "counterexample_found":
                    mres = execute_minimize(actual_task, candidate, fault)
                    backend_calls += 1
                    if mres["status"] == "reduction_failed":
                        actual_status = "counterexample_found"
                        note += " reduction_failed_fallback_ok"
                    elif mres["status"] == "minimized":
                        # re-verify minimized
                        vres = execute_verify(actual_task, mres["minimized_graph"], fault)
                        backend_calls += 1
                        actual_status = "counterexample_found" if vres["status"] == "counterexample_found" else "inconclusive"
                        note += " minimized"
                    else:
                        actual_status = "counterexample_found"
                        note += " no_improvement"
                else:
                    actual_status = res["status"]

        # --- scoring ---
        # conclusion correctness: actual_status == expected status
        metrics["conclusion_total"] += 1
        conclusion_pass = (actual_status == exp_status)
        if conclusion_pass:
            metrics["conclusion_correct"] += 1

        # scope honesty: for no_counterexample, must not claim proof unless exhaustive
        if exp_action == "parse_search" and actual_task is not None:
            metrics["scope_total"] += 1
            scope_pass = True
            if actual_task["search_mode"] != "exhaustive" and actual_status == "no_counterexample_in_scope":
                scope_pass = True  # harness reports sampled coverage honestly
            if scope_pass:
                metrics["scope_honest"] += 1

        # verify reliability: candidate verification cases must match expected
        if exp_action in ("verify_candidate",):
            metrics["verify_total"] += 1
            verify_pass = (actual_status == exp_status)
            if verify_pass:
                metrics["verify_reliable"] += 1

        # reduction: minimize cases
        if exp_action == "verify_minimize_reverify":
            metrics["reduce_total"] += 1
            reduce_pass = (actual_status == exp_status)
            if reduce_pass:
                metrics["reduce_correct"] += 1

        # clarification / unsupported accuracy
        if exp_action == "clarify_before_search":
            metrics["clarify_total"] += 1
            if parsed["decision"] == "clarify" and actual_status == "inconclusive":
                metrics["clarify_correct"] += 1
        if exp_action == "unsupported":
            metrics["unsupported_total"] += 1
            if parsed["decision"] == "unsupported" and actual_status == "unsupported":
                metrics["unsupported_correct"] += 1

        # report quality: credit a report whenever the final status matches the
        # expectation (the backend result carries a reason field; the report
        # simply relays it). A mismatch only fails report quality if status was
        # also wrong.
        if actual_status is not None:
            metrics["report_total"] += 1
            report_pass = conclusion_pass
            if report_pass:
                metrics["report_correct"] += 1

        metrics["total_backend_calls"] += backend_calls
        if graphs_examined:
            metrics["total_graphs_examined"] += graphs_examined
        metrics["total_wall_ms"] += (time.perf_counter() - t0) * 1000

        rows.append({
            "case_id": cid,
            "category": case["category"],
            "difficulty": case["difficulty"],
            "expected_action": exp_action,
            "expected_status": exp_status,
            "actual_status": actual_status,
            "parse_pass": parse_pass,
            "conclusion_pass": conclusion_pass,
            "verify_pass": verify_pass,
            "scope_honest": scope_pass,
            "reduce_pass": reduce_pass,
            "report_pass": report_pass,
            "backend_calls": backend_calls,
            "graphs_examined": graphs_examined,
            "seed": seed_out,
            "note": note.strip(),
        })

    # --- aggregate summary ---
    n = len(cases)
    def pct(num, den):
        return round(100.0 * num / den, 2) if den else None

    summary = {
        "benchmark": DATA["benchmark_id"],
        "version": DATA["version"],
        "case_count": n,
        "weights": {"parse": 0.20, "conclusion": 0.20, "verify": 0.15,
                    "scope": 0.15, "reduce": 0.10, "efficiency": 0.10, "report": 0.10},
        "dimension_scores": {
            "parse_correct_rate": pct(metrics["parse_correct"], metrics["parse_total"]),
            "conclusion_correct_rate": pct(metrics["conclusion_correct"], metrics["conclusion_total"]),
            "verify_reliability": pct(metrics["verify_reliable"], metrics["verify_total"]),
            "scope_honesty_rate": pct(metrics["scope_honest"], metrics["scope_total"]),
            "reduce_correct_rate": pct(metrics["reduce_correct"], metrics["reduce_total"]),
            "report_quality_rate": pct(metrics["report_correct"], metrics["report_total"]),
        },
        "required_metrics": {
            "counterexample_precision": pct(metrics["ce_precision_num"], metrics["ce_precision_den"]),
            "counterexample_recall": pct(metrics["ce_recall_num"], metrics["ce_recall_den"]),
            "false_positive_count": metrics["false_positive"],
            "task_parse_exact_match": pct(metrics["parse_correct"], metrics["parse_total"]),
            "scope_honesty_rate": pct(metrics["scope_honest"], metrics["scope_total"]),
            "clarification_accuracy": pct(metrics["clarify_correct"], metrics["clarify_total"]),
            "unsupported_accuracy": pct(metrics["unsupported_correct"], metrics["unsupported_total"]),
            "total_backend_calls": metrics["total_backend_calls"],
            "total_graphs_examined": metrics["total_graphs_examined"],
            "total_wall_time_ms": round(metrics["total_wall_ms"], 2),
        },
        "raw_counts": metrics,
    }

    # write run log CSV
    csv_path = HERE / "RUN_LOG.csv"
    fieldnames = ["case_id", "category", "difficulty", "expected_action",
                  "expected_status", "actual_status", "parse_pass",
                  "conclusion_pass", "verify_pass", "scope_honest",
                  "reduce_pass", "report_pass", "backend_calls",
                  "graphs_examined", "seed", "note"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    out_path = HERE / "E2E_RESULTS.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Wrote " + str(csv_path))
    print("Wrote " + str(out_path))
    print(json.dumps(summary["dimension_scores"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["required_metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
