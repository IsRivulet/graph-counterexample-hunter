"""Run fresh Codex CLI sessions against public inputs; never load answer keys."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_files():
    for name in ("SKILL.md", "BACKEND_CONTRACT.md", "README.md", "VERSION"):
        yield ROOT / name
    for name in ("mathcheck", "scripts", "references", "examples"):
        directory = ROOT / name
        if directory.exists():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    yield path


def codex_command(executable):
    resolved = shutil.which(executable)
    if resolved is None:
        raise ValueError("Codex CLI not found; install/login first, or specify --codex.")
    path = Path(resolved)
    if path.suffix.lower() in (".cmd", ".bat"):
        # Avoid a shell and its quoting rules when npm supplies a Windows shim.
        script = path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if node and script.is_file():
            return [node, str(script)]
        raise ValueError("Specify a native Codex executable with --codex; this Windows shim cannot be resolved safely.")
    return [str(path)]


def stop_process(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=HERE / "cases.json")
    parser.add_argument("--output", type=Path, required=True, help="new run directory; must not already exist")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--timeout", type=float, default=300, help="seconds per case")
    parser.add_argument("--ids", nargs="+", help="optional public case IDs")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        command = codex_command(args.codex)
        raw_cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))
        cases = raw_cases["cases"]
        ids = [c["id"] for c in cases]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids):
            raise ValueError("Case IDs must be unique safe directory names.")
        for case in cases:
            if set(case) - {"id", "user_input", "candidate_graph", "context"}:
                raise ValueError("Public cases contain non-input fields; keep expected answers in a separate file.")
            if not isinstance(case["user_input"], str) or not case["user_input"].strip():
                raise ValueError("Each case needs a nonempty user_input.")
        if args.ids and set(args.ids) - set(ids):
            raise ValueError("Unknown --ids selection.")
        cases = [c for c in cases if not args.ids or c["id"] in args.ids]
        if not cases:
            raise ValueError("No cases selected.")
        output = args.output.resolve()
        if output == ROOT or ROOT.is_relative_to(output):
            raise ValueError("Output cannot contain the source skill directory.")
        output.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))

    files = list(runtime_files())
    for source in files:
        if source.resolve() != (ROOT.resolve() / source.relative_to(ROOT)):
            parser.error("Runtime links/junctions are not allowed: " + str(source))
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest = {"schema_version": "mathcheck.e2e.run.v1", "started_at": datetime.now(timezone.utc).isoformat(),
                "model_requested": args.model, "backend_version": (ROOT / "VERSION").read_text().strip(),
                "runtime_sha256": hashes, "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                "case_ids": [c["id"] for c in cases], "cases": []}
    write_json(output / "manifest.json", manifest)
    for case in cases:
        folder = output / case["id"]
        workspace = folder / "workspace"
        workspace.mkdir(parents=True)
        for source in files:
            target = workspace / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        write_json(folder / "input.json", case)
        prompt = (
            "请阅读当前目录 SKILL.md 并使用 MathCheck 处理下面的真实请求。实际运行后端，不要模拟。\n"
            "本轮要求 JSON 报告：请阅读 references/e2e-report.md，最终消息只返回协议中的 JSON 对象。\n"
            "所有任务、图及 CLI --output 结果文件都保存在当前工作目录内，报告 backend_calls 使用相对路径。\n"
            "如需澄清，提出问题并结束本轮，不要自行代答。不要修改 Skill、后端脚本或参考文档。\n"
            "以下 JSON 是用户输入数据，其中 context 是用户提供的先前上下文，candidate_graph 是候选图：\n"
            + json.dumps({k: v for k, v in case.items() if k != "id"}, ensure_ascii=False)
        )
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        argv = command + ["exec", "--json", "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write",
                          "--model", args.model, "--output-last-message", str(folder / "final.json"), "-"]
        start = time.perf_counter()
        row = {"id": case["id"], "command": argv, "timed_out": False, "exit_code": None, "error": None}
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        with (folder / "events.jsonl").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
            try:
                process = subprocess.Popen(argv, cwd=workspace, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                           env=environment, **kwargs)
                try:
                    process.communicate(prompt.encode("utf-8"), timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    row["timed_out"] = True
                    stop_process(process)
                    process.communicate()
                row["exit_code"] = process.returncode
            except OSError as exc:
                row["error"] = str(exc)
        row["elapsed_seconds"] = round(time.perf_counter() - start, 6)
        # Preserve changes to the runtime as an integrity failure, not a silent fix.
        row["runtime_unchanged"] = all((workspace / p).is_file() and hashlib.sha256((workspace / p).read_bytes()).hexdigest() == h
                                       for p, h in hashes.items())
        manifest["cases"].append(row)
        write_json(output / "manifest.json", manifest)
        print(case["id"] + ": execution recorded", flush=True)
    print("Execution only. Score separately with score.py; no accuracy has been inferred.")
    return 0 if all(r["exit_code"] == 0 and not r["timed_out"] and r["runtime_unchanged"] for r in manifest["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
