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

import regex

PINNED_LT_VERSION = "6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
LOOMCHILD_VERSION = "2.0.3"
DEFAULT_ORACLE_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "compat" / "oracle_manifest.json"
)
HEX_SHA256_PATTERN = regex.compile(r"^[0-9a-fA-F]{64}$")


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_oracle_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Validate schema, required keys, pinned versions, build records, and SHA-256 in oracle manifest."""
    if not manifest_path.is_file():
        raise RuntimeError(f"Oracle manifest file not found: {manifest_path}")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Malformed oracle manifest at {manifest_path}: {e}") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"Oracle manifest at {manifest_path} must be a JSON object")

    required_keys = {
        "schema_version",
        "pinned_version",
        "pinned_commit",
        "loomchild_version",
        "jar_name",
        "trusted_oracle_builds",
    }
    missing = required_keys - set(data.keys())
    if missing:
        raise RuntimeError(
            f"Oracle manifest at {manifest_path} missing required keys: {missing}"
        )

    if data.get("schema_version") != "1.0.0":
        raise RuntimeError(
            f"Unsupported oracle manifest schema_version: {data.get('schema_version')!r}"
        )

    if data.get("pinned_version") != PINNED_LT_VERSION:
        raise RuntimeError(
            f"Oracle manifest pinned_version mismatch: expected {PINNED_LT_VERSION!r}, got {data.get('pinned_version')!r}"
        )

    if data.get("pinned_commit") != PINNED_LT_COMMIT:
        raise RuntimeError(
            f"Oracle manifest pinned_commit mismatch: expected {PINNED_LT_COMMIT!r}, got {data.get('pinned_commit')!r}"
        )

    if data.get("loomchild_version") != LOOMCHILD_VERSION:
        raise RuntimeError(
            f"Oracle manifest loomchild_version mismatch: expected {LOOMCHILD_VERSION!r}, got {data.get('loomchild_version')!r}"
        )

    if data.get("jar_name") != "languagetool-commandline.jar":
        raise RuntimeError(
            f"Oracle manifest jar_name mismatch: expected 'languagetool-commandline.jar', got {data.get('jar_name')!r}"
        )

    builds = data.get("trusted_oracle_builds")
    if not isinstance(builds, list) or len(builds) == 0:
        raise RuntimeError(
            f"Oracle manifest at {manifest_path} must contain a non-empty 'trusted_oracle_builds' list"
        )

    build_ids = set()
    for idx, b in enumerate(builds):
        if not isinstance(b, dict):
            raise RuntimeError(f"trusted_oracle_builds[{idx}] must be an object")

        b_id = b.get("build_id")
        if not isinstance(b_id, str) or not b_id.strip():
            raise RuntimeError(f"trusted_oracle_builds[{idx}] missing valid 'build_id'")
        if b_id in build_ids:
            raise RuntimeError(f"Duplicate build_id '{b_id}' in trusted_oracle_builds")
        build_ids.add(b_id)

        if b.get("pinned_version") != PINNED_LT_VERSION:
            raise RuntimeError(
                f"Build '{b_id}' pinned_version mismatch: expected {PINNED_LT_VERSION!r}, got {b.get('pinned_version')!r}"
            )
        if b.get("pinned_commit") != PINNED_LT_COMMIT:
            raise RuntimeError(
                f"Build '{b_id}' pinned_commit mismatch: expected {PINNED_LT_COMMIT!r}, got {b.get('pinned_commit')!r}"
            )

        b_type = b.get("build_type")
        if b_type not in ("source_build", "published_artifact"):
            raise RuntimeError(
                f"Build '{b_id}' invalid build_type: expected 'source_build' or 'published_artifact', got {b_type!r}"
            )

        if b.get("jar_name") != "languagetool-commandline.jar":
            raise RuntimeError(
                f"Build '{b_id}' jar_name mismatch: expected 'languagetool-commandline.jar', got {b.get('jar_name')!r}"
            )

        sha = b.get("jar_sha256")
        if not isinstance(sha, str) or not HEX_SHA256_PATTERN.match(sha):
            raise RuntimeError(
                f"Build '{b_id}' jar_sha256 must be a valid 64-char hex SHA-256 string, got {sha!r}"
            )

        if b_type == "source_build":
            for req in ("build_command", "java_version", "artifact_path"):
                if not b.get(req):
                    raise RuntimeError(f"Source build '{b_id}' missing required provenance field '{req}'")
        elif b_type == "published_artifact":
            for req in ("artifact_source", "artifact_hash"):
                if not b.get(req):
                    raise RuntimeError(f"Published artifact build '{b_id}' missing required provenance field '{req}'")

    if "default_build_id" in data:
        def_id = data["default_build_id"]
        if def_id not in build_ids:
            raise RuntimeError(f"default_build_id '{def_id}' not found in trusted_oracle_builds")
        if "oracle_sha256" not in data:
            data["oracle_sha256"] = next(b["jar_sha256"] for b in builds if b["build_id"] == def_id)
    elif "oracle_sha256" in data:
        sha = data["oracle_sha256"]
        if not isinstance(sha, str) or not HEX_SHA256_PATTERN.match(sha):
            raise RuntimeError(
                f"Oracle manifest oracle_sha256 must be a valid 64-char hex SHA-256 string, got {sha!r}"
            )

    return data


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
        expected_build_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Strictly validate the configured Java LanguageTool oracle identity, provenance, and SHA-256.

        Fails closed: refuses execution if no valid trusted SHA-256 can be resolved from
        argument, environment (PYLAT_ORACLE_SHA256), or validated manifest file.
        """
        if not self.is_java_available():
            raise RuntimeError("Java runtime (java/javac) is not available in PATH.")

        jar = self.get_jar_path()
        if not jar or not jar.is_file():
            raise RuntimeError(
                f"LanguageTool standalone jar not found in {self.cache_dir}. "
                f"Oracle requires LanguageTool-{PINNED_LT_VERSION} standalone."
            )

        jar_hash = sha256_file(jar)

        matched_build: Optional[Dict[str, Any]] = None
        manifest_data: Optional[Dict[str, Any]] = None

        if expected_build_id is not None:
            manifest_data = validate_oracle_manifest(self.manifest_path)
            builds = manifest_data.get("trusted_oracle_builds", [])
            build_map = {b["build_id"]: b for b in builds}
            if expected_build_id not in build_map:
                raise RuntimeError(
                    f"Unknown expected_build_id '{expected_build_id}'. Known builds: {list(build_map.keys())}"
                )
            target_build = build_map[expected_build_id]
            if jar_hash.lower() != target_build["jar_sha256"].lower():
                raise RuntimeError(
                    f"Oracle JAR SHA-256 mismatch for build '{expected_build_id}': expected {target_build['jar_sha256']}, got {jar_hash}"
                )
            matched_build = target_build
        elif expected_sha256 is not None:
            if not isinstance(expected_sha256, str) or not HEX_SHA256_PATTERN.match(
                expected_sha256
            ):
                raise RuntimeError(
                    f"Invalid expected_sha256 format: {expected_sha256!r}"
                )
            if jar_hash.lower() != expected_sha256.lower():
                raise RuntimeError(
                    f"Oracle JAR SHA-256 mismatch: expected {expected_sha256}, got {jar_hash}"
                )
            if self.manifest_path and self.manifest_path.is_file():
                manifest_data = validate_oracle_manifest(self.manifest_path)
                sha_to_build = {b["jar_sha256"].lower(): b for b in manifest_data.get("trusted_oracle_builds", [])}
                matched_build = sha_to_build.get(jar_hash.lower())
        elif "PYLAT_ORACLE_SHA256" in os.environ:
            env_val = os.environ["PYLAT_ORACLE_SHA256"].strip()
            if not HEX_SHA256_PATTERN.match(env_val):
                raise RuntimeError(
                    f"Invalid PYLAT_ORACLE_SHA256 environment variable format: {env_val!r}"
                )
            if jar_hash.lower() != env_val.lower():
                raise RuntimeError(
                    f"Oracle JAR SHA-256 mismatch against PYLAT_ORACLE_SHA256: expected {env_val}, got {jar_hash}"
                )
            if self.manifest_path and self.manifest_path.is_file():
                manifest_data = validate_oracle_manifest(self.manifest_path)
                sha_to_build = {b["jar_sha256"].lower(): b for b in manifest_data.get("trusted_oracle_builds", [])}
                matched_build = sha_to_build.get(jar_hash.lower())
        else:
            manifest_data = validate_oracle_manifest(self.manifest_path)
            builds = manifest_data.get("trusted_oracle_builds", [])
            sha_to_build = {b["jar_sha256"].lower(): b for b in builds}
            if jar_hash.lower() not in sha_to_build:
                trusted_shas = [b["jar_sha256"] for b in builds]
                raise RuntimeError(
                    f"Oracle JAR SHA-256 {jar_hash} at {jar} does not match any trusted build record in {self.manifest_path}.\n"
                    f"  Trusted SHAs: {trusted_shas}"
                )
            matched_build = sha_to_build[jar_hash.lower()]

        oracle_build_id = matched_build["build_id"] if matched_build else None

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
                    ["java", "-Dfile.encoding=UTF-8", "-cp", f"{tmpdir}{os.pathsep}{jar}", "OracleProbe"],
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
                    "oracle_build_id": oracle_build_id,
                    "build_record": matched_build,
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
            "-Dfile.encoding=UTF-8",
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
        """Run text through Java LanguageTool SRXSentenceTokenizer."""
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
        boolean singleLine = "ru_one".equals(args.length > 0 ? args[0] : "");
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
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        for (int i = 0; i < sents.size(); i++) {
            if (i > 0) out.print("\\u0000");
            out.print(sents.get(i));
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
                    "-Dfile.encoding=UTF-8",
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
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        for (int i = 0; i < words.size(); i++) {
            if (i > 0) out.print("\\u0000");
            out.print(words.get(i));
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
                ["java", "-Dfile.encoding=UTF-8", "-cp", f"{tmpdir}{os.pathsep}{jar}", "TokenizeWords"],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
            out_bytes = proc.stdout
            if not out_bytes:
                return []
            return out_bytes.decode("utf-8").split("\u0000")

    def tag_tokens(self, tokens: Sequence[str]) -> List[Dict[str, Any]]:
        """Run token sequence through Java LanguageTool RussianTagger."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.tagging.ru.RussianTagger;
import org.languagetool.AnalyzedTokenReadings;
import org.languagetool.AnalyzedToken;
import org.languagetool.chunking.ChunkTag;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class TagTokens {
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
        String[] tokenArray = text.split("\\u0000", -1);
        List<String> inputTokens = Arrays.asList(tokenArray);
        RussianTagger tagger = RussianTagger.INSTANCE;
        List<AnalyzedTokenReadings> atrs = tagger.tag(inputTokens);
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < atrs.size(); i++) {
            if (i > 0) sb.append("\\u0001");
            AnalyzedTokenReadings atr = atrs.get(i);
            sb.append(atr.getStartPos()).append("\\u0002");
            if (atr.getChunkTags() != null) {
                for (int c = 0; c < atr.getChunkTags().size(); c++) {
                    if (c > 0) sb.append(",");
                    sb.append(atr.getChunkTags().get(c).getChunkTag());
                }
            }
            sb.append("\\u0002");
            List<AnalyzedToken> readings = atr.getReadings();
            for (int r = 0; r < readings.size(); r++) {
                if (r > 0) sb.append("\\u0003");
                AnalyzedToken at = readings.get(r);
                sb.append(at.getToken()).append("\\u0004");
                sb.append(at.getLemma() != null ? at.getLemma() : "\\u0005null").append("\\u0004");
                sb.append(at.getPOSTag() != null ? at.getPOSTag() : "\\u0005null");
            }
        }
        out.print(sb.toString());
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "TagTokens.java"
            src_file.write_text(java_src, encoding="utf-8")

            # Compile
            subprocess.run(
                ["javac", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            input_bytes = "\u0000".join(tokens).encode("utf-8")
            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "TagTokens",
                ],
                input=input_bytes,
                capture_output=True,
                check=True,
            )
            out_str = proc.stdout.decode("utf-8")
            if not out_str:
                return []

            results: List[Dict[str, Any]] = []
            atr_blocks = out_str.split("\u0001")
            for block in atr_blocks:
                parts = block.split("\u0002")
                start_pos = int(parts[0])
                chunk_tags = [c for c in parts[1].split(",") if c] if parts[1] else []
                readings = []
                if len(parts) > 2 and parts[2]:
                    r_blocks = parts[2].split("\u0003")
                    for rb in r_blocks:
                        r_parts = rb.split("\u0004")
                        t_str = r_parts[0]
                        l_str = None if r_parts[1] == "\u0005null" else r_parts[1]
                        p_str = None if r_parts[2] == "\u0005null" else r_parts[2]
                        readings.append(
                            {"token": t_str, "lemma": l_str, "pos_tag": p_str}
                        )
                results.append(
                    {
                        "start_pos_utf16": start_pos,
                        "readings": readings,
                        "chunk_tags": chunk_tags,
                    }
                )
            return results

    def disambiguate_sentences(
        self, sentences: Sequence[str]
    ) -> List[Dict[str, Any]]:
        """Run sentences through Java LanguageTool disambiguation stages: raw, multiword, hybrid."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.JLanguageTool;
import org.languagetool.AnalyzedSentence;
import org.languagetool.AnalyzedTokenReadings;
import org.languagetool.AnalyzedToken;
import org.languagetool.language.Russian;
import org.languagetool.tagging.disambiguation.MultiWordChunker;
import org.languagetool.tagging.disambiguation.ru.RussianHybridDisambiguator;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class DisambiguateSentences {
    static String serializeSentence(AnalyzedSentence s) {
        StringBuilder sb = new StringBuilder();
        AnalyzedTokenReadings[] tokens = s.getTokens();
        for (int i = 0; i < tokens.length; i++) {
            if (i > 0) sb.append("\\u0001");
            AnalyzedTokenReadings atr = tokens[i];
            sb.append(atr.getToken()).append("\\u0002");
            sb.append(atr.getStartPos()).append("\\u0002");
            sb.append(atr.getPosFix()).append("\\u0002");
            sb.append(atr.isWhitespace() ? "1" : "0").append("\\u0002");
            sb.append(atr.isSentenceStart() ? "1" : "0").append("\\u0002");
            sb.append(atr.isSentenceEnd() ? "1" : "0").append("\\u0002");
            sb.append(atr.isParagraphEnd() ? "1" : "0").append("\\u0002");
            sb.append(atr.isIgnoredBySpeller() ? "1" : "0").append("\\u0002");
            sb.append(atr.getCleanToken() != null ? atr.getCleanToken() : "\\u0005null").append("\\u0002");
            sb.append(atr.getWhitespaceBefore() != null ? atr.getWhitespaceBefore() : "\\u0005null").append("\\u0002");

            if (atr.getChunkTags() != null) {
                for (int c = 0; c < atr.getChunkTags().size(); c++) {
                    if (c > 0) sb.append(",");
                    sb.append(atr.getChunkTags().get(c).getChunkTag());
                }
            }
            sb.append("\\u0002");

            List<AnalyzedToken> readings = atr.getReadings();
            for (int r = 0; r < readings.size(); r++) {
                if (r > 0) sb.append("\\u0003");
                AnalyzedToken at = readings.get(r);
                sb.append(at.getToken()).append("\\u0004");
                sb.append(at.getLemma() != null ? at.getLemma() : "\\u0005null").append("\\u0004");
                sb.append(at.getPOSTag() != null ? at.getPOSTag() : "\\u0005null");
            }
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[1024];
        int n;
        while ((n = System.in.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, n);
        }
        String text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (text.isEmpty()) return;

        String[] sentenceArray = text.split("\\u0000", -1);
        Russian russian = Russian.getInstance();
        JLanguageTool lt = new JLanguageTool(russian);
        MultiWordChunker multiwords = MultiWordChunker.getInstance("/ru/multiwords.txt");
        RussianHybridDisambiguator hybrid = RussianHybridDisambiguator.getInstance();

        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        for (int s = 0; s < sentenceArray.length; s++) {
            if (s > 0) out.print("\\u0006");
            String sentence = sentenceArray[s];

            // 1. Raw
            AnalyzedSentence raw = lt.getRawAnalyzedSentence(sentence);
            String rawStr = serializeSentence(raw);

            // 2. Multiword chunked
            AnalyzedSentence rawForMw = lt.getRawAnalyzedSentence(sentence);
            AnalyzedSentence mw = multiwords.disambiguate(rawForMw);
            String mwStr = serializeSentence(mw);

            // 3. Final Hybrid disambiguated
            AnalyzedSentence rawForHybrid = lt.getRawAnalyzedSentence(sentence);
            AnalyzedSentence fin = hybrid.disambiguate(rawForHybrid);
            String finStr = serializeSentence(fin);

            out.print(rawStr + "\\u0007" + mwStr + "\\u0007" + finStr);
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "DisambiguateSentences.java"
            src_file.write_text(java_src, encoding="utf-8")

            subprocess.run(
                ["javac", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            input_bytes = "\u0000".join(sentences).encode("utf-8")
            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "DisambiguateSentences",
                ],
                input=input_bytes,
                capture_output=True,
                check=True,
            )
            out_str = proc.stdout.decode("utf-8")
            if not out_str:
                return []

            def parse_sentence_str(s_str: str) -> List[Dict[str, Any]]:
                tokens_res: List[Dict[str, Any]] = []
                for b in s_str.split("\u0001"):
                    parts = b.split("\u0002")
                    if len(parts) < 12:
                        continue
                    tok = parts[0]
                    sp = int(parts[1])
                    pf = int(parts[2])
                    is_ws = parts[3] == "1"
                    is_ss = parts[4] == "1"
                    is_se = parts[5] == "1"
                    is_pe = parts[6] == "1"
                    is_ign = parts[7] == "1"
                    ct = None if parts[8] == "\u0005null" else parts[8]
                    wb = None if parts[9] == "\u0005null" else parts[9]
                    chunks = [c for c in parts[10].split(",") if c] if parts[10] else []

                    readings: List[Dict[str, Optional[str]]] = []
                    if parts[11]:
                        for rb in parts[11].split("\u0003"):
                            r_parts = rb.split("\u0004")
                            if len(r_parts) >= 3:
                                t = r_parts[0]
                                l = None if r_parts[1] == "\u0005null" else r_parts[1]
                                p = None if r_parts[2] == "\u0005null" else r_parts[2]
                                readings.append({"token": t, "lemma": l, "pos_tag": p})

                    tokens_res.append(
                        {
                            "token": tok,
                            "start_pos_utf16": sp,
                            "pos_fix": pf,
                            "is_whitespace": is_ws,
                            "is_sentence_start": is_ss,
                            "is_sentence_end": is_se,
                            "is_paragraph_end": is_pe,
                            "is_ignore_spelling": is_ign,
                            "clean_token": ct,
                            "whitespace_before": wb,
                            "chunk_tags": chunks,
                            "readings": readings,
                        }
                    )
                return tokens_res

            results: List[Dict[str, Any]] = []
            sent_blocks = out_str.split("\u0006")
            for sb in sent_blocks:
                stage_parts = sb.split("\u0007")
                if len(stage_parts) == 3:
                    results.append(
                        {
                            "raw": parse_sentence_str(stage_parts[0]),
                            "multiword": parse_sentence_str(stage_parts[1]),
                            "disambiguated": parse_sentence_str(stage_parts[2]),
                        }
                    )
            return results

    def synthesize_queries(
        self, queries: Sequence[Dict[str, Any]]
    ) -> List[List[str]]:
        """Run synthesis queries through Java LanguageTool RussianSynthesizer."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.synthesis.ru.RussianSynthesizer;
import org.languagetool.AnalyzedToken;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class SynthesizeQueries {
    public static void main(String[] args) throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        PrintWriter out = new PrintWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8), true);
        RussianSynthesizer s = RussianSynthesizer.INSTANCE;

        String line;
        while ((line = reader.readLine()) != null) {
            if (line.isEmpty()) continue;
            String[] parts = line.split("\\t", -1);
            if (parts.length < 3) continue;
            String tokenStr = parts[0];
            String lemmaStr = parts[1];
            String posTag = parts[2];
            boolean isRegex = parts.length > 3 && parts[3].equals("1");

            AnalyzedToken tok = new AnalyzedToken(tokenStr, "DUMMY", lemmaStr);
            String[] res = s.synthesize(tok, posTag, isRegex);

            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < res.length; i++) {
                if (i > 0) sb.append("\\u0001");
                sb.append(res[i]);
            }
            out.println(sb.toString());
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "SynthesizeQueries.java"
            src_file.write_text(java_src, encoding="utf-8")

            subprocess.run(
                ["javac", "-encoding", "UTF-8", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            input_lines = []
            for q in queries:
                token_str = q.get("token", q.get("lemma", ""))
                lemma_str = q.get("lemma", token_str)
                pos_tag = q.get("pos_tag", "")
                is_regex = "1" if q.get("pos_tag_is_regex", False) else "0"
                input_lines.append(f"{token_str}\t{lemma_str}\t{pos_tag}\t{is_regex}")

            input_data = "\n".join(input_lines) + "\n"

            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-Dstdout.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "SynthesizeQueries",
                ],
                input=input_data.encode("utf-8"),
                capture_output=True,
                check=True,
            )

            out_str = proc.stdout.decode("utf-8")
            results: List[List[str]] = []
            for line in out_str.splitlines():
                if not line:
                    results.append([])
                else:
                    results.append(line.split("\u0001"))
            return results



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
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    sent_fixture_path = fixtures_dir / "oracle_russian_sentence_tokenization.json"
    word_fixture_path = fixtures_dir / "oracle_russian_word_tokenization.json"

    if not sent_fixture_path.is_file() or not word_fixture_path.is_file():
        raise FileNotFoundError("Existing fixture files needed for case metadata")

    sent_data = json.loads(sent_fixture_path.read_text(encoding="utf-8"))
    word_data = json.loads(word_fixture_path.read_text(encoding="utf-8"))

    sent_data["metadata"]["oracle_build_id"] = oracle_build_id
    sent_data["metadata"]["oracle_jar_sha256"] = oracle_sha
    word_data["metadata"]["oracle_build_id"] = oracle_build_id
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
    print(
        f"Updated sentence fixture from Java Oracle -> {sent_fixture_path} (oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )
    print(
        f"Updated word fixture from Java Oracle -> {word_fixture_path} (oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


def generate_tagger_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Regenerate oracle Russian tagger fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    tagger_fixture_path = fixtures_dir / "oracle_russian_tagger.json"
    if not tagger_fixture_path.is_file():
        raise FileNotFoundError(f"Fixture template not found: {tagger_fixture_path}")

    tagger_data = json.loads(tagger_fixture_path.read_text(encoding="utf-8"))
    tagger_data["metadata"]["oracle_build_id"] = oracle_build_id
    tagger_data["metadata"]["oracle_jar_sha256"] = oracle_sha

    for case in tagger_data["cases"]:
        input_tokens = case["input_tokens"]
        expected = oracle.tag_tokens(input_tokens)
        case["expected_tokens"] = expected

    tagger_fixture_path.write_text(
        json.dumps(tagger_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Updated tagger fixture from Java Oracle -> {tagger_fixture_path} (oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


DISAMBIGUATION_TEST_CASES = [
    # 1. XML official examples
    {"category": "xml_example", "text": "А на самом деле это так."},
    {"category": "xml_example", "text": "Это просто не так."},
    {"category": "xml_example", "text": "Но это не так."},
    {"category": "xml_example", "text": "Они сидели тихо, затаив дыхание."},
    {"category": "xml_example", "text": "Мы всё сделали как надо."},
    {"category": "xml_example", "text": "Это было сделано как положено."},
    {"category": "xml_example", "text": "Они шли рука об руку."},
    {"category": "xml_example", "text": "Он стоял бок о бок."},
    # 2. Multiword chunker cases
    {"category": "multiword", "text": "В будущем мы увидим результат."},
    {"category": "multiword", "text": "До свидания, дорогие друзья!"},
    {"category": "multiword", "text": "Во что бы то ни стало мы победим."},
    {"category": "multiword", "text": "Откуда ни возьмись появился волк."},
    {"category": "multiword", "text": "Затаив дыхание они слушали."},
    {"category": "multiword", "text": "По меньшей мере это очень странно."},
    {"category": "multiword", "text": "Друг друга они понимали с полуслова."},
    {"category": "multiword", "text": "Один за другим они уходили в ночь."},
    # 3. Actions: ADD, REMOVE, REPLACE (default), REPLACE with match, IGNORE_SPELLING
    {"category": "action_add", "text": "С праздником 8 Марта!"},
    {"category": "action_remove", "text": "Село солнце за горизонт."},
    {"category": "action_replace_default", "text": "Ввиду задержки рейса мы опоздали."},
    {"category": "action_replace_match", "text": "Мы пришли как раз вовремя."},
    {"category": "action_ignore_spelling", "text": "Вице-президент выступил на собрании."},
    # 4. Filters (-ка, -то, пол-, экс-, обер-)
    {"category": "filter", "text": "Дай-ка мне эту книгу."},
    {"category": "filter", "text": "Кто-то постучал в дверь."},
    {"category": "filter", "text": "Пол-яблока лежало на тарелке."},
    {"category": "filter", "text": "Экс-президент прибыл на встречу."},
    {"category": "filter", "text": "Обер-лейтенант отдал приказ."},
    # 5. Pattern constructs: <and>, scope="next", skip=1, skip=-1, inflected, case_sensitive, antipattern
    {"category": "pattern_and", "text": "Стали известны новые подробности."},
    {"category": "pattern_scope_next", "text": "В том числе и наши коллеги пришли."},
    {"category": "pattern_skip", "text": "Не только взрослые, но и дети радовались."},
    {"category": "pattern_inflected", "text": "С каждым новым днем все меняется."},
    {"category": "pattern_case_sensitive", "text": "Москва и Санкт-Петербург встретили гостей."},
    {"category": "pattern_antipattern", "text": "Не так ли это устроено?"},
    {"category": "pattern_antipattern", "text": "Все устроено не так просто."},
    # 6. Accents, soft-hyphen, emojis, whitespace
    {"category": "accent_acute", "text": "Краси́вый за́мок стоял на горе́."},
    {"category": "accent_grave", "text": "Перѐд домом росло дерево."},
    {"category": "soft_hyphen", "text": "Быстро едет авто\u00adмобиль по дороге."},
    {"category": "emoji_surrogates", "text": "🌟 Привет мир! 🚀 Как дела?"},
    {"category": "whitespace_tabs_newlines", "text": "Слово \t еще   слово.\nНовая строка."},
    {"category": "trailing_whitespace", "text": "Тест завершен успешно.   "},
    {"category": "unknown_words", "text": "Квазимодульный глобулятор фырчит."},
]


def generate_disambiguation_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Generate oracle Russian disambiguation fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    output_path = fixtures_dir / "oracle_russian_disambiguation.json"
    sentences = [c["text"] for c in DISAMBIGUATION_TEST_CASES]
    stages_results = oracle.disambiguate_sentences(sentences)

    cases: List[Dict[str, Any]] = []
    for i, item in enumerate(DISAMBIGUATION_TEST_CASES):
        cases.append(
            {
                "id": f"case_{i + 1:03d}",
                "category": item["category"],
                "text": item["text"],
                "stages": stages_results[i],
            }
        )

    fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Disambiguation Fixture",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "cases_count": len(cases),
        },
        "cases": cases,
    }

    output_path.write_text(
        json.dumps(fixture_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Generated Russian disambiguation fixture -> {output_path} ({len(cases)} cases, oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


SYNTHESIS_TEST_QUERIES: List[Dict[str, Any]] = [
    # 1. Noun exact synthesis
    {"category": "noun_exact", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:Sin:R", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "дом", "lemma": "дом", "pos_tag": "NN:Inanim:Masc:PL:Nom", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "дом", "lemma": "дом", "pos_tag": "NN:Inanim:Masc:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "человек", "lemma": "человек", "pos_tag": "NN:Anim:Masc:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "окно", "lemma": "окно", "pos_tag": "NN:Inanim:Neut:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "noun_exact", "token": "рука", "lemma": "рука", "pos_tag": "NN:Inanim:Fem:PL:T", "pos_tag_is_regex": False},
    # 2. Verb exact synthesis
    {"category": "verb_exact", "token": "бежать", "lemma": "бежать", "pos_tag": "VB:INF:INTR:IMPFV", "pos_tag_is_regex": False},
    {"category": "verb_exact", "token": "говорить", "lemma": "говорить", "pos_tag": "VB:Past:Masc:Imperactive", "pos_tag_is_regex": False},
    {"category": "verb_exact", "token": "идти", "lemma": "идти", "pos_tag": "VB:Pres:1p:Sin:Imperactive", "pos_tag_is_regex": False},
    {"category": "verb_exact", "token": "делать", "lemma": "делать", "pos_tag": "VB:Pres:3p:PL:Imperactive", "pos_tag_is_regex": False},
    # 3. Adjective exact synthesis
    {"category": "adj_exact", "token": "красивый", "lemma": "красивый", "pos_tag": "ADJ:Posit:Fem:Nom", "pos_tag_is_regex": False},
    {"category": "adj_exact", "token": "красивый", "lemma": "красивый", "pos_tag": "ADJ:Short:Fem", "pos_tag_is_regex": False},
    {"category": "adj_exact", "token": "новый", "lemma": "новый", "pos_tag": "ADJ:Posit:PL:Nom", "pos_tag_is_regex": False},
    {"category": "adj_exact", "token": "хороший", "lemma": "хороший", "pos_tag": "ADJ:Comp", "pos_tag_is_regex": False},
    # 4. Trailing-empty POS tag
    {"category": "trailing_empty_tag", "token": "блукать", "lemma": "блукать", "pos_tag": "VB:INF:", "pos_tag_is_regex": False},
    # 5. Regex synthesis
    {"category": "regex_noun", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:.*", "pos_tag_is_regex": True},
    {"category": "regex_noun", "token": "дом", "lemma": "дом", "pos_tag": "NN:Inanim:Masc:.*", "pos_tag_is_regex": True},
    {"category": "regex_verb", "token": "бежать", "lemma": "бежать", "pos_tag": "VB:.*", "pos_tag_is_regex": True},
    {"category": "regex_verb", "token": "говорить", "lemma": "говорить", "pos_tag": "VB:.*:3p:.*", "pos_tag_is_regex": True},
    {"category": "regex_adj", "token": "красивый", "lemma": "красивый", "pos_tag": "ADJ:Short:.*", "pos_tag_is_regex": True},
    # 6. Manual additions overlay (added.txt)
    {"category": "manual_added", "token": "мадам", "lemma": "мадам", "pos_tag": "NN:Name:Fem:PL", "pos_tag_is_regex": False},
    {"category": "manual_added", "token": "шлифмашина", "lemma": "шлифмашина", "pos_tag": "NN:Inanim:Masc:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "manual_added", "token": "трассерный", "lemma": "трассерный", "pos_tag": "ADJ:Posit:Masc:Nom", "pos_tag_is_regex": False},
    # 7. Manual removals overlay (removed.txt material cases)
    {"category": "manual_removed", "token": "дерево", "lemma": "дерево", "pos_tag": "NN:Inanim:Neut:PL:R", "pos_tag_is_regex": False},
    {"category": "manual_removed", "token": "втэк", "lemma": "втэк", "pos_tag": "NN:Inanim:Masc:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "manual_removed", "token": "может", "lemma": "может", "pos_tag": "PARENTHESIS", "pos_tag_is_regex": False},
    {"category": "manual_removed", "token": "кпсс", "lemma": "кпсс", "pos_tag": "ABR:Neut", "pos_tag_is_regex": False},
    {"category": "manual_removed", "token": "ао", "lemma": "ао", "pos_tag": "NN:Inanim:Masc", "pos_tag_is_regex": False},
    # 8. Special number tags
    {"category": "special_number", "token": "123", "lemma": "123", "pos_tag": "_spell_number_", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "123", "lemma": "123", "pos_tag": "_spell_number_:feminine", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "1", "lemma": "1", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "4", "lemma": "4", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "9", "lemma": "9", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "123", "lemma": "123", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
    {"category": "special_number", "token": "2024", "lemma": "2024", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
    # 9. Case sensitivity
    {"category": "case_sensitive", "token": "Семья", "lemma": "Семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "case_sensitive", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    # 10. Null lemma edge cases
    {"category": "null_lemma", "token": "семья", "lemma": None, "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "null_lemma", "token": "семья", "lemma": None, "pos_tag": "NN:Inanim:Fem:.*", "pos_tag_is_regex": True},
    # 11. Unknown POS tag & unknown words
    {"category": "unknown_tag", "token": "семья", "lemma": "семья", "pos_tag": "UNKNOWN_POS_TAG", "pos_tag_is_regex": False},
    {"category": "unknown_word", "token": "квазимодулятор", "lemma": "квазимодулятор", "pos_tag": "NN:.*", "pos_tag_is_regex": True},
    {"category": "unknown_word", "token": "blablabla", "lemma": "blablabla", "pos_tag": "VB:.*", "pos_tag_is_regex": True},
]


def generate_synthesizer_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Generate oracle Russian synthesizer fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    output_path = fixtures_dir / "oracle_russian_synthesizer_sample.json"
    results = oracle.synthesize_queries(SYNTHESIS_TEST_QUERIES)

    queries_data: List[Dict[str, Any]] = []
    for i, q in enumerate(SYNTHESIS_TEST_QUERIES):
        queries_data.append(
            {
                "id": f"synth_{i + 1:03d}",
                "category": q["category"],
                "token": q.get("token", q.get("lemma", "")),
                "lemma": q.get("lemma", ""),
                "pos_tag": q["pos_tag"],
                "pos_tag_is_regex": q.get("pos_tag_is_regex", False),
                "expected_forms": results[i],
            }
        )

    fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Synthesizer Fixture",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "queries_count": len(queries_data),
        },
        "queries": queries_data,
    }

    output_path.write_text(
        json.dumps(fixture_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Generated Russian synthesizer fixture -> {output_path} ({len(queries_data)} queries, oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


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
    parser.add_argument(
        "--generate-tagger-fixtures",
        action="store_true",
        help="Generate Russian tagger fixtures from Java LanguageTool oracle",
    )
    parser.add_argument(
        "--generate-disambiguation-fixtures",
        action="store_true",
        help="Generate Russian disambiguation fixtures from Java LanguageTool oracle",
    )
    parser.add_argument(
        "--generate-synthesizer-fixtures",
        action="store_true",
        help="Generate Russian synthesizer fixtures from Java LanguageTool oracle",
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
                "jar_path": str(oracle.get_jar_path())
                if oracle.get_jar_path()
                else None,
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

    if args.generate_tagger_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_tagger_fixtures(oracle, fixtures_dir)
        return 0

    if args.generate_disambiguation_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_disambiguation_fixtures(oracle, fixtures_dir)
        return 0

    if args.generate_synthesizer_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_synthesizer_fixtures(oracle, fixtures_dir)
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

