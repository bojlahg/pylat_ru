"""Persistent batched Java LanguageTool oracle for the Task-0014 differential campaign.

Development/test only.  The installed ``pylat_ru`` distribution never imports this
module and never needs a JVM; see ``tests/unit/test_production_dependency_audit_0013.py``
and ``tests/unit/test_differential_boundary_0014.py``.

The wrapper drives ``tools/DifferentialCorpusOracle0014.java``: it validates the trusted
pinned jar, compiles the helper once into the oracle cache, starts a single JVM, and then
serves thousands of whole-pipeline Russian checks over one long-lived process.  Every
response echoes its case id so a desynchronised or dead stream fails loudly instead of
silently misattributing Java results to the wrong case.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.differential_lt import (  # noqa: E402
    Finding,
    JavaLanguageToolOracle,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SOURCE = REPO_ROOT / "tools" / "DifferentialCorpusOracle0014.java"
JAVA_MAIN_CLASS = "DifferentialCorpusOracle0014"

#: Suggestion list separator used by the Java helper.  Chosen because no LanguageTool
#: suggestion may contain a C0 control character.
SUGGESTION_SEPARATOR = "\u0001"

#: Language-model rule kept outside the ordinary/non-LM differential surface.
LANGUAGE_MODEL_RULE_ID = "CONFUSION_RULE"


class OracleProtocolError(RuntimeError):
    """Raised when the Java oracle stream desynchronises, errors, or dies."""


@dataclass(frozen=True)
class Profile:
    """One whole-pipeline configuration applied identically to Java and Python."""

    profile_id: str
    enabled_rules: tuple[str, ...] = ()
    disabled_rules: tuple[str, ...] = ()
    rule_config: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    enable_all_default_off: bool = False

    def config_spec(self) -> str:
        """Serialise ``rule_config`` deterministically for the Java helper."""
        entries = []
        for rule_id in sorted(self.rule_config):
            options = self.rule_config[rule_id]
            pairs = ",".join(
                f"{key}:{_java_literal(options[key])}" for key in sorted(options)
            )
            entries.append(f"{rule_id}={pairs}")
        return ";".join(entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "enabled_rules": list(self.enabled_rules),
            "disabled_rules": list(self.disabled_rules),
            "rule_config": {
                rule_id: dict(sorted(self.rule_config[rule_id].items()))
                for rule_id in sorted(self.rule_config)
            },
            "enable_all_default_off": self.enable_all_default_off,
        }

    def signature(self) -> str:
        """Stable content hash of the profile, used inside case identities."""
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _java_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True)
class JavaRuleInfo:
    """One rule as the pinned Java pipeline reports it for a given profile."""

    rule_id: str
    full_rule_id: str
    category_id: str
    default_off: bool
    rule_class: str


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _unb64(value: str) -> str:
    return base64.b64decode(value).decode("utf-8") if value else ""


class BatchJavaOracle:
    """One JVM, one pinned Russian pipeline per profile, many cases.

    Use as a context manager::

        with BatchJavaOracle() as oracle:
            oracle.define_profile(Profile("default"))
            findings = oracle.check("case_0001", "default", "Это тест.")
    """

    def __init__(
        self,
        jar_path: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        manifest_path: Optional[Path] = None,
        heap: str = "2g",
    ) -> None:
        self._oracle = JavaLanguageToolOracle(
            jar_path=jar_path, cache_dir=cache_dir, manifest_path=manifest_path
        )
        self.heap = heap
        self._process: Optional[subprocess.Popen] = None
        self._profiles: Dict[str, Profile] = {}
        self.validation: Dict[str, Any] = {}

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "BatchJavaOracle":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        """Validate the trusted oracle, compile the helper, and start the JVM."""
        if self._process is not None:
            return
        self.validation = self._oracle.validate_oracle()
        jar = self._oracle.get_jar_path()
        if jar is None:  # pragma: no cover - validate_oracle already fails closed
            raise RuntimeError("Trusted LanguageTool jar not found")
        classes_dir = self._compile(jar)

        self._process = subprocess.Popen(
            [
                "java",
                f"-Xmx{self.heap}",
                "-Dfile.encoding=UTF-8",
                "-Dstdout.encoding=UTF-8",
                "-cp",
                f"{classes_dir}{os.pathsep}{jar}",
                JAVA_MAIN_CLASS,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            text=True,
            encoding="utf-8",
        )
        if self._request("PING") != ["PONG"]:  # pragma: no cover - defensive
            raise OracleProtocolError("Java oracle did not answer the startup PING")

    def _compile(self, jar: Path) -> Path:
        """Compile the helper into the oracle cache, reusing an up-to-date build."""
        source_hash = hashlib.sha256(JAVA_SOURCE.read_bytes()).hexdigest()[:16]
        classes_dir = self._oracle.cache_dir / f"classes_0014_{source_hash}"
        marker = classes_dir / f"{JAVA_MAIN_CLASS}.class"
        if marker.is_file():
            return classes_dir
        classes_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "javac",
                "-encoding",
                "UTF-8",
                "-cp",
                str(jar),
                "-d",
                str(classes_dir),
                str(JAVA_SOURCE),
            ],
            check=True,
            capture_output=True,
        )
        return classes_dir

    def close(self) -> None:
        if self._process is None:
            return
        process = self._process
        try:
            if process.poll() is None and process.stdin is not None:
                process.stdin.write("QUIT\n")
                process.stdin.flush()
                process.wait(timeout=30)
        except Exception:  # pragma: no cover - best-effort shutdown
            process.kill()
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:  # pragma: no cover
                        pass
            self._process = None

    # -- protocol ----------------------------------------------------------

    def _request(self, line: str) -> List[str]:
        """Send one framed request and read its complete response block."""
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise OracleProtocolError("Java oracle process is not running")
        if process.poll() is not None:
            raise OracleProtocolError(
                f"Java oracle process died with exit code {process.returncode}"
            )
        process.stdin.write(line + "\n")
        process.stdin.flush()

        collected: List[str] = []
        while True:
            response = process.stdout.readline()
            if not response:
                stderr = process.stderr.read() if process.stderr else ""
                raise OracleProtocolError(
                    f"Java oracle closed its output stream unexpectedly. stderr: {stderr[:2000]}"
                )
            response = response.rstrip("\n").rstrip("\r")
            collected.append(response)
            head = response.split("\t", 1)[0]
            if head in ("PONG", "BYE", "PROFILE_OK", "END", "ERROR"):
                return collected

    # -- operations --------------------------------------------------------

    def define_profile(self, profile: Profile) -> int:
        """Create (or replace) one pinned Java pipeline for ``profile``."""
        request = "\t".join(
            [
                "PROFILE",
                profile.profile_id,
                _b64(",".join(profile.enabled_rules)),
                _b64(",".join(profile.disabled_rules)),
                _b64(profile.config_spec()),
                "1" if profile.enable_all_default_off else "0",
            ]
        )
        response = self._request(request)
        head = response[-1].split("\t")
        if head[0] == "ERROR":
            raise OracleProtocolError(
                f"Java oracle refused profile {profile.profile_id!r}: {_unb64(head[2])}"
            )
        if head[1] != profile.profile_id:
            raise OracleProtocolError(
                f"Java oracle profile response desynchronised: expected "
                f"{profile.profile_id!r}, got {head[1]!r}"
            )
        self._profiles[profile.profile_id] = profile
        return int(head[2])

    def rule_inventory(self, profile_id: str) -> List[JavaRuleInfo]:
        """Return every rule the pinned pipeline registers for ``profile_id``."""
        response = self._request("\t".join(["INVENTORY", profile_id]))
        last = response[-1].split("\t")
        if last[0] == "ERROR":
            raise OracleProtocolError(f"Java oracle inventory failed: {_unb64(last[2])}")
        rules: List[JavaRuleInfo] = []
        for line in response:
            fields = line.split("\t")
            if fields[0] != "RULE":
                continue
            rules.append(
                JavaRuleInfo(
                    rule_id=_unb64(fields[2]),
                    full_rule_id=_unb64(fields[3]),
                    category_id=_unb64(fields[4]),
                    default_off=fields[5] == "1",
                    rule_class=_unb64(fields[6]),
                )
            )
        return rules

    def check(self, case_id: str, profile_id: str, text: str) -> List[Finding]:
        """Run one whole-pipeline Java check and return ordered findings."""
        response = self._request(
            "\t".join(["CHECK", case_id, profile_id, _b64(text)])
        )
        head = response[0].split("\t")
        if head[0] == "ERROR":
            raise OracleProtocolError(
                f"Java oracle error for case {case_id!r}: {_unb64(head[2])}"
            )
        if head[0] != "RESULT" or head[1] != case_id:
            raise OracleProtocolError(
                f"Java oracle response desynchronised: expected RESULT for {case_id!r}, "
                f"got {response[0][:200]!r}"
            )
        expected = int(head[2])
        findings = [_parse_finding(line) for line in response[1:-1]]
        if len(findings) != expected:
            raise OracleProtocolError(
                f"Java oracle promised {expected} findings for {case_id!r} but sent {len(findings)}"
            )
        tail = response[-1].split("\t")
        if tail[0] != "END" or tail[1] != case_id:
            raise OracleProtocolError(
                f"Java oracle did not terminate case {case_id!r} correctly: {response[-1][:200]!r}"
            )
        return findings

    def check_many(
        self, cases: Iterable[tuple[str, str, str]]
    ) -> List[tuple[str, List[Finding]]]:
        """Run many ``(case_id, profile_id, text)`` triples in deterministic order."""
        return [
            (case_id, self.check(case_id, profile_id, text))
            for case_id, profile_id, text in cases
        ]


def _parse_finding(line: str) -> Finding:
    fields = line.split("\t")
    if fields[0] != "F":
        raise OracleProtocolError(f"Unexpected Java oracle finding line: {line[:200]!r}")
    from_pos = int(fields[1])
    to_pos = int(fields[2])
    raw_suggestions = _unb64(fields[9])
    suggestions = raw_suggestions.split(SUGGESTION_SEPARATOR) if raw_suggestions else []
    return Finding(
        rule_id=_unb64(fields[3]),
        category_id=_unb64(fields[5]),
        message=_unb64(fields[7]),
        offset=from_pos,
        length=to_pos - from_pos,
        suggestions=suggestions,
        source="java_lt",
        short_message=_unb64(fields[8]),
        url=_unb64(fields[10]),
    )


def pylat_findings(matches: Sequence[Any]) -> List[Finding]:
    """Project ``pylat_ru.RuleMatch`` objects onto the strict comparison schema.

    The comparison span is the UTF-16 span because Java ``RuleMatch`` positions index
    a UTF-16 ``String``.  Code-point positions are carried along for diagnostics only.
    """
    findings: List[Finding] = []
    for match in matches:
        findings.append(
            Finding(
                rule_id=match.rule_id,
                category_id=match.category_id,
                message=match.message,
                offset=match.utf16_offset,
                length=match.utf16_length,
                suggestions=list(match.replacements),
                source="pylat_ru",
                short_message=match.short_message or "",
                url=match.url or "",
                codepoint_offset=match.offset,
                codepoint_length=match.length,
            )
        )
    return findings
