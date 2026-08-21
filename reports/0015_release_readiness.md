# Task 0015 — Packaging, performance, release readiness, and stable public API

## Baseline and scope

Baseline: `a80dfcfe019ee1cd6ffd26feee2a9313f60c195f`.

This task stabilizes and documents the already accepted implementation. It adds release
metadata, artifact audits, clean-install smoke coverage, CI release preflight, performance
measurement, and an upstream-update runbook. The LanguageTool pin and checking semantics
were not changed. The only production-source change exports the existing `LEVEL_DEFAULT`
and `LEVEL_PICKY` constants.

The version remains `0.1.0a0`: release readiness does not itself justify implying a
published or release-candidate build.

## API and documentation

The stable primary surface is `LanguageToolRU`, `RuleMatch`, and `__version__`, with
`LEVEL_DEFAULT` and `LEVEL_PICKY` as documented constants. Existing lower-level exports
remain advanced/provisional and were not removed. `compat/public_api_0015.json` records
signatures, exports, ordered `RuleMatch` fields/defaults, checking levels, and coordinate
domains. README examples for basic checking, rule enable/disable, configuration, checking
levels, and offsets are executable tests.

`offset`/`length` are Python code-point coordinates; `utf16_offset`/`utf16_length` are
Java-compatible UTF-16 code-unit coordinates. Unknown levels/configuration and missing
resources remain fail-closed. `docs/upstream_update.md` documents the controlled update
sequence without moving the pin.

## Packaging and platform policy

Package: `pylat_ru 0.1.0a0`, Python `>=3.10`, runtime dependency `regex` only.
Linux 3.10/3.12 retain full-test CI; Python 3.11 receives installed-artifact smoke; Linux
3.12 runs release preflight; Windows 3.12 installs and checks the exact Linux-built pure
Python wheel. Exact-final-SHA results belong in the final handoff, avoiding SHA recursion.

Local Windows/Python 3.10 release-preflight results:

- wheel `pylat_ru-0.1.0a0-py3-none-any.whl`: 6,327,561 bytes, 99 files;
- sdist `pylat_ru-0.1.0a0.tar.gz`: 6,301,810 bytes, 106 files;
- runtime resources: 30 files, 10,881,559 uncompressed bytes;
- `twine check`: wheel PASS, sdist PASS, README metadata PASS;
- forbidden wheel files: 0; forbidden sdist local/cache/corpus/oracle files: 0;
- fresh wheel install outside repository: PASS; `pip check`: PASS;
- fresh sdist build/install outside repository: PASS; `pip check`: PASS;
- XML grammar, native rule, spelling, DEFAULT/PICKY, configuration, non-BMP offsets,
  no-socket/no-subprocess, and separate-instance concurrency smoke: PASS.

The largest runtime members are `russian.dict` (2,322,253 bytes), `ru_RU.dict`
(1,889,147), `ru_RU_yo.dict` (1,783,672), `russian_synth.dict` (1,481,255), and
`grammar.xml` (1,194,903). No duplicate oracle/test payload appeared in the wheel.

Two clean builds used `SOURCE_DATE_EPOCH=1700000000`. Wheel bytes were identical; sdist
gzip bytes were not, but normalized member sets, sizes, and content hashes were identical.
This proves semantic member reproducibility, not byte-identical sdist output.

## Licensing and provenance

Root LGPL license metadata is coherent with repository policy. The wheel contains the
root license, LanguageTool copying text, and third-party license notes. The built-wheel
hashes for `grammar.xml`, `russian.dict`, `russian_synth.dict`, and `disambiguation.xml`
reconcile exactly to verified LGPL entries in the existing inventory. Existing inventory
tests continue to cover the broader source resource set; no blocked license entry is
silently shipped. This is an evidence audit, not a new legal conclusion.

## Performance baseline

Measured on Windows 10, CPython 3.10.11, on a 32-logical-CPU AMD64 Family 26 Model 68
host. Values are a local regression baseline, not an SLA or a cross-platform speed
claim. Three in-process construction samples had median 0.248 s and p95 0.275 s.

| Warm case | Code points | Median (s) | p95 (s) | chars/s |
|---|---:|---:|---:|---:|
| short clean | 135 | 0.0334 | 0.0358 | 4,040 |
| short errors | 64 | 0.0235 | 0.0240 | 2,725 |
| spelling-heavy | 62 | 0.0177 | 0.0183 | 3,499 |
| medium | 1,870 | 0.9640 | 0.9665 | 1,940 |
| long | 10,750 | 3.1364 | 3.1733 | 3,427 |
| PICKY | 25 | 0.0164 | 0.0167 | 1,522 |
| configured speller | 50 | 0.0243 | 0.0249 | 2,054 |

Working-set RSS was 23,072,768 bytes before construction, 64,282,624 after construction,
230,993,920 after warmup, and 248,016,896 after the bounded soak. The 100-check mixed
soak completed in 3.470 s and grew by 282,624 bytes between its immediate endpoints.
Bounded caches and resource reuse have structural tests; CI has no flaky micro-timing gate.

## Compatibility, limitations, and publication

The committed Task 0014 parity/regression evidence remains the compatibility authority:
892/892 XML rules, 2,446/2,446 grammar examples, 907/907 variants, 23/23 ordinary Java
ports, 7/7 filters, and 16,834/16,834 exact comparable campaign cases with zero ordinary
unexplained discrepancies. The 37 documented non-comparable paragraph-repeat cases remain
an upstream defect, not Python failures.

`RussianConfusionProbabilityRule` remains `LANGUAGE_MODEL_DEFERRED`. No LanguageTool pin
upgrade, PyPI/TestPyPI upload, GitHub Release, or tag was performed. Publication status:
`NOT PUBLISHED`.

Full local pytest: 1,152 passed, 0 failed, 0 errors, 0 skipped on Windows/Python
3.10.11. Exact-final-SHA CI run IDs and final artifact hashes are intentionally recorded
only in the final handoff.
