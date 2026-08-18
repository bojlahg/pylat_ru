#!/usr/bin/env python3
"""tools/differential_lt.py

Development-only differential oracle harness for comparing pylat_ru against
official pinned Java LanguageTool.

IMPORTANT:
- This tool is strictly DEV/TEST only.
- Production code must never import or depend on this module.
- Absence of Java/LanguageTool does not break pylat_ru package imports or execution.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


PINNED_LT_VERSION = "6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"


@dataclass(frozen=True)
class Finding:
    """Standardized finding representation for differential comparisons."""

    rule_id: str
    category_id: str
    message: str
    offset: int
    length: int
    suggestions: List[str]
    source: str  # "java_lt" or "pylat_ru"


@dataclass(frozen=True)
class DifferentialComparisonResult:
    """Structured differential comparison result between Java LT and pylat_ru."""

    text: str
    java_findings: List[Finding]
    pylat_findings: List[Finding]
    finding_count_match: bool
    matching_rule_ids: List[str]
    missing_in_pylat: List[str]
    extra_in_pylat: List[str]
    span_matches: int
    suggestion_matches: int
    is_exact_match: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "java_findings_count": len(self.java_findings),
            "pylat_findings_count": len(self.pylat_findings),
            "finding_count_match": self.finding_count_match,
            "is_exact_match": self.is_exact_match,
            "matching_rule_ids": self.matching_rule_ids,
            "missing_in_pylat": self.missing_in_pylat,
            "extra_in_pylat": self.extra_in_pylat,
            "span_matches": self.span_matches,
            "suggestion_matches": self.suggestion_matches,
            "java_findings": [asdict(f) for f in self.java_findings],
            "pylat_findings": [asdict(f) for f in self.pylat_findings],
        }


class JavaLanguageToolOracle:
    """Interface to the pinned Java LanguageTool development oracle."""

    def __init__(
        self,
        jar_path: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        language: str = "ru-RU",
    ) -> None:
        self.language = language
        self.cache_dir = cache_dir or (Path(__file__).resolve().parent.parent / ".oracle_cache")
        self.jar_path = jar_path

    def is_java_available(self) -> bool:
        """Check if java runtime is available on the system."""
        return shutil.which("java") is not None

    def is_oracle_configured(self) -> bool:
        """Check if Java LanguageTool jar/server is available."""
        if not self.is_java_available():
            return False
        if self.jar_path and self.jar_path.is_file():
            return True
        # Check standard cache location
        candidate = self.cache_dir / f"LanguageTool-{PINNED_LT_VERSION}" / "languagetool-commandline.jar"
        return candidate.is_file()

    def get_jar_path(self) -> Optional[Path]:
        if self.jar_path and self.jar_path.is_file():
            return self.jar_path
        candidate = self.cache_dir / f"LanguageTool-{PINNED_LT_VERSION}" / "languagetool-commandline.jar"
        if candidate.is_file():
            return candidate
        return None

    def check(self, text: str, disabled_rules: Sequence[str] | None = None) -> List[Finding]:
        """Run text through Java LanguageTool CLI and return structured findings.

        Raises:
            RuntimeError: If Java or LanguageTool jar is not available.
        """
        if not self.is_java_available():
            raise RuntimeError("Java is not installed or not in PATH.")

        jar = self.get_jar_path()
        if not jar:
            raise RuntimeError(
                f"LanguageTool standalone jar not found in {self.cache_dir}. "
                "Oracle is development-only and requires LanguageTool-6.8 standalone."
            )

        cmd = [
            "java",
            "-jar",
            str(jar),
            "-l",
            self.language,
            "--json",
        ]
        if disabled_rules:
            cmd.extend(["--disable", ",".join(disabled_rules)])

        try:
            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                check=True,
                encoding="utf-8",
            )
            raw_json = json.loads(proc.stdout)
            matches = raw_json.get("matches", [])
            findings: List[Finding] = []
            for m in matches:
                rule = m.get("rule", {})
                rule_id = rule.get("id", "")
                cat_id = rule.get("category", {}).get("id", "")
                message = m.get("message", "")
                offset = m.get("offset", 0)
                length = m.get("length", 0)
                replacements = [r.get("value", "") for r in m.get("replacements", []) if isinstance(r, dict)]

                findings.append(
                    Finding(
                        rule_id=rule_id,
                        category_id=cat_id,
                        message=message,
                        offset=offset,
                        length=length,
                        suggestions=replacements,
                        source="java_lt",
                    )
                )
            return findings
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Java LanguageTool execution failed: {e.stderr}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Java LanguageTool JSON output: {e}") from e


def compare_findings(
    text: str,
    java_findings: List[Finding],
    pylat_findings: List[Finding],
) -> DifferentialComparisonResult:
    """Compare two sets of findings and produce a structured differential result."""
    java_rule_ids = [f.rule_id for f in java_findings]
    pylat_rule_ids = [f.rule_id for f in pylat_findings]

    matching_rule_ids = [r for r in pylat_rule_ids if r in java_rule_ids]
    missing_in_pylat = [r for r in java_rule_ids if r not in pylat_rule_ids]
    extra_in_pylat = [r for r in pylat_rule_ids if r not in java_rule_ids]

    count_match = len(java_findings) == len(pylat_findings)

    # Count span and suggestion matches
    span_matches = 0
    suggestion_matches = 0

    for jf in java_findings:
        for pf in pylat_findings:
            if jf.rule_id == pf.rule_id:
                if jf.offset == pf.offset and jf.length == pf.length:
                    span_matches += 1
                if set(jf.suggestions) == set(pf.suggestions):
                    suggestion_matches += 1
                break

    is_exact = (
        count_match
        and len(missing_in_pylat) == 0
        and len(extra_in_pylat) == 0
        and span_matches == len(java_findings)
    )

    return DifferentialComparisonResult(
        text=text,
        java_findings=java_findings,
        pylat_findings=pylat_findings,
        finding_count_match=count_match,
        matching_rule_ids=matching_rule_ids,
        missing_in_pylat=missing_in_pylat,
        extra_in_pylat=extra_in_pylat,
        span_matches=span_matches,
        suggestion_matches=suggestion_matches,
        is_exact_match=is_exact,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differential test oracle for LanguageTool Russian vs pylat_ru."
    )
    parser.add_argument("--status", action="store_true", help="Check Java oracle availability")
    parser.add_argument("--text", type=str, help="Text to check")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()
    oracle = JavaLanguageToolOracle()

    if args.status:
        status_info = {
            "java_available": oracle.is_java_available(),
            "oracle_configured": oracle.is_oracle_configured(),
            "pinned_version": PINNED_LT_VERSION,
            "pinned_commit": PINNED_LT_COMMIT,
            "jar_path": str(oracle.get_jar_path()) if oracle.get_jar_path() else None,
        }
        if args.json:
            print(json.dumps(status_info, indent=2))
        else:
            print(f"Java Available: {status_info['java_available']}")
            print(f"Oracle Configured: {status_info['oracle_configured']}")
            print(f"Pinned Version: {PINNED_LT_VERSION} ({PINNED_LT_COMMIT})")
        return 0

    if not args.text:
        parser.print_help()
        return 1

    if not oracle.is_oracle_configured():
        print(
            "Java LanguageTool oracle is not configured. "
            "Place LanguageTool-6.8 standalone jar in .oracle_cache/ or specify path.",
            file=sys.stderr,
        )
        return 1

    findings = oracle.check(args.text)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        print(f"Found {len(findings)} findings from Java LanguageTool:")
        for f in findings:
            print(f"  [{f.rule_id}] {f.message} (offset: {f.offset}, len: {f.length})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
