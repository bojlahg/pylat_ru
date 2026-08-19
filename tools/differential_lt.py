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
            boolean isNullLemma = parts.length > 4 && parts[4].equals("1");

            AnalyzedToken tok = new AnalyzedToken(tokenStr, "DUMMY", isNullLemma ? null : lemmaStr);
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
                token_str = q.get("token", "")
                lemma_val = q.get("lemma")
                if lemma_val is None and "lemma" not in q:
                    lemma_val = token_str
                is_null_lemma = "1" if lemma_val is None else "0"
                lemma_str = "" if lemma_val is None else str(lemma_val)
                pos_tag = q.get("pos_tag", "")
                is_regex = "1" if q.get("pos_tag_is_regex", False) else "0"
                input_lines.append(f"{token_str}\t{lemma_str}\t{pos_tag}\t{is_regex}\t{is_null_lemma}")

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

    def chunk_sentences(
        self, sentences: Sequence[str]
    ) -> List[Dict[str, Any]]:
        """Run sentences through Java LanguageTool post-hybrid and post-chunker stages."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.JLanguageTool;
import org.languagetool.AnalyzedSentence;
import org.languagetool.AnalyzedTokenReadings;
import org.languagetool.AnalyzedToken;
import org.languagetool.language.Russian;
import org.languagetool.tagging.disambiguation.ru.RussianHybridDisambiguator;
import org.languagetool.chunking.RussianChunker;
import org.languagetool.chunking.ChunkTag;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class ChunkSentences {
    static String serializeSentence(AnalyzedSentence s) {
        StringBuilder sb = new StringBuilder();
        AnalyzedTokenReadings[] tokens = s.getTokens();
        for (int i = 0; i < tokens.length; i++) {
            if (i > 0) sb.append("\u0001");
            AnalyzedTokenReadings atr = tokens[i];
            sb.append(atr.getToken()).append("\u0002");
            sb.append(atr.getStartPos()).append("\u0002");
            sb.append(atr.getPosFix()).append("\u0002");
            sb.append(atr.isWhitespace() ? "1" : "0").append("\u0002");
            sb.append(atr.isSentenceStart() ? "1" : "0").append("\u0002");
            sb.append(atr.isSentenceEnd() ? "1" : "0").append("\u0002");
            sb.append(atr.isParagraphEnd() ? "1" : "0").append("\u0002");
            sb.append(atr.isIgnoredBySpeller() ? "1" : "0").append("\u0002");
            sb.append(atr.getCleanToken() != null ? atr.getCleanToken() : "\u0005null").append("\u0002");
            sb.append(atr.getWhitespaceBefore() != null ? atr.getWhitespaceBefore() : "\u0005null").append("\u0002");

            if (atr.getChunkTags() != null) {
                for (int c = 0; c < atr.getChunkTags().size(); c++) {
                    if (c > 0) sb.append(",");
                    sb.append(atr.getChunkTags().get(c).getChunkTag());
                }
            }
            sb.append("\u0002");

            List<AnalyzedToken> readings = atr.getReadings();
            for (int r = 0; r < readings.size(); r++) {
                if (r > 0) sb.append("\u0003");
                AnalyzedToken at = readings.get(r);
                sb.append(at.getToken()).append("\u0004");
                sb.append(at.getLemma() != null ? at.getLemma() : "\u0005null").append("\u0004");
                sb.append(at.getPOSTag() != null ? at.getPOSTag() : "\u0005null");
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

        String[] sentenceArray = text.split("\u0000", -1);
        Russian russian = Russian.getInstance();
        JLanguageTool lt = new JLanguageTool(russian);
        RussianHybridDisambiguator hybrid = RussianHybridDisambiguator.getInstance();
        RussianChunker chunker = new RussianChunker();

        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        for (int s = 0; s < sentenceArray.length; s++) {
            if (s > 0) out.print("\u0006");
            String item = sentenceArray[s];
            String sentence = item;
            Map<String, List<ChunkTag>> injectedChunks = new HashMap<>();
            if (item.contains("\u0008")) {
                String[] parts = item.split("\u0008", 2);
                sentence = parts[0];
                for (String spec : parts[1].split(";")) {
                    if (!spec.isEmpty()) {
                        String[] specParts = spec.split(":", 2);
                        if (specParts.length == 2) {
                            List<ChunkTag> cTags = new ArrayList<>();
                            for (String ct : specParts[1].split(",")) {
                                if (!ct.isEmpty()) cTags.add(new ChunkTag(ct));
                            }
                            injectedChunks.put(specParts[0], cTags);
                        }
                    }
                }
            }

            // 1. Post-hybrid
            AnalyzedSentence raw = lt.getRawAnalyzedSentence(sentence);
            AnalyzedSentence postHybrid = hybrid.disambiguate(raw);

            // Inject explicit pre-existing chunk tags if requested
            if (!injectedChunks.isEmpty()) {
                for (AnalyzedTokenReadings atr : postHybrid.getTokens()) {
                    if (injectedChunks.containsKey(atr.getToken())) {
                        atr.setChunkTags(injectedChunks.get(atr.getToken()));
                    }
                }
            }

            String preChunkerStr = serializeSentence(postHybrid);

            // 2. Post-chunker
            chunker.addChunkTags(Arrays.asList(postHybrid.getTokens()));
            String postChunkerStr = serializeSentence(postHybrid);

            out.print(preChunkerStr + "\u0007" + postChunkerStr);
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "ChunkSentences.java"
            src_file.write_text(java_src, encoding="utf-8")

            subprocess.run(
                ["javac", "-encoding", "UTF-8", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            input_bytes = "\u0000".join(sentences).encode("utf-8")
            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-Dstdout.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "ChunkSentences",
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
                if len(stage_parts) == 2:
                    results.append(
                        {
                            "pre_chunker": parse_sentence_str(stage_parts[0]),
                            "post_chunker": parse_sentence_str(stage_parts[1]),
                        }
                    )
            return results

    def check_pattern_rules(
        self, cases: Sequence[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Run specific Russian pattern rules against texts in Java LanguageTool oracle."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """
import org.languagetool.rules.patterns.PatternRuleLoader;
import org.languagetool.rules.patterns.AbstractPatternRule;
import org.languagetool.rules.RuleMatch;
import org.languagetool.language.Russian;
import org.languagetool.JLanguageTool;
import org.languagetool.AnalyzedSentence;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class CheckPatternRules {
    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[1024];
        int n;
        while ((n = System.in.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, n);
        }
        String text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (text.isEmpty()) return;

        String[] caseArray = text.split("\\u0000", -1);
        Russian russian = Russian.getInstance();
        JLanguageTool lt = new JLanguageTool(russian);
        PatternRuleLoader loader = new PatternRuleLoader();
        InputStream is = Russian.class.getResourceAsStream("/org/languagetool/rules/ru/grammar.xml");
        List<AbstractPatternRule> rules = loader.getRules(is, "/org/languagetool/rules/ru/grammar.xml", russian);
        Map<String, Set<AbstractPatternRule>> ruleMap = new HashMap<>();
        for (AbstractPatternRule r : rules) {
            ruleMap.computeIfAbsent(r.getFullId(), k -> new LinkedHashSet<>()).add(r);
            if (!r.getFullId().equals(r.getId())) {
                ruleMap.computeIfAbsent(r.getId(), k -> new LinkedHashSet<>()).add(r);
            }
            if (r.getSubId() != null) {
                ruleMap.computeIfAbsent(r.getId() + "[" + r.getSubId() + "]", k -> new LinkedHashSet<>()).add(r);
            }
        }

        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        for (int i = 0; i < caseArray.length; i++) {
            if (i > 0) out.print("\u0006");
            String[] pair = caseArray[i].split("\u0007", 2);
            String targetId = pair[0];
            String inputText = pair.length > 1 ? pair[1] : "";

            Set<AbstractPatternRule> rSet = ruleMap.get(targetId);
            if (rSet == null && targetId.contains("[")) {
                String baseId = targetId.substring(0, targetId.indexOf('['));
                String sub = targetId.substring(targetId.indexOf('[') + 1, targetId.length() - 1);
                rSet = ruleMap.get(sub);
                if (rSet == null) {
                    rSet = ruleMap.get(baseId);
                }
            }
            if (rSet == null || rSet.isEmpty()) {
                out.print("NOT_FOUND\u0008" + targetId);
                continue;
            }

            AbstractPatternRule r = rSet.iterator().next();
            AnalyzedSentence sent = lt.getAnalyzedSentence(inputText);
            List<RuleMatch> allMatches = new ArrayList<>();
            for (AbstractPatternRule variant : rSet) {
                RuleMatch[] matches = variant.match(sent);
                if (matches != null) {
                    for (RuleMatch m : matches) {
                        allMatches.add(m);
                    }
                }
            }
            List<RuleMatch> filteredMatches = new ArrayList<>();
            for (RuleMatch m : allMatches) {
                boolean subsumed = false;
                for (RuleMatch other : allMatches) {
                    if (other != m && other.getFromPos() <= m.getFromPos() && other.getToPos() >= m.getToPos()
                        && (other.getToPos() - other.getFromPos() > m.getToPos() - m.getFromPos())) {
                        subsumed = true;
                        break;
                    }
                    if (other != m && other.getFromPos() == m.getFromPos() && other.getToPos() == m.getToPos()) {
                        if (allMatches.indexOf(other) < allMatches.indexOf(m)) {
                            subsumed = true;
                            break;
                        }
                    }
                }
                if (!subsumed) {
                    filteredMatches.add(m);
                }
            }

            StringBuilder sb = new StringBuilder();
            sb.append("FOUND\u0008").append(r.getId()).append("\u0008").append(r.getFullId()).append("\u0008")
              .append(r.getCategory().getId().toString()).append("\u0008")
              .append(r.getCategory().getName()).append("\u0008")
              .append(r.getDescription()).append("\u0008")
              .append(r.isDefaultOff() ? "1" : "0").append("\u0008")
              .append(filteredMatches.size());

            for (RuleMatch m : filteredMatches) {
                sb.append("\u0008");
                sb.append(m.getFromPos()).append("\u0002")
                  .append(m.getToPos()).append("\u0002")
                  .append(m.getMessage()).append("\u0002")
                  .append(m.getShortMessage() != null ? m.getShortMessage() : "\u0005null").append("\u0002");
                List<String> repls = m.getSuggestedReplacements();
                for (int repIdx = 0; repIdx < repls.size(); repIdx++) {
                    if (repIdx > 0) sb.append("\u0003");
                    sb.append(repls.get(repIdx));
                }
            }
            out.print(sb.toString());
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "CheckPatternRules.java"
            src_file.write_text(java_src, encoding="utf-8")

            subprocess.run(
                ["javac", "-encoding", "UTF-8", "-cp", str(jar), str(src_file)],
                check=True,
                capture_output=True,
            )

            case_strings = [f"{c['full_rule_id']}\u0007{c['text']}" for c in cases]
            input_bytes = "\u0000".join(case_strings).encode("utf-8")

            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-Dstdout.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "CheckPatternRules",
                ],
                input=input_bytes,
                capture_output=True,
                check=True,
            )

            out_str = proc.stdout.decode("utf-8")
            if not out_str:
                return []

            results: List[Dict[str, Any]] = []
            for block in out_str.split("\u0006"):
                fields = block.split("\u0008")
                status = fields[0]
                if status == "NOT_FOUND":
                    results.append({"status": "NOT_FOUND", "target_rule_id": fields[1], "matches": []})
                elif status == "FOUND":
                    rule_id = fields[1]
                    full_rule_id = fields[2]
                    category_id = fields[3]
                    category_name = fields[4]
                    description = fields[5]
                    is_default_off = fields[6] == "1"
                    match_count = int(fields[7])

                    matches: List[Dict[str, Any]] = []
                    for m_str in fields[8 : 8 + match_count]:
                        m_parts = m_str.split("\u0002")
                        if len(m_parts) >= 5:
                            from_p = int(m_parts[0])
                            to_p = int(m_parts[1])
                            msg = m_parts[2]
                            short_msg = None if m_parts[3] == "\u0005null" else m_parts[3]
                            suggs = [s for s in m_parts[4].split("\u0003") if s] if m_parts[4] else []
                            matches.append(
                                {
                                    "from_utf16": from_p,
                                    "to_utf16": to_p,
                                    "message": msg,
                                    "short_message": short_msg,
                                    "suggestions": suggs,
                                }
                            )

                    results.append(
                        {
                            "status": "FOUND",
                            "rule_id": rule_id,
                            "full_rule_id": full_rule_id,
                            "category_id": category_id,
                            "category_name": category_name,
                            "description": description,
                            "is_default_off": is_default_off,
                            "matches_count": match_count,
                            "matches": matches,
                        }
                    )
            return results

    def evaluate_pattern_tokens(
        self, cases: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Evaluate PatternToken matching directly using Java LanguageTool classes."""
        self.validate_oracle()
        jar = self.get_jar_path()

        java_src = """package org.languagetool.rules.patterns;

import org.languagetool.rules.patterns.PatternToken;
import org.languagetool.AnalyzedToken;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class EvaluatePatternTokens {
    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] data = new byte[1024];
        int n;
        while ((n = System.in.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, n);
        }
        String text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (text.isEmpty()) return;

        String[] caseArray = text.split("\\u0000", -1);
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);

        for (int i = 0; i < caseArray.length; i++) {
            if (i > 0) out.print("\\u0006");
            String caseStr = caseArray[i];
            if (caseStr.isEmpty()) continue;

            String[] parts = caseStr.split("\\u0002", 2);
            String[] patParts = parts[0].split("\\u0001", -1);
            String[] tokParts = parts[1].split("\\u0001", -1);

            String patText = patParts[0].equals("\\u0005null") ? null : patParts[0];
            boolean isInflected = patParts[1].equals("1");
            boolean isCaseSensitive = patParts[2].equals("1");
            boolean isRegExp = patParts[3].equals("1");
            String postag = patParts[4].equals("\\u0005null") ? null : patParts[4];
            boolean isPosRegExp = patParts[5].equals("1");
            boolean hasException = patParts[6].equals("1");

            PatternToken pt = new PatternToken(patText, isCaseSensitive, isRegExp, isInflected);
            if (postag != null) {
                pt.setPosToken(new PatternToken.PosToken(postag, isPosRegExp, false));
            }

            if (hasException) {
                String excText = patParts[7].equals("\\u0005null") ? null : patParts[7];
                boolean excInflected = patParts[8].equals("1");
                String excPos = patParts[9].equals("\\u0005null") ? null : patParts[9];
                boolean excPosReg = patParts[10].equals("1");

                pt.setStringPosException(excText, false, excInflected, false, false, false, excPos, excPosReg, false, isCaseSensitive);
            }

            String token = tokParts[0];
            String posTag = tokParts[1].equals("\\u0005null") ? null : tokParts[1];
            String lemma = tokParts[2].equals("\\u0005null") ? null : tokParts[2];

            AnalyzedToken at = new AnalyzedToken(token, posTag, lemma);

            boolean isMatched = pt.isMatched(at);
            boolean isExceptionMatched = pt.isExceptionMatched(at);
            boolean finalMatch = isMatched && !isExceptionMatched;

            out.print((isMatched ? "1" : "0") + "\\u0001" + (isExceptionMatched ? "1" : "0") + "\\u0001" + (finalMatch ? "1" : "0"));
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir) / "org" / "languagetool" / "rules" / "patterns"
            pkg_dir.mkdir(parents=True, exist_ok=True)
            java_file = pkg_dir / "EvaluatePatternTokens.java"
            java_file.write_text(java_src, encoding="utf-8")

            res = subprocess.run(
                [
                    "javac",
                    "-encoding",
                    "UTF-8",
                    "-cp",
                    str(jar),
                    str(java_file),
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise RuntimeError(f"javac failed: {res.stderr}")

            case_strings = []
            for c in cases:
                pat = c["pattern"]
                tok = c["token"]
                pat_text = pat.get("text") or "\u0005null"
                inflected = "1" if pat.get("inflected") else "0"
                cs = "1" if pat.get("case_sensitive") else "0"
                regexp = "1" if pat.get("regexp") else "0"
                postag = pat.get("postag") or "\u0005null"
                pos_reg = "1" if pat.get("postag_regexp") else "0"
                has_exc = "1" if pat.get("has_exception") else "0"
                exc = pat.get("exception") or {}
                exc_text = exc.get("text") or "\u0005null"
                exc_inf = "1" if exc.get("inflected") else "0"
                exc_pos = exc.get("postag") or "\u0005null"
                exc_pos_reg = "1" if exc.get("postag_regexp") else "0"

                pat_str = f"{pat_text}\u0001{inflected}\u0001{cs}\u0001{regexp}\u0001{postag}\u0001{pos_reg}\u0001{has_exc}\u0001{exc_text}\u0001{exc_inf}\u0001{exc_pos}\u0001{exc_pos_reg}"

                token_val = tok.get("token")
                tok_pos = tok.get("pos_tag") or "\u0005null"
                tok_lemma = tok.get("lemma") or "\u0005null"
                tok_str = f"{token_val}\u0001{tok_pos}\u0001{tok_lemma}"

                case_strings.append(f"{pat_str}\u0002{tok_str}")

            input_bytes = "\u0000".join(case_strings).encode("utf-8")

            proc = subprocess.run(
                [
                    "java",
                    "-Dfile.encoding=UTF-8",
                    "-Dstdout.encoding=UTF-8",
                    "-cp",
                    f"{tmpdir}{os.pathsep}{jar}",
                    "org.languagetool.rules.patterns.EvaluatePatternTokens",
                ],
                input=input_bytes,
                capture_output=True,
                check=True,
            )

            out_str = proc.stdout.decode("utf-8")
            if not out_str:
                return []

            results: List[Dict[str, Any]] = []
            for block in out_str.split("\u0006"):
                parts = block.split("\u0001")
                if len(parts) >= 3:
                    results.append(
                        {
                            "is_matched": parts[0] == "1",
                            "is_exception_matched": parts[1] == "1",
                            "final_match": parts[2] == "1",
                        }
                    )
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
    # 8b. Special number tags with pos_tag_is_regex=True
    {"category": "special_number_regex", "token": "123", "lemma": "123", "pos_tag": "_spell_number_", "pos_tag_is_regex": True},
    {"category": "special_number_regex", "token": "123", "lemma": "123", "pos_tag": "_spell_number_:feminine", "pos_tag_is_regex": True},
    {"category": "special_number_regex", "token": "123", "lemma": "123", "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": True},
    {"category": "special_number_regex", "token": "123", "lemma": None, "pos_tag": "_spell_number_", "pos_tag_is_regex": True},
    {"category": "special_number_regex", "token": "123", "lemma": None, "pos_tag": "_spell_number_:feminine", "pos_tag_is_regex": True},
    {"category": "special_number_regex", "token": "123", "lemma": None, "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": True},
    # 9. Case sensitivity
    {"category": "case_sensitive", "token": "Семья", "lemma": "Семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "case_sensitive", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    # 10. Null lemma edge cases
    {"category": "null_lemma", "token": "семья", "lemma": None, "pos_tag": "NN:Inanim:Fem:Sin:Nom", "pos_tag_is_regex": False},
    {"category": "null_lemma", "token": "семья", "lemma": None, "pos_tag": "NN:Inanim:Fem:.*", "pos_tag_is_regex": True},
    {"category": "null_lemma_special_number", "token": "123", "lemma": None, "pos_tag": "_spell_number_", "pos_tag_is_regex": False},
    {"category": "null_lemma_special_number", "token": "123", "lemma": None, "pos_tag": "_spell_number_:feminine", "pos_tag_is_regex": False},
    {"category": "null_lemma_special_number", "token": "123", "lemma": None, "pos_tag": "_spell_number_:Roman", "pos_tag_is_regex": False},
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
        token_str = q.get("token", "")
        lemma_val = q.get("lemma")
        if lemma_val is None and "lemma" not in q:
            lemma_val = token_str
        queries_data.append(
            {
                "id": f"synth_{i + 1:03d}",
                "category": q["category"],
                "token": token_str,
                "lemma": lemma_val,
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




CHUNKER_TEST_CASES: List[Dict[str, Any]] = [
    # 1. Names and full name patterns (REGEXES1[0])
    {"id": "chunk_01_full_name", "category": "name_np", "text": "Иванов Иван Иванович пришел на встречу."},
    {"id": "chunk_02_two_names", "category": "name_np", "text": "Петров Петр ждет у входа."},
    {"id": "chunk_03_patronymic_name", "category": "name_np", "text": "Сидоров Сидор Сидорович уехал в отпуск."},
    # 2. Initials + surname / Surname + initials (REGEXES1[1], REGEXES1[2])
    {"id": "chunk_04_surname_initials", "category": "surname_initials", "text": "Иванов И. И. подписал приказ."},
    {"id": "chunk_05_surname_initials_nospace", "category": "surname_initials", "text": "Петров П.П. сдал отчет."},
    {"id": "chunk_06_initials_surname", "category": "initials_surname", "text": "И. И. Иванов подписал документ."},
    {"id": "chunk_07_initials_surname_nospace", "category": "initials_surname", "text": "С.С. Сидоров прибыл в город."},
    # 3. Verb phrases (REGEXES1[3])
    {"id": "chunk_08_verb_chain", "category": "vp_chain", "text": "Он начал читать новую книгу."},
    {"id": "chunk_09_verb_single", "category": "vp_single", "text": "Птицы поют в саду."},
    # 4. SBAR literals (REGEXES1[4], REGEXES1[5])
    {"id": "chunk_10_sbar_esli", "category": "sbar", "text": "Если пойдет дождь, мы останемся дома."},
    {"id": "chunk_11_sbar_poetomu", "category": "sbar", "text": "Поэтому решение было принято единогласно."},
    # 5. Adjective + Noun NP (REGEXES1[6], REGEXES1[7])
    {"id": "chunk_12_adj_noun", "category": "adj_noun_np", "text": "Красный флаг развевался на ветру."},
    {"id": "chunk_13_adj_noun_noun", "category": "adj_noun_np", "text": "Большой красивый дом стоял у реки."},
    # 6. Adj -> participle phrase (REGEXES1[8])
    {"id": "chunk_14_adj_participle", "category": "adjp_phrase", "text": "Уставший человек вернулся домой вечером."},
    # 7. Adverbial participle DPT (REGEXES1[9], REGEXES1[10], REGEXES1[11])
    {"id": "chunk_15_dpt_single", "category": "dpt", "text": "Улыбнувшись, он пожал руку гостю."},
    {"id": "chunk_16_dpt_noun", "category": "dpt", "text": "Прочитав книгу, студент закрыл ее."},
    {"id": "chunk_17_dpt_prep_noun", "category": "dpt", "text": "Подъезжая к станции, пассажиры готовились к выходу."},
    # 8. Participle ADJP (REGEXES1[12]..[19])
    {"id": "chunk_18_pt_single", "category": "adjp", "text": "Открытая дверь скрипнула."},
    {"id": "chunk_19_pt_adv", "category": "adjp", "text": "Быстро бегущий спортсмен финишировал первым."},
    {"id": "chunk_20_pt_noun", "category": "adjp", "text": "Человек, написавший письмо, ушел."},
    {"id": "chunk_21_pt_prep_noun", "category": "adjp", "text": "Поезд, прибывший на вокзал, остановился."},
    {"id": "chunk_22_pt_prep_adj_noun", "category": "adjp", "text": "Книга, найденная в старом шкафу, оказалась редкой."},
    {"id": "chunk_23_pt_pnn_noun", "category": "adjp", "text": "Студент, сдавший свой экзамен, вздохнул с облегчением."},
    {"id": "chunk_24_pt_adj", "category": "adjp", "text": "Освещенный яркий зал был полон гостей."},
    # 9. Title NP (REGEXES1[20])
    {"id": "chunk_25_tov", "category": "tov_np", "text": "Тов. Сидоров выступил перед коллективом."},
    # 10. Plural noun phrases with REGEXES2[0], REGEXES2[1]
    {"id": "chunk_26_plural_names_i", "category": "plural_np", "text": "Маша и Миша гуляли в парке."},
    {"id": "chunk_27_plural_names_ili", "category": "plural_np", "text": "Анна или Ольга помогут решить задачу."},
    # 11. Не + VB with REGEXES2[2]
    {"id": "chunk_28_ne_verb", "category": "ne_vp", "text": "Я не знаю ответа на этот вопрос."},
    {"id": "chunk_29_ne_verb_chain", "category": "ne_vp", "text": "Мы не можем продолжать молчать."},
    # 12. MayMissingYO exclusion & Non-BMP emoji
    {"id": "chunk_30_yo_and_emoji", "category": "yo_and_emoji", "text": "🚀 Иван Иванович пошел в лес за грибами."},
    # 13. Synthetic boundary cases with explicit pre-existing chunk tags
    {
        "id": "chunk_31_unrelated_preexisting_tag",
        "category": "unrelated_preexisting_tag",
        "text": "Студент шел в университет.",
        "inject_chunks": {"Студент": ["CUSTOM_PRE_TAG"]},
    },
    {
        "id": "chunk_32_filter_tag_preexisting",
        "category": "filter_tag_preexisting",
        "text": "Иванов Иван Иванович встретил Петра.",
        "inject_chunks": {"Иванов": ["PP"]},
    },
    {
        "id": "chunk_33_may_missing_yo_exclusion",
        "category": "may_missing_yo_exclusion",
        "text": "Все студенты сдали экзамен.",
        "inject_chunks": {"Все": ["MayMissingYO"]},
    },
    {
        "id": "chunk_34_ambiguous_readings",
        "category": "ambiguous_readings",
        "text": "Печь пироги было весело.",
    },
]


def generate_chunker_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Generate oracle Russian chunker fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    output_path = fixtures_dir / "oracle_russian_chunker.json"
    payload = []
    for c in CHUNKER_TEST_CASES:
        txt = c["text"]
        injected = c.get("inject_chunks")
        if injected:
            spec_str = ";".join(f"{tok}:{','.join(tags)}" for tok, tags in injected.items())
            payload.append(f"{txt}\u0008{spec_str}")
        else:
            payload.append(txt)

    stages_results = oracle.chunk_sentences(payload)

    cases: List[Dict[str, Any]] = []
    for i, item in enumerate(CHUNKER_TEST_CASES):
        case_obj: Dict[str, Any] = {
            "id": item["id"],
            "category": item["category"],
            "text": item["text"],
        }
        if "inject_chunks" in item:
            case_obj["inject_chunks"] = item["inject_chunks"]
        case_obj["stages"] = stages_results[i]
        cases.append(case_obj)

    fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Chunker Fixture",
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
        f"Generated Russian chunker fixture -> {output_path} ({len(cases)} cases, oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


GRAMMAR_CORE_TEST_CASES: List[Dict[str, Any]] = [
    # 1. LOGIC (18 cases)
    {"id": "gc_01_zadat_test_match", "category": "LOGIC", "full_rule_id": "zadat_test", "text": "Ученик решил задать тест учителю."},
    {"id": "gc_02_zadat_test_correct", "category": "LOGIC", "full_rule_id": "zadat_test", "text": "Ученик решил предложить тест учителю."},
    {"id": "gc_03_perehodny_match", "category": "LOGIC", "full_rule_id": "perehodny_peshehod", "text": "Здесь опасный переходный пешеход."},
    {"id": "gc_04_perehodny_correct", "category": "LOGIC", "full_rule_id": "perehodny_peshehod", "text": "Здесь безопасный пешеходный переход."},
    {"id": "gc_05_plohoj_den_match", "category": "LOGIC", "full_rule_id": "plohoj_den", "text": "Сегодня был плахой день."},
    {"id": "gc_06_plohoj_den_correct", "category": "LOGIC", "full_rule_id": "plohoj_den", "text": "Сегодня был хороший день."},
    {"id": "gc_07_odin_za_odnim_match", "category": "LOGIC", "full_rule_id": "odin_za_odnim", "text": "Они шли один за одним по тропинке."},
    {"id": "gc_08_odin_za_odnim_correct", "category": "LOGIC", "full_rule_id": "odin_za_odnim", "text": "Они шли один за другим по тропинке."},
    {"id": "gc_09_vazhno_1_match", "category": "LOGIC", "full_rule_id": "Vazhno_chto_etogo[1]", "text": "Важно, что этого не произошло."},
    {"id": "gc_10_vazhno_2_match", "category": "LOGIC", "full_rule_id": "Vazhno_chto_etogo[2]", "text": "Важно то, что этого не произошло."},
    {"id": "gc_11_interesnaja_kniga_match", "category": "LOGIC", "full_rule_id": "Slovosoch_interesnaja_kniga", "text": "Это была очень интересная книга."},
    {"id": "gc_12_interesnaja_kniga_correct", "category": "LOGIC", "full_rule_id": "Slovosoch_interesnaja_kniga", "text": "Это была очень увлекательная книга."},
    {"id": "gc_13_dumu_dumat_1_match", "category": "LOGIC", "full_rule_id": "DUMU_DUMAT[1]", "text": "Он сидел и думу думал."},
    {"id": "gc_14_dumu_dumat_2_match", "category": "LOGIC", "full_rule_id": "DUMU_DUMAT[2]", "text": "Они сидели и думали думу."},
    {"id": "gc_15_dumu_dumat_correct", "category": "LOGIC", "full_rule_id": "DUMU_DUMAT[1]", "text": "Он сидел и глубоко думал."},
    {"id": "gc_16_tavtology_aborigen_match", "category": "LOGIC", "full_rule_id": "Tavtology_mestnij_aborigen", "text": "Нас окружили местные аборигены."},
    {"id": "gc_17_tavtology_aborigen_correct", "category": "LOGIC", "full_rule_id": "Tavtology_mestnij_aborigen", "text": "Нас окружили аборигены."},
    {"id": "gc_18_tavtology_gorstka_match", "category": "LOGIC", "full_rule_id": "Tavtology_nebolshaja_gorstka", "text": "Была небольшая горстка людей."},

    # 2. PUNCTUATION (10 cases)
    {"id": "gc_19_pozhalujsta_1_match", "category": "PUNCTUATION", "full_rule_id": "POZHALUJSTA[1]", "text": "Скажи пожалуйста где выход."},
    {"id": "gc_20_pozhalujsta_1_correct", "category": "PUNCTUATION", "full_rule_id": "POZHALUJSTA[1]", "text": "Скажи, пожалуйста, где выход."},
    {"id": "gc_21_pozhalujsta_2_match", "category": "PUNCTUATION", "full_rule_id": "POZHALUJSTA[2]", "text": "Пожалуйста помогите мне."},
    {"id": "gc_22_pozhalujsta_2_correct", "category": "PUNCTUATION", "full_rule_id": "POZHALUJSTA[2]", "text": "Пожалуйста, помогите мне."},
    {"id": "gc_23_privet_druzja_match", "category": "PUNCTUATION", "full_rule_id": "Privet_druzja[1]", "text": "Привет друзья!"},
    {"id": "gc_24_privet_druzja_correct", "category": "PUNCTUATION", "full_rule_id": "Privet_druzja[1]", "text": "Привет, друзья!"},
    {"id": "gc_25_kak_bi_to_ni_bilo_match", "category": "PUNCTUATION", "full_rule_id": "Kak_bi_to_ni_bilo[1]", "text": "Как бы то ни было мы продолжим."},
    {"id": "gc_26_kak_bi_to_ni_bilo_correct", "category": "PUNCTUATION", "full_rule_id": "Kak_bi_to_ni_bilo[1]", "text": "Как бы то ни было, мы продолжим."},
    {"id": "gc_27_comma_and_to_jest_match", "category": "PUNCTUATION", "full_rule_id": "comma_and_to_jest", "text": "Он пришел и то есть помог."},
    {"id": "gc_28_comma_and_to_jest_correct", "category": "PUNCTUATION", "full_rule_id": "comma_and_to_jest", "text": "Он пришел, то есть помог."},

    # 3. GRAMMAR (14 cases)
    {"id": "gc_29_pravopisanie_slitno1_3_match", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[3]", "text": "Они спустились в низ по лестнице."},
    {"id": "gc_30_pravopisanie_slitno1_3_correct", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[3]", "text": "Они спустились вниз по лестнице."},
    {"id": "gc_31_pravopisanie_slitno1_4_match", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[4]", "text": "В дали показался корабль."},
    {"id": "gc_32_pravopisanie_slitno1_4_correct", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[4]", "text": "Вдали показался корабль."},
    {"id": "gc_33_pravopisanie_slitno1_5_match", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[5]", "text": "Они посмотрели в даль моря."},
    {"id": "gc_34_pravopisanie_slitno1_5_correct", "category": "GRAMMAR", "full_rule_id": "Pravopisanie_slitno1[5]", "text": "Они посмотрели вдаль моря."},
    {"id": "gc_35_prosit_proshenija_match", "category": "GRAMMAR", "full_rule_id": "prosit_proshenija", "text": "Он пришел просить прощения у всех."},
    {"id": "gc_36_prosit_proshenija_correct", "category": "GRAMMAR", "full_rule_id": "prosit_proshenija", "text": "Он пришел просить прощение у всех."},
    {"id": "gc_37_skuchat_za_match", "category": "GRAMMAR", "full_rule_id": "skuchat_za", "text": "Она стала скучать за ним в разлуке."},
    {"id": "gc_38_skuchat_za_correct", "category": "GRAMMAR", "full_rule_id": "skuchat_za", "text": "Она стала скучать по нему в разлуке."},
    {"id": "gc_39_kak_ni_stranno_match", "category": "GRAMMAR", "full_rule_id": "kak_ni_stranno", "text": "Как не странно, все получилось."},
    {"id": "gc_40_kak_ni_stranno_correct", "category": "GRAMMAR", "full_rule_id": "kak_ni_stranno", "text": "Как ни странно, все получилось."},
    {"id": "gc_41_dlya_togo_chtob_match", "category": "GRAMMAR", "full_rule_id": "dlya_togo_chtoby_2", "text": "Для того чтоб это сделать."},
    {"id": "gc_42_takim_obrazom_chto_match", "category": "GRAMMAR", "full_rule_id": "takim_obrazom_chto", "text": "Сделано таким образом что работает."},

    # 4. STYLE (8 cases)
    {"id": "gc_43_ugasno_krasivij_match", "category": "STYLE", "full_rule_id": "ugasno_krasivij[1]", "text": "Это было ужасно красиво и ярко."},
    {"id": "gc_44_ugasno_krasivij_correct", "category": "STYLE", "full_rule_id": "ugasno_krasivij[1]", "text": "Это было очень красиво и ярко."},
    {"id": "gc_45_nagnat_strahu_match", "category": "STYLE", "full_rule_id": "nagnat_strahu[1]", "text": "Он решил нагнать страху на врагов."},
    {"id": "gc_46_nagnat_strahu_correct", "category": "STYLE", "full_rule_id": "nagnat_strahu[1]", "text": "Он решил нагнать страх на врагов."},
    {"id": "gc_47_ni_v_koem_match", "category": "STYLE", "full_rule_id": "ni_v_koem_sluchae[1]", "text": "Ни в коем случае нельзя это делать."},
    {"id": "gc_48_bolee_menee_match", "category": "STYLE", "full_rule_id": "Logical_bolee_menee[1]", "text": "Это более или менее понятно."},
    {"id": "gc_49_use_prep_o_match", "category": "STYLE", "full_rule_id": "Use_prep_O[1]", "text": "Мы говорили о брате."},
    {"id": "gc_50_use_prep_o_correct", "category": "STYLE", "full_rule_id": "Use_prep_O[1]", "text": "Мы говорили про брата."},

    # 5. TYPOS & EXTEND & Special Cases (12 cases)
    {"id": "gc_51_v_techenii_match", "category": "GRAMMAR", "full_rule_id": "V_TECHENII", "text": "В течении реки есть пороги."},
    {"id": "gc_52_v_techenii_correct", "category": "GRAMMAR", "full_rule_id": "V_TECHENII", "text": "В течение реки есть пороги."},
    {"id": "gc_53_v_prodolzhenie_match", "category": "GRAMMAR", "full_rule_id": "V_PRODOLJENI\u0415[1]", "text": "В продолжении недели мы работали."},
    {"id": "gc_54_v_prodolzhenie_correct", "category": "GRAMMAR", "full_rule_id": "V_PRODOLJENI\u0415[1]", "text": "В продолжение недели мы работали."},
    {"id": "gc_55_v_zakluchenie_match", "category": "EXTEND", "full_rule_id": "Predlog_v_zakluchenije[1]", "text": "В заключении хочу сказать спасибо."},
    {"id": "gc_56_v_zakluchenie_correct", "category": "EXTEND", "full_rule_id": "Predlog_v_zakluchenije[1]", "text": "В заключение хочу сказать спасибо."},
    {"id": "gc_57_adv_vposledstvii_match", "category": "EXTEND", "full_rule_id": "Adv_vposledstvii[1]", "text": "В последствии все наладилось."},
    {"id": "gc_58_adv_vposledstvii_correct", "category": "EXTEND", "full_rule_id": "Adv_vposledstvii[1]", "text": "Впоследствии все наладилось."},
    {"id": "gc_59_adv_vposledstvii_2_match", "category": "EXTEND", "full_rule_id": "Adv_vposledstvii[2]", "text": "В последствие все наладилось."},
    {"id": "gc_60_neujto_match", "category": "PUNCTUATION", "full_rule_id": "NEUJTO", "text": "Неужтоли это правда?"},
    {"id": "gc_61_capitalization_match", "category": "LOGIC", "full_rule_id": "Tavtology_mestnij_aborigen", "text": "Местные аборигены нас окружили."},
    {"id": "gc_62_emoji_offset_match", "category": "LOGIC", "full_rule_id": "Tavtology_mestnij_aborigen", "text": "🚀 Нас окружили местные аборигены."},
]


def generate_grammar_core_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Generate oracle Russian grammar core fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    output_path = fixtures_dir / "oracle_russian_grammar_core.json"
    cases_input = [{"full_rule_id": c["full_rule_id"], "text": c["text"]} for c in GRAMMAR_CORE_TEST_CASES]
    results = oracle.check_pattern_rules(cases_input)

    cases: List[Dict[str, Any]] = []
    for i, item in enumerate(GRAMMAR_CORE_TEST_CASES):
        res = results[i]
        cases.append(
            {
                "id": item["id"],
                "category": item["category"],
                "full_rule_id": item["full_rule_id"],
                "text": item["text"],
                "oracle_result": res,
            }
        )

    fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Grammar Core Fixture",
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
        f"Generated Russian grammar core fixture -> {output_path} ({len(cases)} cases, oracle SHA: {oracle_sha}, build: {oracle_build_id})"
    )


PATTERN_TOKEN_INFLECTED_CASES: List[Dict[str, Any]] = [
    {
        "id": "pt_inflected_01_surface_matches_lemma_differs",
        "description": "Surface matches pattern ('бежать') but non-null lemma differs ('побег') -> no match",
        "pattern": {
            "text": "бежать",
            "inflected": True,
            "case_sensitive": False,
            "regexp": False,
            "postag": None,
            "postag_regexp": False,
            "has_exception": False,
            "exception": None,
        },
        "token": {
            "token": "бежать",
            "pos_tag": "NN:Inan:Fem",
            "lemma": "побег",
        },
    },
    {
        "id": "pt_inflected_02_lemma_matches_surface_differs",
        "description": "Lemma matches pattern ('бежать') while surface differs ('бежал') -> match",
        "pattern": {
            "text": "бежать",
            "inflected": True,
            "case_sensitive": False,
            "regexp": False,
            "postag": None,
            "postag_regexp": False,
            "has_exception": False,
            "exception": None,
        },
        "token": {
            "token": "бежал",
            "pos_tag": "VB:Past:Masc",
            "lemma": "бежать",
        },
    },
    {
        "id": "pt_inflected_03_lemma_null_surface_fallback_match",
        "description": "Lemma is null -> fallback to surface token ('неизвестно') matching pattern -> match",
        "pattern": {
            "text": "неизвестно",
            "inflected": True,
            "case_sensitive": False,
            "regexp": False,
            "postag": None,
            "postag_regexp": False,
            "has_exception": False,
            "exception": None,
        },
        "token": {
            "token": "неизвестно",
            "pos_tag": "ADV",
            "lemma": None,
        },
    },
    {
        "id": "pt_inflected_04_lemma_null_surface_differs_no_match",
        "description": "Lemma is null -> fallback to surface token ('другое') not matching pattern ('бежать') -> no match",
        "pattern": {
            "text": "бежать",
            "inflected": True,
            "case_sensitive": False,
            "regexp": False,
            "postag": None,
            "postag_regexp": False,
            "has_exception": False,
            "exception": None,
        },
        "token": {
            "token": "другое",
            "pos_tag": "ADJ",
            "lemma": None,
        },
    },
    {
        "id": "pt_inflected_05_exception_inflected_match_excluded",
        "description": "Token matches POS (VB:.*), exception has inflected='делать'. Lemma is 'делать', so exception matches -> excluded (finalMatch=false)",
        "pattern": {
            "text": None,
            "inflected": False,
            "case_sensitive": False,
            "regexp": False,
            "postag": "VB:.*",
            "postag_regexp": True,
            "has_exception": True,
            "exception": {
                "text": "делать",
                "inflected": True,
                "postag": None,
                "postag_regexp": False,
            },
        },
        "token": {
            "token": "делал",
            "pos_tag": "VB:Past:Masc",
            "lemma": "делать",
        },
    },
    {
        "id": "pt_inflected_06_exception_inflected_differs_included",
        "description": "Token matches POS (VB:.*), exception has inflected='делать'. Lemma is 'дело', exception does not match -> included (finalMatch=true)",
        "pattern": {
            "text": None,
            "inflected": False,
            "case_sensitive": False,
            "regexp": False,
            "postag": "VB:.*",
            "postag_regexp": True,
            "has_exception": True,
            "exception": {
                "text": "делать",
                "inflected": True,
                "postag": None,
                "postag_regexp": False,
            },
        },
        "token": {
            "token": "делал",
            "pos_tag": "VB:Past:Masc",
            "lemma": "дело",
        },
    },
]


def generate_pattern_token_fixtures(
    oracle: JavaLanguageToolOracle, fixtures_dir: Path
) -> None:
    """Generate oracle PatternToken inflected semantics fixture directly from pinned Java LT."""
    val = oracle.validate_oracle()
    oracle_sha = val.get("jar_sha256", "UNKNOWN")
    oracle_build_id = val.get("oracle_build_id", "UNKNOWN")

    output_path = fixtures_dir / "oracle_pattern_token_inflected.json"
    results = oracle.evaluate_pattern_tokens(PATTERN_TOKEN_INFLECTED_CASES)

    cases: List[Dict[str, Any]] = []
    for i, item in enumerate(PATTERN_TOKEN_INFLECTED_CASES):
        cases.append(
            {
                "id": item["id"],
                "description": item["description"],
                "pattern": item["pattern"],
                "token": item["token"],
                "oracle_result": results[i],
            }
        )

    fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle PatternToken Inflected Semantics Fixture",
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
        f"Generated PatternToken inflected fixture -> {output_path} ({len(cases)} cases, oracle SHA: {oracle_sha}, build: {oracle_build_id})"
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
    parser.add_argument(
        "--generate-chunker-fixtures",
        action="store_true",
        help="Generate Russian chunker fixtures from Java LanguageTool oracle",
    )
    parser.add_argument(
        "--generate-grammar-core-fixtures",
        action="store_true",
        help="Generate Russian grammar core fixtures from Java LanguageTool oracle",
    )
    parser.add_argument(
        "--generate-pattern-token-fixtures",
        action="store_true",
        help="Generate PatternToken inflected semantics fixtures from Java LanguageTool oracle",
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

    if args.generate_chunker_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_chunker_fixtures(oracle, fixtures_dir)
        return 0

    if args.generate_grammar_core_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_grammar_core_fixtures(oracle, fixtures_dir)
        return 0

    if args.generate_pattern_token_fixtures:
        try:
            oracle.validate_oracle()
        except Exception as e:
            print(
                f"Refusing fixture generation: Java LanguageTool oracle identity cannot be proven: {e}",
                file=sys.stderr,
            )
            return 1
        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        generate_pattern_token_fixtures(oracle, fixtures_dir)
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


