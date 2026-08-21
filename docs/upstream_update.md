# Controlled LanguageTool upstream update

The compatibility target is LanguageTool 6.8 commit
`e807fcde6a6506191e1470744d2345da28c26be6`. Updating it is a separate compatibility
campaign, never an incidental dependency refresh.

1. Fetch the proposed exact commit into a temporary upstream checkout; never target a
   floating branch.
2. Update `third_party/languagetool/UPSTREAM.json` and regenerate the source inventory
   with `python -m tools.upstream_inventory`.
3. Compare old and proposed inventories with
   `python -m tools.upstream_diff --baseline <old-inventory> --target <new-inventory>`;
   run `python -m tools.upstream_diff --help` for the exact CLI contract.
4. Inspect every added, removed, or changed rule, XML construct, filter, Java rule,
   dictionary, and runtime resource. Unsupported behavior must remain explicit.
5. Re-run the relevant extraction tools under `tools/` and regenerate affected oracle
   fixtures and compatibility inventories.
6. Run grammar examples, translated upstream-test parity, ordinary rule/filter parity,
   resource-hash tests, and the full Java-free test suite.
7. Build and validate the exact proposed Java oracle, then rerun the Task 0014
   differential campaign and account for every non-comparable or mismatching case.
8. Reconcile changed shipped files with `third_party/languagetool/license_inventory.json`;
   mark unclear provenance `BLOCKED_LICENSE_REVIEW` and do not ship it.
9. Run Task 0015 release preflight on wheel and sdist across the supported Python and
   platform matrix.
10. Only after reviewed evidence is committed may documentation name the new pin.

Never overwrite old evidence in a way that makes the transition unauditable, and never
publish as part of the update unless publication is separately authorized.
