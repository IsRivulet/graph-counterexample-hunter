"""Prepare condition-anonymized report packets and a separate unblinding map."""

import csv
import json
import secrets
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "runs"
CONDITIONS = {
    "skill": RUNS / "heldout-v1-skill-20261106",
    "baseline": RUNS / "heldout-v1-baseline-20261106",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    cases = {row["id"]: row for row in load(HERE / "cases.json")["cases"]}
    packet_rows, map_rows = [], []
    prompt_ids = {case_id: f"P{index:02d}" for index, case_id in enumerate(cases, start=1)}
    aliases = [f"R-{secrets.token_hex(3)}" for _ in range(len(cases) * len(CONDITIONS))]
    index = 0
    for condition, run_dir in CONDITIONS.items():
        for case_id, case in cases.items():
            raw = (run_dir / case_id / "final.json").read_text(encoding="utf-8-sig")
            try:
                parsed = json.loads(raw)
                # Hide execution and environment metadata while retaining evidence and reasoning.
                report = {k: v for k, v in parsed.items() if k not in {"backend_calls", "mode", "schema_version"}}
            except json.JSONDecodeError:
                report = {"parse_error": "Final response is not a single valid JSON object.", "raw_response": raw}
            blind_id = aliases[index]
            index += 1
            packet_rows.append({"blind_id": blind_id, "prompt_id": prompt_ids[case_id],
                                "user_input": case["user_input"], "report": report})
            map_rows.append({"blind_id": blind_id, "prompt_id": prompt_ids[case_id],
                             "case_id": case_id, "condition": condition})
    secrets.SystemRandom().shuffle(packet_rows)
    (HERE / "blind_review_packets.json").write_text(json.dumps({
        "instructions": "Rate the report without looking at blind_review_map.json. Pair outputs using prompt_id.",
        "rubric": {"size_and_simplicity": "0-2", "mathematical_explanation": "0-2", "evidence_and_claims": "0-2"},
        "packets": packet_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "blind_review_map.json").write_text(json.dumps(map_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (HERE / "blind_review_template.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["blind_id", "prompt_id", "witness_valid", "size_and_simplicity_0_2",
                                                    "mathematical_explanation_0_2", "evidence_and_claims_0_2", "notes"])
        writer.writeheader()
        for row in packet_rows:
            writer.writerow({"blind_id": row["blind_id"], "prompt_id": row["prompt_id"]})
    print(f"Prepared {len(packet_rows)} anonymized report packets.")


if __name__ == "__main__":
    main()
