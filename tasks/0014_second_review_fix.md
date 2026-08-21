# Task 0014 — Second Review-Fix

Review baseline: `af4f64da366b87cb9ea46005c1053dad9faa9d60`.

Pinned LanguageTool: 6.8 at
`e807fcde6a6506191e1470744d2345da28c26be6`; trusted oracle build
`lt_6.8_source_build_jdk17_stefan`, JAR SHA-256
`b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`.

## Required corrections

1. Replace the invalid `cfg_long_paragraph_30` → `ref_picky` sensitivity pair
   with an enabled PICKY reference that retains pinned `maxWords=220`, so only
   `TOO_LONG_PARAGRAPH.maxWords` differs.
2. Validate every config-sensitivity pair fail-closed: enablement, disabled rules,
   level, and default-off state must be identical, and only the declared rule options
   may differ.
3. Make LongSentence word counting use the first UTF-16 code unit exactly as pinned
   Java does. A supplementary-plane letter such as U+10400 must not count.
4. Add direct, oracle-backed, and whole-pipeline PICKY regressions for the
   supplementary-letter threshold distinction, while preserving existing non-BMP
   coverage.
5. Rerun the complete deterministic differential campaign and regenerate all Task
   0014 manifests, summaries, fixtures, hashes, state-isolation evidence, compatibility
   metadata, and the authoritative report.

## Acceptance

- At least 8,000 unique texts and 12,000 profile executions.
- All Java-returned ordinary cases match the strict ordered Finding sequence exactly.
- Zero unexplained ordinary discrepancies and zero ordinary allowlist entries.
- Every required config target has a Java delta, the same Python delta, and exact
  target output.
- Supplementary-letter coverage is nonzero and every comparable case is exact.
- Focused and full pytest runs have zero failures, errors, and skips.
- Wheel and state/order isolation pass.
- One final commit is pushed to `main`, and both Python 3.10 and 3.12 Actions jobs run
  against that exact SHA. Do not start Task 0015.
