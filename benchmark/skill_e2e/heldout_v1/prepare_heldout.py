"""Freeze the stratified 12-case evaluation split and runtime hashes."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_DIR = HERE.parent / "formal_v1"
CASE_IDS = [
    "E2E-03", "E2E-04", "E2E-09", "E2E-11", "E2E-14", "E2E-17",
    "E2E-20", "E2E-22", "E2E-25", "E2E-32", "E2E-33", "E2E-39",
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_cases = {row["id"]: row for row in load(SOURCE_DIR / "cases.json")["cases"]}
    source_expectations = {row["id"]: row for row in load(SOURCE_DIR / "expectations.json")["cases"]}
    missing = set(CASE_IDS) - source_cases.keys() | (set(CASE_IDS) - source_expectations.keys())
    if missing:
        raise ValueError(f"Missing selected cases or labels: {sorted(missing)}")

    (HERE / "cases.json").write_text(json.dumps({
        "description": "Frozen 12-case paired evaluation split; E2E-01/02 were used for development smoke runs and are excluded.",
        "cases": [source_cases[i] for i in CASE_IDS],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "expectations.json").write_text(json.dumps({
        "description": "Frozen labels for independent scoring; do not copy into model workspaces.",
        "cases": [source_expectations[i] for i in CASE_IDS],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    runtime_paths = [ROOT / "SKILL.md", ROOT / "references" / "e2e-report.md", ROOT / "VERSION"]
    manifest = {
        "split": "MathCheck-E2E heldout_v1 paired evaluation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_ids": CASE_IDS,
        "excluded_development_cases": ["E2E-01", "E2E-02"],
        "cases_sha256": digest(HERE / "cases.json"),
        "expectations_sha256": digest(HERE / "expectations.json"),
        "frozen_runtime_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in runtime_paths},
    }
    (HERE / "freeze_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen {len(CASE_IDS)} cases: {', '.join(CASE_IDS)}")


if __name__ == "__main__":
    main()
