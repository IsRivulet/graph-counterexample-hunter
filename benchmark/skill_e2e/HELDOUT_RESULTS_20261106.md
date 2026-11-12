# 12-case paired evaluation (2026-11-06)

## Frozen setup

- Split: `heldout_v1`, selected from the remaining formal cases after excluding development smoke cases E2E-01/02.
- Cases: E2E-03, E2E-04, E2E-09, E2E-11, E2E-14, E2E-17, E2E-20, E2E-22, E2E-25, E2E-32, E2E-33, E2E-39.
- Both conditions used `gpt-6-luna`, fresh sessions, the same input/expectation files, backend version and 300-second per-case timeout.
- Frozen `SKILL.md` SHA-256: `a4ca77fb227f2903bb3e08fe426eeebb96a8119dc0ea765d7cfeda6271925de2`.
- The baseline workspace omitted `SKILL.md`; all 12 cases completed in each group with zero timeouts and zero nonzero CLI exits.

## Automatic score and efficiency

| Measure | Skill | Baseline |
|---|---:|---:|
| Automatic pass | 8/12 (66.7%) | 7/12 (58.3%) |
| Counterexample recall | 4/6 (66.7%) | 4/6 (66.7%) |
| Counterexample precision | 4/4 (100%) | 4/7 (57.1%) |
| Unverified/invalid counterexample claims | 0 | 3 |
| Timeouts | 0 | 0 |
| Total wall time | 1,366.3 s | 1,238.8 s |
| Median / P95 wall time | 87.6 / 208.0 s | 96.1 / 167.6 s |
| Total input tokens | 1,544,707 | 1,902,771 |
| Median / P95 input tokens | 102,598 / 240,391 | 131,938 / 240,345 |
| Total output tokens | 18,983 | 23,354 |
| Median / P95 output tokens | 1,167 / 3,737 | 1,788 / 3,354 |

On this sample, Skill used about 18.8% fewer input tokens and 18.7% fewer output tokens, while total elapsed time was about 10.3% higher. Median time was lower, but P95 time was higher. Token use and latency vary considerably by case, so these are descriptive results only.

The Skill group's four oracle-accepted counterexample reports and the baseline group's four oracle-accepted reports each received a provisional mean quality score of **5/6**: size/simplicity 1, explanation 2, evidence/claims 2. None had oracle-proven global minimum edge count. This is a single-reviewer result, not a clean independent blind comparison; see the review note below.

## Paired case findings

- The revised Skill completed the required search/verify/minimize/reverify chain on its four automatically accepted counterexamples (E2E-03, E2E-14, E2E-32, E2E-39). In E2E-39 it reduced the provided five-vertex candidate to a four-cycle and independently verified it.
- The baseline made three counterexample claims that the frozen scorer could not validate, including treating a multigraph request as a simple-graph search and using the wrong action or task on candidate cases. The Skill correctly returned `unsupported` on the multigraph case and clarified the explicitly ambiguous “Euler graph” case.
- Skill automatic failures were E2E-04 and E2E-11 (it asked for clarification while the frozen key expects a search), E2E-09 (the report is correct but the scorer could not match a declared CLI call to the event trace), and E2E-20 (the final response is not a single valid JSON object). The two Euler cases merit manual adjudication because the Skill's definition says to clarify when terminology or conventions could change truth; the trace mismatch is an evidence-format failure, while E2E-20 is a report-protocol failure.
- The score file still shows zero strict passes because the benchmark marks natural-language cases for manual review. Automatic pass and strict pass are different here.

## Review limitation

`heldout_v1/blind_review_packets.json` and `blind_review_template.csv` contain condition-anonymized review material. I had already inspected condition-coded automatic summaries before rating the packets, so those ratings are provisional and should not be described as fully blind. `blind_review_map.json` contains the unblinding map. For a defensible final submission, have another reviewer rate the anonymized packets without opening the map, then compare or replace the provisional ratings.

## Artifacts

- Frozen split and hashes: `heldout_v1/freeze_manifest.json`
- Skill run and scores: `runs/heldout-v1-skill-20261106/`
- Baseline run and scores: `runs/heldout-v1-baseline-20261106/`
- Anonymized review packets and template: `heldout_v1/`
