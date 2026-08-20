"""Deterministic, fail-closed mini-parser for pinned LanguageTool JUnit sources.

This module is a *development-only* tool.  It is never imported by
``pylat_ru`` production code.

It is intentionally **not** a full Java parser.  It understands exactly the
syntax used by the pinned LanguageTool 6.8 Russian test module and the core
base/helper test classes those tests inherit from, and it raises
:class:`JavaParseError` on anything it cannot account for, so that a silent
undercount is impossible.

Structural model
----------------
* comments are blanked (they never contribute assertions, see Task 0013 section 8);
* string/char literal *contents* are blanked for structural scanning, so that
  braces or parentheses inside literals cannot corrupt brace matching;
* only declarations at class-body depth 1 are treated as methods of the class
  (inner/anonymous classes are never counted).

Scenario/assertion counting rule (Task 0013 section 8)
------------------------------------------------------
Within an executable method body, an *invocation at parenthesis depth 0* is a
counting candidate.  Nested invocations that appear as arguments of another
invocation are arguments, not scenarios, and are never counted.

A candidate is classified as:

``ASSERTION``
    a JUnit/Hamcrest assertion call (``assertEquals``, ``assertThat``, ``fail``,
    ...) -> 1 assertion unit;
``DELEGATION``
    a call to a method declared by the same class or one of its vendored
    superclasses, or a ``new Helper(...).method(...)`` call -> 1 scenario unit,
    and the target is recorded for further accounting;
``SETUP``
    an explicitly allow-listed non-scenario call (object construction,
    accessors, fixture plumbing) -> 0 units.

Anything else raises :class:`JavaParseError`.

A ``for (T x : VECTOR)`` loop whose ``VECTOR`` resolves to a field initialised
from a literal collection contributes ``len(unique elements) * (units inside
the loop body)`` units, and the invocations inside the loop body are not
counted again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class JavaParseError(RuntimeError):
    """Raised when the pinned source contains syntax this tool cannot account for."""


# --- classification vocabulary ---------------------------------------------

ASSERTION_CALLS = frozenset({
    "assertEquals",
    "assertNotEquals",
    "assertArrayEquals",
    "assertTrue",
    "assertFalse",
    "assertNull",
    "assertNotNull",
    "assertSame",
    "assertNotSame",
    "assertThat",
    "assertThrows",
    "fail",
})

# Receiver-less or qualified calls that perform no assertion and create no
# scenario.  Anything not listed here and not resolvable as an assertion or an
# in-class delegation fails the extraction.
SETUP_CALLS = frozenset({
    # fixture plumbing / object graph construction / accessors
    "getInstance", "getMessages", "getEnglishMessages", "getLanguageForShortCode",
    "getMessageBundle", "getDataBroker", "getResourceDir", "getRulesDir",
    "getShortCode", "getShortCodeWithCountryAndVariant", "getName",
    "getAllRules", "getAllActiveRules", "getAnalyzedSentence",
    "getRawAnalyzedSentence", "getSynthesizer", "getDisambiguator",
    "getRuleFileNames", "getSpellingFileName", "getMaintainedState",
    "getClass", "getResourceAsStream", "getFromResourceDirAsStream",
    "getFromResourceDirAsUrl", "getAsStream", "getDictionaryPath",
    "getRelevantLanguageModelRules", "getWrongWords", "getSuggestion",
    "getSuggestedReplacements", "getCompoundRuleData", "getIncorrectCompounds",
    "getDashSuggestion", "getJoinedSuggestion", "getJoinedLowerCaseSuggestion",
    "getFileNames", "getId", "getFullId", "getDescription", "getMessage",
    "getSourceFile", "getPatternTokens", "getSuggestionMatches",
    "getSuggestionMatchesOutMsg", "getPosTag", "getPosTagReplace", "getSubId",
    "getCategory", "getTags", "getExample", "getCorrections",
    "getUntouchedExamples", "getExamples", "getDisambiguated", "getAmbiguous",
    "getCorrectExamples", "getIncorrectExamples", "getErrorTriggeringExamples",
    "getSuggestionsOutMsg", "getDefaultSpellingRule", "getPatternRuleId",
    "getRules", "getWithDemoLanguage", "get", "getOrDefault", "getKey",
    "getValue", "getSpecificRuleId", "getToPos", "getFromPos", "getWord",
    "getStem", "getTag", "getPattern", "getXmlLineNumber", "getShortMessage",
    "getPatternRulesByIdAndSubId", "getMatchesForText",
    "getMatchesForSingleSentence", "getTokens", "getTokenRef", "getPOStag",
    "getLanguage", "getAntiPatterns", "getMaxBackReferenceNo", "getMatchNos",
    "getAsStrings", "getAsString", "getNoWhitespaceTokens", "getFilter",
    "getAllPatternRules", "getGrammarFileNames",
    # mutation / plumbing / JDK
    "put", "add", "addAll", "addError", "remove", "contains", "containsKey",
    "keySet", "values", "entrySet", "isEmpty", "size", "length", "trim",
    "toString", "equals", "equalsIgnoreCase", "startsWith", "endsWith",
    "matches", "replace", "replaceAll", "substring", "indexOf", "split",
    "join", "sort", "stream", "anyMatch", "filter", "collect", "distinct",
    "max", "incrementAndGet", "submit", "shutdown", "start", "lock", "unlock",
    "writeLock", "readLock", "availableProcessors", "getRuntime",
    "currentTimeMillis", "println", "printf", "print", "printStackTrace",
    "setTags", "setMessage", "setStartPos", "notComplexPhrase", "disableRule",
    "enableRule", "disableAllRulesExcept", "check", "match", "synthesize",
    "tokenize", "tag", "createNullToken", "disambiguate", "loadWords",
    "loadConfusionPairs", "loadPatternRules", "validateWithXmlSchema",
    "validateUniqueness", "warnIfRegexpSyntaxNotKosher",
    "cleanMarkersInExample", "newInstance", "newSAXParser",
    "newFixedThreadPool", "withInitial", "parse", "parseInt", "compile",
    "matcher", "find", "group", "chars", "count", "asList", "singletonList",
    "emptyList", "of", "ofNullable", "isPresent", "isDefaultOff",
    "isDefaultTempOff", "isVariant", "isMisspelled", "isInsideMarker",
    "isSentenceStart", "isUnified", "isUnificationNeutral", "isPostagRegexp",
    "isWithComplexPhrase", "isLetter", "isDigit", "charAt", "read",
    "resourceExists", "ruleFileExists", "toLowerCase", "mergeCompound",
    "toXML", "hasNext", "next", "iterator", "supportsLanguage", "verify",
    "getDayOfWeek", "getMonth", "printWarning", "cleanXML", "sortForms",
    "disableSpellingRules", "enableOnlyOneRule", "findLargestReference",
    "rangeIsOverlapping", "createToolForTesting", "isWord",
    "append", "toShortString", "comparingInt", "format", "valueOf", "hashCode",
    "sleep", "wait",
    "notify", "notifyAll", "run", "call", "apply", "accept", "test",
    "forEach", "map", "toArray", "createLanguage", "createSampleText",
    "createPatternRuleErrorCollector", "failTest",
    "assertIdUniqueness", "assertIdValidity", "assertIdAndDescriptionValidity",
    "testExamples", "testCorrectSentences", "testIncorrectExamples",
    "testCorrectExamples", "testBadSentences", "testErrorTriggeringSentences",
    "assertSuggestions", "assertSuggestionsDoNotCreateErrors",
    "warnIfShortMessageLongerThanErrorMessage", "skipCountryVariant",
    "validateRuleFile", "disambiguateUntil", "setUp", "validateWords",
    "getDayOfWeekStr", "getMonthStr", "setLevel", "flush", "close",
    "getHistoricalAnnotations", "setHistoricalAnnotations", "toSortedString",
    "getAnnotations", "getSubstring", "setChunkTags", "getChunkTags",
    "preDisambiguate",
    "getEndPos",
    "getStartPos",
})

CONTROL_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "synchronized", "try", "return",
    "new", "else", "do", "throw", "assert", "super", "this", "case", "instanceof",
})

_LITERAL_COLLECTION_FACTORIES = ("ImmutableSet.of", "ImmutableList.of",
                                 "Arrays.asList", "Set.of", "List.of")


@dataclass(frozen=True)
class Candidate:
    """One parenthesis-depth-0 invocation inside a method body."""

    qualifier: str
    name: str
    line: int
    kind: str  # ASSERTION | DELEGATION | SETUP
    target: str = ""  # DeclaringClass#method for DELEGATION


@dataclass
class JavaMethod:
    name: str
    param_count: int
    annotations: Tuple[str, ...]
    signature: str
    line: int
    body: str
    is_test: bool
    is_ignored: bool
    ignore_reason: str
    is_override: bool
    is_abstract: bool
    assertion_units: int = 0
    scenario_units: int = 0
    candidates: List[Candidate] = field(default_factory=list)
    delegates_to: Tuple[str, ...] = ()
    vector_loops: Tuple[Tuple[str, int, int], ...] = ()
    throw_guards: int = 0

    @property
    def key(self) -> str:
        return f"{self.name}/{self.param_count}"


@dataclass
class JavaTestFile:
    rel_path: str
    package: str
    class_name: str
    extends: Optional[str]
    size_bytes: int
    sha256: str
    methods: List[JavaMethod]
    vectors: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def fq_class(self) -> str:
        return f"{self.package}.{self.class_name}" if self.package else self.class_name

    def method(self, name: str, arity: Optional[int] = None) -> Optional[JavaMethod]:
        named = [m for m in self.methods if m.name == name]
        if not named:
            return None
        if arity is not None:
            for m in named:
                if m.param_count == arity:
                    return m
            for m in named:  # varargs collapse several call arities into one
                if m.signature.count("...") and arity >= m.param_count - 1:
                    return m
        return named[0]


# --- lexical preprocessing --------------------------------------------------

def blank_comments(src: str) -> str:
    """Replace comment characters with spaces, preserving offsets and newlines."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                if src[i] == "\n" and quote == '"':
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            if end == -1:
                raise JavaParseError("unterminated block comment")
            end += 2
            for j in range(i, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def blank_literals(src: str) -> str:
    """Blank the *contents* of string/char literals, preserving offsets."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    out[i] = " "
                    if i + 1 < n:
                        out[i + 1] = " "
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def match_brace(struct: str, open_idx: int) -> int:
    """Return the index of the closing brace matching the one at ``open_idx``."""
    if struct[open_idx] != "{":
        raise JavaParseError(f"expected an opening brace at offset {open_idx}")
    depth = 0
    for i in range(open_idx, len(struct)):
        if struct[i] == "{":
            depth += 1
        elif struct[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise JavaParseError("unbalanced braces")


# --- declaration scanning ---------------------------------------------------

_ANNOTATION_RE = re.compile(r"@(\w+)(\s*\([^)]*\))?")
_METHOD_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{}()]*)\)\s*"
    r"(?:throws\s+[\w.,\s]+?)?\s*(?P<end>[{;])"
)
_FIELD_RE = re.compile(
    r"(?:private|protected|public|static|final|volatile|transient)"
    r"[\w.<>\[\],\s?]*\s(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<init>[^;]+);"
)


def _count_params(params: str) -> int:
    """Declared parameter count of a Java method signature fragment."""
    params = params.strip()
    if not params:
        return 0
    depth = 0
    count = 1
    for ch in params:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def _brace_depths(struct: str) -> List[int]:
    """Brace depth *before* the character at each index."""
    depths = [0] * (len(struct) + 1)
    d = 0
    for i, ch in enumerate(struct):
        depths[i] = d
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
    depths[len(struct)] = d
    return depths


def parse_java_file(path: Path, rel_path: str, sha256: str) -> JavaTestFile:
    raw = path.read_bytes()
    src = raw.decode("utf-8")
    code = blank_comments(src)
    struct = blank_literals(code)

    pkg_m = re.search(r"^\s*package\s+([\w.]+)\s*;", struct, re.MULTILINE)
    package = pkg_m.group(1) if pkg_m else ""

    cls_m = re.search(
        r"\b(?:public\s+|final\s+|abstract\s+)*class\s+(\w+)"
        r"(?:\s+extends\s+([\w.<>]+))?",
        struct,
    )
    if not cls_m:
        raise JavaParseError(f"{rel_path}: no top-level class declaration found")
    class_name, extends = cls_m.group(1), cls_m.group(2)

    class_open = struct.index("{", cls_m.end() - 1)
    class_close = match_brace(struct, class_open)
    depths = _brace_depths(struct)

    methods: List[JavaMethod] = []
    for m in _METHOD_RE.finditer(struct, class_open, class_close):
        if depths[m.start()] != 1:
            continue  # inner class / nested scope
        name = m.group("name")
        if name in CONTROL_KEYWORDS:
            continue
        prev = max(
            struct.rfind(";", class_open, m.start()),
            struct.rfind("{", class_open, m.start()),
            struct.rfind("}", class_open, m.start()),
        )
        head = code[prev + 1:m.start()]
        head_struct = struct[prev + 1:m.start()]
        annotations = tuple(a.group(0).strip() for a in _ANNOTATION_RE.finditer(head))
        without_annotations = _ANNOTATION_RE.sub(" ", head_struct).strip()
        if not without_annotations:
            continue  # bare invocation, not a declaration
        is_abstract = bool(re.search(r"\babstract\b", without_annotations))
        if m.group("end") == ";":
            if not is_abstract:
                continue  # not a method declaration
            body = ""
        else:
            open_idx = m.end() - 1
            close_idx = match_brace(struct, open_idx)
            body = code[open_idx + 1:close_idx]
        ann_names = {a.split("(")[0] for a in annotations}
        ignore_reason = ""
        for a in annotations:
            if a.startswith("@Ignore"):
                lit = re.search(r'"([^"]*)"', a)
                ignore_reason = lit.group(1) if lit else "(no reason given)"
        methods.append(
            JavaMethod(
                name=name,
                param_count=_count_params(m.group("params")),
                annotations=annotations,
                signature=" ".join(
                    f"{without_annotations} {name}({m.group('params').strip()})".split()
                ),
                line=_line_of(src, m.start()),
                body=body,
                is_test="@Test" in ann_names,
                is_ignored="@Ignore" in ann_names,
                ignore_reason=ignore_reason,
                is_override="@Override" in ann_names,
                is_abstract=is_abstract,
            )
        )

    parsed = JavaTestFile(
        rel_path=rel_path,
        package=package,
        class_name=class_name,
        extends=extends.split("<")[0] if extends else None,
        size_bytes=len(raw),
        sha256=sha256,
        methods=methods,
    )
    parsed.vectors = _collect_literal_vectors(code, struct, rel_path)
    return parsed


def _collect_literal_vectors(code: str, struct: str, rel_path: str) -> Dict[str, List[str]]:
    """Map field name -> unique string literal elements of its initializer.

    Field spans are located on the structural view (literal contents blanked)
    so a ``;`` inside a string literal cannot truncate an initializer, and the
    elements are then read back from the comment-stripped source.
    """
    vectors: Dict[str, List[str]] = {}
    for m in _FIELD_RE.finditer(struct):
        init_struct = " ".join(m.group("init").split())
        if not any(init_struct.startswith(f) for f in _LITERAL_COLLECTION_FACTORIES):
            continue
        init = code[m.start("init"):m.end("init")]
        inner = init[init.index("(") + 1:init.rindex(")")]
        literals = re.findall(r'"((?:[^"\\]|\\.)*)"', inner)
        residue = re.sub(r'"(?:[^"\\]|\\.)*"', "", inner).replace(",", "").strip()
        if residue:
            raise JavaParseError(
                f"{rel_path}: field {m.group('name')!r} has non-literal elements: {residue!r}"
            )
        unique: List[str] = []
        for lit in literals:
            if lit not in unique:
                unique.append(lit)
        vectors[m.group("name")] = unique
    return vectors


# --- scenario/assertion counting -------------------------------------------

_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_FOREACH_RE = re.compile(
    r"\bfor\s*\(\s*(?:final\s+)?[\w.<>\[\],\s?]+?\s+\w+\s*:\s*(?P<vector>[A-Za-z_]\w*)\s*\)\s*\{"
)


class MethodResolver:
    """Resolves a simple/qualified call to a declaring vendored test class."""

    def __init__(self, files: Dict[str, JavaTestFile]) -> None:
        # fq class name -> parsed file
        self._by_fq = {f.fq_class: f for f in files.values()}
        self._by_simple: Dict[str, JavaTestFile] = {}
        for f in files.values():
            self._by_simple.setdefault(f.class_name, f)

    def chain(self, parsed: JavaTestFile) -> List[JavaTestFile]:
        out, seen, cur = [], set(), parsed
        while cur is not None and cur.class_name not in seen:
            out.append(cur)
            seen.add(cur.class_name)
            cur = self._by_simple.get(cur.extends) if cur.extends else None
        return out

    def resolve(
        self, parsed: JavaTestFile, qualifier: str, name: str, arity: Optional[int] = None
    ) -> Optional[JavaMethod]:
        if not qualifier:
            for cls in self.chain(parsed):
                found = cls.method(name, arity)
                if found is not None:
                    return found
            return None
        target = self._by_simple.get(qualifier.split(".")[-1])
        if target is not None:
            return target.method(name, arity)
        return None

    def declaring_class(self, parsed: JavaTestFile, qualifier: str, name: str) -> Optional[JavaTestFile]:
        if not qualifier:
            for cls in self.chain(parsed):
                if cls.method(name) is not None:
                    return cls
            return None
        return self._by_simple.get(qualifier.split(".")[-1])

    def inherited_test_methods(self, parsed: JavaTestFile) -> List[Tuple[str, "JavaMethod"]]:
        """@Test methods inherited (and not overridden) from vendored superclasses."""
        chain = self.chain(parsed)
        own = {m.name for m in parsed.methods}
        out: List[Tuple[str, JavaMethod]] = []
        for cls in chain[1:]:
            for m in cls.methods:
                if m.is_test and m.name not in own:
                    own.add(m.name)
                    out.append((cls.fq_class, m))
        return out


def _qualifier_before(struct: str, idx: int) -> str:
    """Return the receiver expression immediately before the identifier at ``idx``."""
    j = idx - 1
    while j >= 0 and struct[j] in " \t\n\r":
        j -= 1
    if j < 0 or struct[j] != ".":
        return ""
    j -= 1
    while j >= 0 and struct[j] in " \t\n\r":
        j -= 1
    if j >= 0 and struct[j] == ")":
        depth = 0
        while j >= 0:
            if struct[j] == ")":
                depth += 1
            elif struct[j] == "(":
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        j -= 1
        while j >= 0 and struct[j] in " \t\n\r":
            j -= 1
    end = j + 1
    while j >= 0 and (struct[j].isalnum() or struct[j] in "_."):
        j -= 1
    return struct[j + 1:end]


def _call_arity(struct: str, open_idx: int) -> int:
    """Number of top-level arguments of the call whose ``(`` sits at ``open_idx``."""
    depth = 0
    args = 0
    seen = False
    for i in range(open_idx, len(struct)):
        ch = struct[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return args + (1 if seen else 0)
        elif ch == "," and depth == 1:
            args += 1
        elif not ch.isspace() and depth == 1:
            seen = True
    raise JavaParseError("unbalanced parentheses in call argument list")


def _preceded_by_new(struct: str, idx: int) -> bool:
    j = idx - 1
    while j >= 0 and struct[j] in " \t\n\r":
        j -= 1
    return struct[max(0, j - 2):j + 1] == "new"


def _scan_candidates(
    parsed: JavaTestFile,
    resolver: MethodResolver,
    region: str,
    base_line: int,
    line_offset: int,
) -> List[Candidate]:
    struct = blank_literals(region)
    out: List[Candidate] = []
    paren = 0
    i, n = 0, len(struct)
    while i < n:
        ch = struct[i]
        if ch == "(":
            paren += 1
            i += 1
            continue
        if ch == ")":
            paren -= 1
            i += 1
            continue
        m = _IDENT_RE.match(struct, i)
        if not m:
            i += 1
            continue
        name = m.group(0)
        j = m.end()
        while j < n and struct[j] in " \t\n\r":
            j += 1
        if j < n and struct[j] == "(" and paren == 0 and name not in CONTROL_KEYWORDS:
            if not _preceded_by_new(struct, i):
                qualifier = _qualifier_before(struct, i)
                line = base_line + line_offset + region.count("\n", 0, i)
                arity = _call_arity(struct, j)
                if name in ASSERTION_CALLS and qualifier in ("", "Assert", "MatcherAssert",
                                                             "org.junit.Assert", "TestCase"):
                    out.append(Candidate(qualifier, name, line, "ASSERTION"))
                else:
                    target = resolver.resolve(parsed, qualifier, name, arity)
                    owner = resolver.declaring_class(parsed, qualifier, name)
                    if target is not None and not target.is_abstract:
                        out.append(Candidate(qualifier, name, line, "DELEGATION",
                                             f"{owner.fq_class}#{target.key}"))
                    elif target is not None and target.is_abstract:
                        # Abstract fixture hook implemented by the concrete test
                        # class: it supplies data, it asserts nothing.
                        out.append(Candidate(qualifier, name, line, "SETUP"))
                    elif name in SETUP_CALLS or name in ASSERTION_CALLS:
                        out.append(Candidate(qualifier, name, line, "SETUP"))
                    else:
                        raise JavaParseError(
                            f"{parsed.rel_path}: unclassified depth-0 invocation "
                            f"{qualifier + '.' if qualifier else ''}{name}() at line {line} - "
                            "extend the counting vocabulary rather than undercounting"
                        )
        i = m.end()
    return out


_THROW_RE = re.compile(r"\bthrow\s+new\s+\w+")


def _count_throw_guards(region: str) -> int:
    """Count ``throw new X(...)`` fail-closed guards (JUnit-free assertions)."""
    return len(_THROW_RE.findall(blank_literals(region)))


def analyze_method(parsed: JavaTestFile, method: JavaMethod, resolver: MethodResolver) -> None:
    """Compute assertion/scenario units for one method, fail-closed."""
    body = method.body
    struct = blank_literals(body)
    vectors: Dict[str, List[str]] = {}
    for cls in resolver.chain(parsed):
        for k, v in cls.vectors.items():
            vectors.setdefault(k, v)

    working = list(body)
    vector_loops: List[Tuple[str, int, int]] = []
    total_scenarios = 0
    total_assertions = 0
    candidates: List[Candidate] = []

    for m in _FOREACH_RE.finditer(struct):
        vec = m.group("vector")
        if vec not in vectors:
            continue  # not a static test vector; body is scanned inline below
        open_idx = m.end() - 1
        close_idx = match_brace(struct, open_idx)
        loop_body = body[open_idx + 1:close_idx]
        inner = _scan_candidates(
            parsed, resolver, loop_body, method.line,
            body.count("\n", 0, open_idx + 1),
        )
        inner_units = sum(1 for c in inner if c.kind in ("ASSERTION", "DELEGATION"))
        if inner_units == 0:
            raise JavaParseError(
                f"{parsed.rel_path}: vector loop over {vec!r} in {method.name} has no "
                "assertion or delegation - refusing to record a zero-scenario vector"
            )
        elements = len(vectors[vec])
        vector_loops.append((vec, elements, inner_units))
        total_scenarios += elements * inner_units
        total_assertions += elements * sum(1 for c in inner if c.kind == "ASSERTION")
        candidates.extend(inner)
        for k in range(m.start(), close_idx + 1):
            if working[k] != "\n":
                working[k] = " "

    flat = _scan_candidates(parsed, resolver, "".join(working), method.line, 0)
    candidates.extend(flat)
    total_scenarios += sum(1 for c in flat if c.kind in ("ASSERTION", "DELEGATION"))
    total_assertions += sum(1 for c in flat if c.kind == "ASSERTION")

    guards = _count_throw_guards("".join(working))
    method.throw_guards = guards
    total_assertions += guards
    total_scenarios += guards

    method.assertion_units = total_assertions
    method.scenario_units = total_scenarios
    method.candidates = sorted(candidates, key=lambda c: (c.line, c.name))
    method.delegates_to = tuple(sorted({c.target for c in candidates if c.kind == "DELEGATION"}))
    method.vector_loops = tuple(vector_loops)
