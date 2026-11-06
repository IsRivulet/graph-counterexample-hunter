"""Score saved real sessions against separate frozen expectations (no model calls)."""

import argparse
from itertools import product
import json
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark.validation import verify_witness

HERE = Path(__file__).resolve().parent
DEFAULTS = {"graph_type": "simple_undirected", "min_nodes": 1, "max_nodes": 5,
            "search_mode": "exhaustive", "seed": None, "max_graphs": 2000}
ALIASES = {"max_degree_at_most_2": ("max_degree_at_most", 2), "min_degree_at_least_1": ("min_degree_at_least", 1)}
ZERO = {"connected", "bipartite", "tree", "eulerian_circuit", "eulerian_trail", "all_even_degree", "has_leaf", "has_cycle", "complete"}
PARAM = {"max_degree_at_most", "min_degree_at_least", "num_leaves_at_least", "chromatic_number_at_most", "diameter_at_most"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def expression(raw):
    if isinstance(raw, str):
        raw = {"predicate": raw}
    if not isinstance(raw, dict) or type(raw.get("negated", False)) is not bool:
        raise ValueError("Malformed predicate expression")
    if "or" in raw:
        if set(raw) - {"or", "negated"} or not isinstance(raw["or"], list) or not raw["or"]:
            raise ValueError("Malformed disjunction")
        tree = ("or", tuple(expression(x) for x in raw["or"]))
    else:
        if set(raw) - {"predicate", "k", "negated"}:
            raise ValueError("Unexpected expression field")
        name, k = raw["predicate"], raw.get("k")
        if name in ALIASES:
            if k is not None:
                raise ValueError("Alias with an unexpected parameter")
            name, k = ALIASES[name]
        if name in PARAM:
            if type(k) is not int or k < 1:
                raise ValueError("Invalid predicate parameter")
        elif name not in ZERO or k is not None:
            raise ValueError("Unknown predicate or unexpected parameter")
        tree = ("atom", (name, k))
    return ("not", tree) if raw.get("negated", False) else tree


def atoms(tree):
    if tree[0] == "atom":
        return {tree[1]}
    if tree[0] == "not":
        return atoms(tree[1])
    return set().union(*(atoms(x) for x in tree[1])) if tree[1] else set()


def value(tree, assignment):
    if tree[0] == "atom":
        return assignment[tree[1]]
    if tree[0] == "not":
        return not value(tree[1], assignment)
    values = (value(x, assignment) for x in tree[1])
    return all(values) if tree[0] == "and" else any(values)


def equivalent(left, right):
    keys = sorted(atoms(left) | atoms(right))
    if len(keys) > 16:
        raise ValueError("Semantic comparison exceeds 16 atoms")
    return all(value(left, dict(zip(keys, bits))) == value(right, dict(zip(keys, bits)))
               for bits in product((False, True), repeat=len(keys)))


def task_match(actual, expected):
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    # Compare the premises and conclusion separately: an impossible premise
    # must not hide an incorrectly translated conclusion.
    if any(actual.get(k, default) != expected.get(k, default) for k, default in DEFAULTS.items()):
        return False
    for key in ("min_nodes", "max_nodes", "max_graphs"):
        if type(actual.get(key, DEFAULTS[key])) is not int:
            return False
    if actual.get("seed") is not None and type(actual["seed"]) is not int:
        return False
    if not isinstance(actual.get("premises"), list) or not isinstance(expected.get("premises"), list):
        return False
    return (equivalent(("and", tuple(map(expression, actual["premises"]))),
                       ("and", tuple(map(expression, expected["premises"]))))
            and equivalent(expression(actual["conclusion"]), expression(expected["conclusion"])))


def same_graph(left, right):
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return (sorted(left["nodes"]) == sorted(right["nodes"])
            and sorted(tuple(sorted(e)) for e in left["edges"]) == sorted(tuple(sorted(e)) for e in right["edges"]))


def artifact(workspace, raw):
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError("Artifact paths must be relative to the case workspace")
    path = (workspace / raw).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError("Artifact path escapes workspace")
    return load(path)


def trace_commands(path):
    commands, usage = [], None
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "command_execution":
                commands.append({"command": item.get("command", ""), "stdout": item.get("aggregated_output", ""),
                                 "exit_code": item.get("exit_code"), "status": item.get("status")})
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
    return commands, usage


def command_has(command, token):
    token = token.replace("\\", "/")
    command = command.replace("\\", "/")
    return re.search(r"(?<![A-Za-z0-9_.-])" + re.escape(token) + r"(?![A-Za-z0-9_.-])", command) is not None


def command_arguments(command):
    """Accept one Python invocation, optionally wrapped by a normal shell launcher."""
    for _ in range(4):
        tokens = shlex.split(command, posix=False)
        tokens = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
        if not tokens:
            raise ValueError("Empty command")
        name = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        if name in ("powershell", "powershell.exe", "pwsh", "pwsh.exe", "bash", "sh", "zsh", "cmd.exe"):
            flag = next((i for i, t in enumerate(tokens) if t.lower() in ("-command", "-c", "-lc", "/c")), None)
            if flag is None or len(tokens) != flag + 2:
                raise ValueError("Unsupported shell wrapper")
            command = tokens[-1]
            continue
        if tokens[0] == "&":
            tokens = tokens[1:]
        if not tokens or not re.fullmatch(r"(?:python(?:\d+(?:\.\d+)*)?|py)(?:\.exe)?", tokens[0].replace("\\", "/").rsplit("/", 1)[-1], re.I):
            raise ValueError("Expected a single Python CLI invocation")
        if any(any(c in t for c in (";", "|", "\n", "\r", "`", "$", "#", ">", "<")) or t in ("&&", "&") for t in tokens):
            raise ValueError("Compound shell commands are not accepted as CLI evidence")
        return tokens
    raise ValueError("Too many shell wrappers")


def call_matches(event, call, script, workspace):
    try:
        if event.get("exit_code") != 0 or event.get("status") != "completed":
            return False
        tokens = command_arguments(event["command"])
        def path(raw):
            return (workspace / raw.replace("\\", "/")).resolve()
        if len(tokens) < 2 or path(tokens[1]) != (workspace / "scripts" / script).resolve():
            return False
        arguments = tokens[2:]
        options = {}
        while arguments:
            flag = arguments.pop(0)
            if flag == "--minimize":
                continue
            if flag not in ("--task", "--graph", "--output") or not arguments or flag in options:
                return False
            options[flag] = arguments.pop(0)
        wanted = {"--task": call["task_file"], "--output": call["result_file"]}
        if call["operation"] != "search":
            wanted["--graph"] = call["graph_file"]
        return set(options) == set(wanted) and all(path(options[k]) == path(v) for k, v in wanted.items())
    except (TypeError, ValueError):
        return False


def backend_records(report, folder, expected_task, commands):
    records = []
    last_command = -1
    result_paths = set()
    scripts = {"search": "search_engine.py", "verify": "verify_candidate.py", "minimize": "minimize_counterexample.py"}
    calls = report.get("backend_calls")
    if not isinstance(calls, list):
        raise ValueError("Missing backend_calls")
    for call in calls:
        operation = call["operation"]
        script = scripts[operation]
        matching = [i for i, event in enumerate(commands) if i > last_command
                    and call_matches(event, call, script, folder / "workspace")]
        if not matching:
            raise ValueError("No successful CLI trace matches a declared backend call")
        last_command = matching[0]
        result_path = (folder / "workspace" / call["result_file"]).resolve()
        if result_path in result_paths:
            raise ValueError("Backend result files must not be overwritten between calls")
        result_paths.add(result_path)
        task = artifact(folder / "workspace", call["task_file"])
        if not task_match(task, expected_task):
            raise ValueError("Backend was called with a different task")
        result = artifact(folder / "workspace", call["result_file"])
        if json.loads(commands[last_command]["stdout"]) != result:
            raise ValueError("Result file differs from the successful CLI stdout")
        graph = artifact(folder / "workspace", call["graph_file"]) if operation != "search" else None
        if operation != "minimize" and not task_match(result.get("task"), expected_task):
            raise ValueError("Backend result task differs from the expected task")
        records.append({"operation": operation, "result": result, "input_graph": graph})
    return records


def local_minimum(task, graph):
    for node in graph["nodes"]:
        candidate = {"nodes": [v for v in graph["nodes"] if v != node],
                     "edges": [e for e in graph["edges"] if node not in e]}
        if verify_witness(task, candidate)["valid"]:
            return False
    for index in range(len(graph["edges"])):
        if verify_witness(task, dict(graph, edges=graph["edges"][:index] + graph["edges"][index + 1:]))["valid"]:
            return False
    return True


def score_case(row, expected, folder, manual):
    checks = {"execution": row["exit_code"] == 0 and not row["timed_out"] and row["runtime_unchanged"]}
    result = {"id": row["id"], "checks": checks, "error": None, "usage": None,
              "claims_counterexample": False, "witness_valid": None}
    try:
        report = load(folder / "final.json")
        commands, result["usage"] = trace_commands(folder / "events.jsonl")
        required = {"schema_version", "action", "status", "mode", "task", "counterexample", "coverage", "checks",
                    "evidence", "minimization", "minimality", "reason", "clarification", "backend_calls"}
        checks["protocol"] = (required <= set(report) and report.get("schema_version") == "mathcheck.e2e.v1" and report.get("mode") == "live"
                              and isinstance(report.get("reason"), str) and bool(report["reason"].strip()))
        checks["action"] = report.get("action") == expected["action"]
        checks["status"] = report.get("status") == expected["status"]
        result["claims_counterexample"] = report.get("status") == "counterexample_found"
        task = expected.get("task")
        if expected["action"] in ("clarify", "unsupported"):
            checks["no_backend_calls"] = report.get("backend_calls") == [] and not any(
                command_has(c["command"], script) for c in commands
                for script in ("search_engine.py", "verify_candidate.py", "minimize_counterexample.py"))
            checks["no_witness"] = report.get("counterexample") is None and report.get("coverage") is None
            if expected["action"] == "clarify":
                checks["clarification"] = isinstance(report.get("clarification"), str) and bool(report["clarification"].strip())
        else:
            checks["task_semantics"] = task_match(report.get("task"), task)
            records = backend_records(report, folder, task, commands)
            operation = expected["action"]
            primary = [r for r in records if r["operation"] == operation]
            checks["tool_evidence"] = bool(primary)
            if not primary:
                raise ValueError("Required backend operation is missing")
            # A candidate task may verify the original, then the reduced graph.
            # Bind its primary operation to the user's original candidate.
            primary_record = primary[0] if operation == "verify" else primary[-1]
            backend = primary_record["result"]
            checks["backend_status"] = backend.get("status") == report.get("status")
            if operation == "verify":
                candidate = load(folder / "input.json").get("candidate_graph")
                checks["candidate_preserved"] = same_graph(primary_record["input_graph"], candidate)
            coverage = backend.get("coverage")
            checks["coverage_matches"] = report.get("coverage") == coverage
            if operation == "search":
                coverage = coverage or {}
                checks["coverage_mode"] = coverage.get("search_mode") == task.get("search_mode", "exhaustive")
                checks["coverage_range"] = (coverage.get("min_nodes") == task.get("min_nodes", 1)
                                             and coverage.get("max_nodes") == task.get("max_nodes", 5))
                if report.get("status") == "verified_true_in_scope":
                    total = sum(1 << (n * (n - 1) // 2) for n in range(task.get("min_nodes", 1), task.get("max_nodes", 5) + 1))
                    checks["exhaustion"] = (coverage.get("search_mode") == "exhaustive" and coverage.get("fully_exhausted") is True
                                            and coverage.get("graphs_evaluated") == total)
                elif report.get("status") == "no_counterexample_in_scope":
                    checks["sample_scope"] = coverage.get("search_mode") in ("random", "special") and coverage.get("fully_exhausted") is False
            if result["claims_counterexample"]:
                graph = report.get("counterexample")
                independent = verify_witness(task, graph)
                result["witness_valid"] = independent["valid"]
                checks["independent_witness"] = independent["valid"]
                verified = [r["result"] for r in records if r["operation"] == "verify"
                            and r["result"].get("status") == "counterexample_found"
                            and same_graph(r["result"].get("counterexample"), graph)
                            and same_graph(r["input_graph"], graph)]
                checks["explicit_reverification"] = bool(verified)
                checks["reported_checks"] = bool(verified) and report.get("checks") == verified[-1].get("checks")
                checks["reported_evidence"] = bool(verified) and report.get("evidence") == verified[-1].get("evidence")
                reductions = [r["result"] for r in records if r["operation"] == "minimize"]
                reductions += [r["result"]["minimization"] for r in records if r["operation"] == "search" and r["result"].get("minimization")]
                if expected.get("require_minimization", True):
                    checks["reduction_recorded"] = bool(reductions) and report.get("minimization") == reductions[-1]
                    if reductions:
                        reduced = reductions[-1]
                        checks["reduction_chain"] = (same_graph(reduced.get("original_graph"), backend.get("counterexample"))
                                                     and any((r["operation"] == "minimize" and r["result"] == reduced
                                                              and same_graph(r["input_graph"], reduced.get("original_graph")))
                                                             or (r["operation"] == "search" and r["result"].get("minimization") == reduced)
                                                             for r in records))
                        checks["reduced_witness"] = verify_witness(task, reduced.get("minimized_graph"))["valid"]
                        checks["reduction_did_not_grow"] = (len(reduced["minimized_graph"]["nodes"]), len(reduced["minimized_graph"]["edges"])) <= (len(reduced["original_graph"]["nodes"]), len(reduced["original_graph"]["edges"]))
                        checks["reduction_reverified"] = any(r["operation"] == "verify" and r["result"].get("status") == "counterexample_found"
                                                                 and same_graph(r["input_graph"], reduced.get("minimized_graph")) for r in records)
                permitted = [backend.get("counterexample")]
                permitted += [r.get("minimized_graph") for r in reductions
                              if same_graph(r.get("original_graph"), backend.get("counterexample"))]
                checks["reported_graph_in_chain"] = any(same_graph(graph, g) for g in permitted)
                minimum = report.get("minimality") or {}
                checks["no_unproven_edge_minimum"] = minimum.get("edge_minimum_at_minimum_vertices", False) is False
                if minimum.get("vertex_minimum_in_scope"):
                    checks["vertex_minimum_evidence"] = (operation == "search" and coverage.get("search_mode") == "exhaustive"
                                                         and backend.get("minimality", {}).get("vertex_minimum_in_scope") is True
                                                         and len(graph["nodes"]) == len(backend["counterexample"]["nodes"])
                                                         and minimum.get("scope") == [task.get("min_nodes", 1), task.get("max_nodes", 5)])
                if minimum.get("local_single_deletion_minimum"):
                    checks["local_minimum_evidence"] = independent["valid"] and local_minimum(task, graph)
            else:
                checks["no_witness"] = report.get("counterexample") is None
                checks["reported_checks"] = report.get("checks") == backend.get("checks")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        result["error"] = str(exc)
        checks["artifacts_readable_and_consistent"] = False
    result["automatic_pass"] = all(v is True for v in checks.values())
    review = manual.get(row["id"])
    needs_review = expected.get("manual_required", False)
    result["manual_required"] = needs_review
    result["manual_review"] = review
    approval = review.get("approved") if isinstance(review, dict) else None
    result["strict_pass"] = (None if needs_review and approval is None and result["automatic_pass"]
                             else result["automatic_pass"] and (not needs_review or approval is True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, default=HERE / "expectations.json")
    parser.add_argument("--manual-review", type=Path, help='JSON mapping case ID to {"approved": bool, "notes": str}')
    parser.add_argument("--output", type=Path, help="defaults to RUN/scores.json")
    args = parser.parse_args()
    try:
        manifest = load(args.run / "manifest.json")
        if manifest.get("schema_version") != "mathcheck.e2e.run.v1":
            raise ValueError("Unknown run manifest version")
        if (len(set(manifest["case_ids"])) != len(manifest["case_ids"])
                or any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in manifest["case_ids"])):
            raise ValueError("Invalid or duplicate run case IDs")
        expected_rows = load(args.expectations)["cases"]
        expectations = {r["id"]: r for r in expected_rows}
        if len(expectations) != len(expected_rows):
            raise ValueError("Duplicate expectation IDs")
        manual = load(args.manual_review) if args.manual_review else {}
        execution = {r["id"]: r for r in manifest["cases"]}
        rows = []
        for case_id in manifest["case_ids"]:
            row = execution.get(case_id, {"id": case_id, "exit_code": None, "timed_out": False, "runtime_unchanged": False})
            rows.append(score_case(row, expectations[case_id], args.run / case_id, manual))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    claims = sum(r["claims_counterexample"] for r in rows)
    valid = sum(r["witness_valid"] is True for r in rows)
    gold_positive = sum(expectations[r["id"]]["status"] == "counterexample_found" for r in rows)
    detected = sum(r["witness_valid"] is True and expectations[r["id"]]["status"] == "counterexample_found" for r in rows)
    dimensions = sorted({k for r in rows for k in r["checks"]})
    summary = {"schema_version": "mathcheck.e2e.scores.v1", "case_count": len(rows),
               "model_requested": manifest["model_requested"],
               "automatic_pass_count": sum(r["automatic_pass"] for r in rows),
               "strict_pass_count": sum(r["strict_pass"] is True for r in rows),
               "pending_review_count": sum(r["strict_pass"] is None for r in rows),
               "strict_pass_rate": sum(r["strict_pass"] is True for r in rows) / len(rows) if rows else None,
               "counterexample_precision": valid / claims if claims else None,
               "counterexample_recall": detected / gold_positive if gold_positive else None,
               "invalid_counterexample_count": claims - valid,
               "dimensions": {k: {"passed": sum(r["checks"].get(k) is True for r in rows),
                                  "applicable": sum(k in r["checks"] for r in rows)} for k in dimensions},
               "notes": ["Structural/Boolean semantics are automatic; natural-language reason and clarification quality need human review.",
                         "CLI trace and artifacts are consistency evidence, not a tamper-proof audit or OS isolation boundary.",
                         "Published starter cases are development cases, not a held-out generalization benchmark."],
               "cases": rows}
    target = args.output or args.run / "scores.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote " + str(target))
    return 0 if rows and all(r["strict_pass"] is True for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
