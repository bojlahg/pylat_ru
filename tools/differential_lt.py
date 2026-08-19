#!/usr/bin/env python3
"""tools/differential_lt.py

Development-only differential oracle harness for comparing pylat_ru against
official pinned Java LanguageTool (v6.8).

IMPORTANT:
- This tool is strictly DEV/TEST only.
- Production code must never import or depend on this module.
- Absence of Java/LanguageTool does not break pylat_ru package imports or execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PINNED_LT_VERSION = "6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
LOOMCHILD_VERSION = "2.0.3"
DEFAULT_ORACLE_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "compat" / "oracle_manifest.json"
)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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
        manifest_path: Optional[Path] = None,
    ) -> None:
        self.language = language
        self.cache_dir = cache_dir or (
            Path(__file__).resolve().parent.parent / ".oracle_cache"
        )
        self.jar_path = jar_path
        self.manifest_path = manifest_path or DEFAULT_ORACLE_MANIFEST_PATH

    def is_java_available(self) -> bool:
        """Check if java and javac runtimes are available on the system."""
        return shutil.which("java") is not None and shutil.which("javac") is not None

    def get_jar_path(self) -> Optional[Path]:
        """Resolve candidate path to languagetool-commandline.jar."""
        if self.jar_path and self.jar_path.is_file():
            return self.jar_path
        candidate = (
            self.cache_dir
            / f"LanguageTool-{PINNED_LT_VERSION}"
            / "languagetool-commandline.jar"
        )
        if candidate.is_file():
            return candidate
        return None

    def validate_oracle(
        self,
        expected_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Strictly validate the configured Java LanguageTool oracle identity, provenance, and SHA-256."""
        if not self.is_java_available():
            raise RuntimeError("Java runtime (java/javac) is not available in PATH.")

        jar = self.get_jar_path()
        if not jar or not jar.is_file():
            raise RuntimeError(
                f"LanguageTool standalone jar not found in {self.cache_dir}. "
                f"Oracle requires LanguageTool-{PINNED_LT_VERSION} standalone."
            )

        jar_hash = sha256_file(jar)

        # Resolve expected SHA-256 from argument, manifest, or environment
        expected_hash = expected_sha256
        if expected_hash is None and self.manifest_path.is_file():
            try:
                manifest_data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                expected_hash = manifest_data.get("oracle_sha256")
            except Exception:
                pass
        if expected_hash is None:
            expected_hash = os.environ.get("PYLAT_ORACLE_SHA256")

        if expected_hash and jar_hash != expected_hash:
            raise RuntimeError(
                f"Oracle JAR SHA-256 mismatch for {jar}:\n"
                f"  Expected: {expected_hash}\n"
                f"  Actual:   {jar_hash}\n"
                f"Refusing to use unverified LanguageTool oracle."
            )

        # Run minimal Java probe to verify JLanguageTool version and Russian pipeline classes
        java_probe = """
import org.languagetool.JLanguageTool;
import org.languagetool.language.Russian;
import net.loomchild.segment.srx.SrxDocument;

public class OracleProbe {
    public static void main(String[] args) {
        String ver = JLanguageTool.VERSION;
        String lang = Russian.getInstance().getShortCode();
        System.out.print(ver + "|" + lang);
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "OracleProbe.java"
            src_file.write_text(java_probe, encoding="utf-8")

            try:
                subprocess.run(
                    ["javac", "-cp", str(jar), str(src_file)],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                proc = subprocess.run(
                    ["java", "-cp", f"{tmpdir}{os.pathsep}{jar}", "OracleProbe"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                output = proc.stdout.strip()
                parts = output.split("|")
                if len(parts) != 2:
                    raise RuntimeError(f"Unexpected probe output: {output!r}")
                version, lang_code = parts
                if not version.startswith(PINNED_LT_VERSION):
                    raise RuntimeError(
                        f"LanguageTool version mismatch: expected '{PINNED_LT_VERSION}', got '{version}'"
                    )
                if lang_code != "ru":
                    raise RuntimeError(
                        f"Russian language module mismatch: expected 'ru', got '{lang_code}'"
                    )

                return {
                    "is_verified": True,
                    "version": version,
                    "language_code": lang_code,
                    "jar_path": str(jar),
                    "jar_sha256": jar_hash,
                    "pinned_version": PINNED_LT_VERSION,
                    "pinned_commit": PINNED_LT_COMMIT,
                }
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    f"Java LanguageTool oracle probe failed: {e.stderr}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Failed to verify Java LanguageTool oracle identity: {e}"
                ) from e

    def is_oracle_configured(self) -> bool:
        """Check if Java LanguageTool oracle is available and passes identity verification."""
        if not self.is_java_available():
            return False
        if not self.get_jar_path():
            return False
        try:
            val = self.validate_oracle()
            return val.get("is_verified", False)
        except Exception:
            return False

    def check(
        self, text: str, disabled_rules: Sequence[str] | None = None
    ) -> List[Finding]:
        """Run text through Java LanguageTool CLI and return structured findings."""
        self.validate_oracle()
        jar = self.get_jar_path()

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
                replacements = [
                    r.get("value", "")
                    for r in m.get("replacements", [])
                    if isinstance(r, dict)
                ]

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
            raise RuntimeError(
                f"Failed to parse Java LanguageTool JSON output: {e}"
            ) from e

    def tokenize_sentences(
        self, text: str, single_line_breaks: bool = False
    ) -> List[str]:
        """Run text through Java LanguageTool Russian SRXSentenceTokenizer."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.language.Russian;
import org.languagetool.tokenizers.SentenceTokenizer;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class TokenizeSentences {
    public static void main(String[] args) throws Exception {
        boolean singleLine = args.length > 0 && args[0].equals("ru_one");
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[1024];
        int n;
        while ((n = System.in.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, n);
        }
        String text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (text.isEmpty()) {
            return;
        }
        Russian ru = (Russian) Russian.getInstance();
        SentenceTokenizer tok = ru.getSentenceTokenizer();
        tok.setSingleLineBreaksMarksParagraph(singleLine);
        List<String> sents = tok.tokenize(text);
        for (int i = 0; i < sents.size(); i++) {
            if (i > 0) System.out.print("\\u0000");
            System.out.print(sents.get(i));
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "TokenizeSentences.java"
            src_file.write_text(java_src, encoding="utf-8")

            # Compile
            subprocess.run(
                ["javac", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            mode_arg = "ru_one" if single_line_breaks else "ru_two"
            proc = subprocess.run(
                [
                    "java",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "TokenizeSentences",
                    mode_arg,
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
            out_bytes = proc.stdout
            if not out_bytes:
                return []
            return out_bytes.decode("utf-8").split("\u0000")

    def tokenize_words(self, text: str) -> List[str]:
        """Run text through Java LanguageTool RussianWordTokenizer."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.language.Russian;
import org.languagetool.tokenizers.Tokenizer;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class TokenizeWords {
    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[1024];
        int n;
        while ((n = System.in.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, n);
        }
        String text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (text.isEmpty()) {
            return;
        }
        Russian ru = (Russian) Russian.getInstance();
        Tokenizer tok = ru.getWordTokenizer();
        List<String> words = tok.tokenize(text);
        for (int i = 0; i < words.size(); i++) {
            if (i > 0) System.out.print("\\u0000");
            System.out.print(words.get(i));
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "TokenizeWords.java"
            src_file.write_text(java_src, encoding="utf-8")

            # Compile
            subprocess.run(
                ["javac", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            proc = subprocess.run(
                ["java", "-cp", f"{tmpdir}{os.pathsep}{jar}", "TokenizeWords"],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
            out_bytes = proc.stdout
            if not out_bytes:
                return []
            return out_bytes.decode("utf-8").split("\u0000")


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


def generate_tokenization_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Regenerate oracle sentence and word fixtures directly from pinned Java LT."""
    # Refuse fixture generation if oracle cannot be strictly proven
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")

    sent_fixture_path = fixtures_dir / "oracle_russian_sentence_tokenization.json"
    word_fixture_path = fixtures_dir / "oracle_russian_word_tokenization.json"

    if not sent_fixture_path.is_file() or not word_fixture_path.is_file():
        raise FileNotFoundError("Existing fixture files needed for case metadata")

    sent_data = json.loads(sent_fixture_path.read_text(encoding="utf-8"))
    word_data = json.loads(word_fixture_path.read_text(encoding="utf-8"))

    sent_data["metadata"]["oracle_jar_sha256"] = oracle_sha
    word_data["metadata"]["oracle_jar_sha256"] = oracle_sha

    for case in sent_data["cases"]:
        text = case["text"]
        single_line = case.get("mode") == "ru_one"
        expected = oracle.tokenize_sentences(text, single_line_breaks=single_line)
        case["expected_sentences"] = expected

    for case in word_data["cases"]:
        text = case["text"]
        expected = oracle.tokenize_words(text)
        case["expected_tokens"] = expected

    sent_fixture_path.write_text(
        json.dumps(sent_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    word_fixture_path.write_text(
        json.dumps(word_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Updated sentence fixture from Java Oracle -> {sent_fixture_path} (oracle SHA: {oracle_sha})")
    print(f"Updated word fixture from Java Oracle -> {word_fixture_path} (oracle SHA: {oracle_sha})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differential test oracle for LanguageTool Russian vs pylat_ru."
    )
    parser.add_argument(
        "--status", action="store_true", help="Check Java oracle availability"
    )
    parser.add_argument("--text", type=str, help="Text to check")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument(
        "--generate-tokenization-fixtures",
        action="store_true",
        help="Generate tokenization fixtures from Java LanguageTool oracle",
    )

    args = parser.parse_args()
    oracle = JavaLanguageToolOracle()

    if args.status:
        try:
            val = oracle.validate_oracle()
            status_info = {
                "java_available": True,
                "oracle_configured": True,
                "oracle_verified": True,
                "pinned_version": PINNED_LT_VERSION,
                "pinned_commit": PINNED_LT_COMMIT,
                "jar_path": str(oracle.get_jar_path()),
                "jar_sha256": val.get("jar_sha256"),
            }
        except Exception as e:
            status_info = {
                "java_available": oracle.is_java_available(),
                "oracle_configured": False,
                "oracle_verified": False,
                "pinned_version": PINNED_LT_VERSION,
                "pinned_commit": PINNED_LT_COMMIT,
                "jar_path": str(oracle.get_jar_path()) if oracle.get_jar_path() else None,
                "error": str(e),
            }

        if args.json:
            print(json.dumps(status_info, indent=2))
        else:
            print(f"Java Available: {status_info['java_available']}")
            print(f"Oracle Configured: {status_info['oracle_configured']}")
            print(f"Pinned Version: {PINNED_LT_VERSION} ({PINNED_LT_COMMIT})")
            if not status_info["oracle_configured"]:
                print(f"Oracle Status Error: {status_info.get('error')}")
        return 0

    if args.generate_tokenization_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_tokenization_fixtures(oracle, fixtures_dir)
        return 0

    if not args.text:
        parser.print_help()
        return 1

    try:
        oracle.validate_oracle()
    except Exception as e:
        print(
            f"Java LanguageTool oracle error: {e}",
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
