"""Fetch the Task-0014 Stratum-D natural Russian development corpus.

Development only.  The corpus is written under the git-ignored ``corpora/`` directory
and is never committed; only its provenance, byte size, SHA-256 and block counts are
recorded in ``compat/differential_corpus_0014_manifest.json``.

Two sources are used so the stratum covers more than one domain:

* Russian Wikipedia (``ru.wikipedia.org``) — encyclopedic prose, CC BY-SA 4.0.
* Russian Wikisource (``ru.wikisource.org``) — literary prose, CC BY-SA 4.0 for the
  wiki layer; the underlying works are public domain.

Selection is deterministic in both cases:

* Wikipedia — a fixed-seed PRNG draws two-letter Cyrillic start points from a fixed
  alphabet and each start point walks namespace 0 with ``generator=allpages``.
* Wikisource — a fixed, sorted list of prose categories is walked with
  ``list=categorymembers``.  Wikisource articles are transclusions from the ``Page:``
  namespace, which the ``extracts`` API does not resolve, so their plain text comes
  from ``action=parse`` and the rendered ``<p>`` elements.

The retrieved page-id lists are recorded verbatim in the metadata file, so a run is
reproducible from its own record even as the wikis change.

Preprocessing is deliberately minimal: paragraph-sized blocks are accepted or rejected
whole.  Nothing is spell-corrected, case-folded, re-punctuated, ё/е-normalised or
whitespace-normalised.  The only text transformation is the markup-to-plain-text
extraction needed to obtain plain text at all.

Usage::

    python -m tools.fetch_natural_corpus_0014 --wikipedia-target 1600 --wikisource-target 800
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPORA_DIR = REPO_ROOT / "corpora"

#: Committed fixed seed for the whole Task-0014 corpus.
FIXED_SEED = 140014

USER_AGENT = (
    "pylat-ru-differential-corpus/0014 (development differential testing; "
    "https://github.com/bojlahg/pylat_ru)"
)

#: Heading lines in the plain-text extract projection, e.g. ``== История ==``.
HEADING_PATTERN = re.compile(r"^\s*={2,}.*={2,}\s*$")
CYRILLIC_PATTERN = re.compile(r"[Ѐ-ӿ]")

MIN_BLOCK_CHARS = 80
MAX_BLOCK_CHARS = 3000
MIN_CYRILLIC_RATIO = 0.5
MAX_BLOCKS_PER_PAGE = 6

#: Alphabet the deterministic Wikipedia ``allpages`` start points are drawn from.
START_ALPHABET = "абвгдежзиклмнопрстуфхцчшэюя"

#: Fixed, sorted Wikisource prose categories walked in order.
WIKISOURCE_CATEGORIES: tuple[str, ...] = (
    "Категория:Повести",
    "Категория:Проза",
    "Категория:Рассказы",
    "Категория:Романы",
)


@dataclass(frozen=True)
class SourceSpec:
    """One MediaWiki source of natural Russian text."""

    source_id: str
    api_url: str
    site: str
    license_name: str
    license_url: str
    filename: str
    strategy: str


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="ru_wikipedia",
        api_url="https://ru.wikipedia.org/w/api.php",
        site="ru.wikipedia.org",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        filename="natural_ru_wikipedia_0014.jsonl",
        strategy="allpages_textextracts",
    ),
    SourceSpec(
        source_id="ru_wikisource",
        api_url="https://ru.wikisource.org/w/api.php",
        site="ru.wikisource.org",
        license_name="CC BY-SA 4.0 (wiki layer); underlying works public domain",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        filename="natural_ru_wikisource_0014.jsonl",
        strategy="categorymembers_parse",
    ),
)


def _api_get(api_url: str, params: Dict[str, str], retries: int = 4) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{api_url}?{query}", headers={"User-Agent": USER_AGENT}
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(
        f"MediaWiki API request failed after {retries} attempts: {last_error}"
    )


# --------------------------------------------------------------------------
# Block acceptance
# --------------------------------------------------------------------------


def _accept_block(block: str) -> bool:
    """Whole-block accept/reject decision.  Block text is never edited."""
    if not block.strip():
        return False
    if HEADING_PATTERN.match(block):
        return False
    if len(block) < MIN_BLOCK_CHARS or len(block) > MAX_BLOCK_CHARS:
        return False
    letters = [c for c in block if c.isalpha()]
    if not letters:
        return False
    cyrillic = sum(1 for c in letters if CYRILLIC_PATTERN.match(c))
    return cyrillic / len(letters) >= MIN_CYRILLIC_RATIO


def _blocks_from_extract(extract: str) -> List[str]:
    """Blocks from a TextExtracts plain-text projection, split on blank lines."""
    blocks: List[str] = []
    for raw_block in extract.split("\n\n"):
        block = raw_block.strip("\n")
        if _accept_block(block):
            blocks.append(block)
            if len(blocks) >= MAX_BLOCKS_PER_PAGE:
                break
    return blocks


_TAG_PATTERN = re.compile(r"<[^>]+>")
_SUP_PATTERN = re.compile(r"<sup\b.*?</sup>", re.S)
_PARAGRAPH_PATTERN = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S)


def _blocks_from_html(rendered: str) -> List[str]:
    """Blocks from rendered wiki HTML: one block per ``<p>`` element.

    Reference superscripts are dropped because they are markup artefacts, not part of
    the prose.  Remaining tags are removed and entities decoded; no other edits occur.
    """
    blocks: List[str] = []
    for match in _PARAGRAPH_PATTERN.finditer(rendered):
        fragment = _SUP_PATTERN.sub("", match.group(1))
        text = html.unescape(_TAG_PATTERN.sub("", fragment)).strip()
        if _accept_block(text):
            blocks.append(text)
            if len(blocks) >= MAX_BLOCKS_PER_PAGE:
                break
    return blocks


# --------------------------------------------------------------------------
# Wikipedia: deterministic allpages walk + TextExtracts
# --------------------------------------------------------------------------


def _start_points(seed: int, source_id: str) -> Iterator[str]:
    """Yield deterministic alphabetical start points for the ``allpages`` walk."""
    rng = random.Random(f"{seed}:{source_id}")
    seen: set[str] = set()
    while True:
        point = rng.choice(START_ALPHABET) + rng.choice(START_ALPHABET)
        if point in seen:
            continue
        seen.add(point)
        yield point.capitalize()


def _walk_allpages(spec: SourceSpec, seed: int) -> Iterator[tuple[str, Dict[str, Any]]]:
    """Yield ``(start_point, page)`` with a full plain-text extract per page.

    ``TextExtracts`` only serialises one full extract per request, so the ``excontinue``
    token is exhausted for each generator window before ``gapcontinue`` advances it.
    """
    for start_point in _start_points(seed, spec.source_id):
        gap_continue: str | None = None
        while True:
            ex_continue: str | None = None
            next_gap: str | None = None
            while True:
                params = {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "generator": "allpages",
                    "gapnamespace": "0",
                    "gapfilterredir": "nonredirects",
                    "gaplimit": "20",
                    "gapfrom": start_point,
                    "prop": "extracts",
                    "explaintext": "1",
                    "exsectionformat": "plain",
                }
                if gap_continue:
                    params["gapcontinue"] = gap_continue
                if ex_continue:
                    params["excontinue"] = str(ex_continue)
                payload = _api_get(spec.api_url, params)
                pages = payload.get("query", {}).get("pages", [])
                if not pages:
                    return
                for page in pages:
                    if page.get("extract"):
                        yield start_point, page
                continuation = payload.get("continue", {})
                next_gap = continuation.get("gapcontinue", next_gap)
                ex_continue = continuation.get("excontinue")
                if not ex_continue:
                    break
            if not next_gap:
                break
            gap_continue = next_gap


# --------------------------------------------------------------------------
# Wikisource: deterministic category walk + rendered-HTML paragraphs
# --------------------------------------------------------------------------


def _walk_category_pages(spec: SourceSpec) -> Iterator[tuple[str, Dict[str, Any]]]:
    """Yield ``(category, page)`` for every member of the fixed prose categories."""
    for category in WIKISOURCE_CATEGORIES:
        cm_continue: str | None = None
        while True:
            params = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "list": "categorymembers",
                "cmtitle": category,
                "cmnamespace": "0",
                "cmlimit": "500",
                "cmsort": "sortkey",
            }
            if cm_continue:
                params["cmcontinue"] = cm_continue
            payload = _api_get(spec.api_url, params)
            members = payload.get("query", {}).get("categorymembers", [])
            if not members:
                break
            for member in members:
                yield category, member
            cm_continue = payload.get("continue", {}).get("cmcontinue")
            if not cm_continue:
                break


def _render_page(spec: SourceSpec, title: str) -> str:
    payload = _api_get(
        spec.api_url,
        {
            "action": "parse",
            "format": "json",
            "formatversion": "2",
            "page": title,
            "prop": "text",
            "disablelimitreport": "1",
            "disableeditsection": "1",
        },
    )
    return payload.get("parse", {}).get("text", "") or ""


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def fetch_source(spec: SourceSpec, target_blocks: int, seed: int) -> Dict[str, Any]:
    """Fetch at least ``target_blocks`` accepted blocks from one source."""
    CORPORA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CORPORA_DIR / spec.filename

    retrieved_page_ids: List[int] = []
    selection_points: List[str] = []
    visited_pages = 0
    raw_block_count = 0
    seen_texts: set[str] = set()
    records: List[Dict[str, Any]] = []

    def note(point: str) -> None:
        if point not in selection_points:
            selection_points.append(point)
        if visited_pages % 25 == 0:
            print(
                f"  {spec.source_id}: {len(records)}/{target_blocks} blocks "
                f"from {len(retrieved_page_ids)} of {visited_pages} pages "
                f"({point})",
                file=sys.stderr,
                flush=True,
            )

    def absorb(page_id: int, title: str, blocks: Sequence[str]) -> None:
        nonlocal raw_block_count
        raw_block_count += len(blocks)
        if not blocks:
            return
        retrieved_page_ids.append(page_id)
        for index, block in enumerate(blocks):
            if block in seen_texts:
                continue
            seen_texts.add(block)
            records.append(
                {
                    "source_id": spec.source_id,
                    "page_id": page_id,
                    "page_title": title,
                    "block_index": index,
                    "text": block,
                }
            )

    if spec.strategy == "allpages_textextracts":
        for start_point, page in _walk_allpages(spec, seed):
            if len(records) >= target_blocks:
                break
            visited_pages += 1
            note(start_point)
            absorb(
                int(page["pageid"]),
                page.get("title", ""),
                _blocks_from_extract(page["extract"]),
            )
    elif spec.strategy == "categorymembers_parse":
        for category, member in _walk_category_pages(spec):
            if len(records) >= target_blocks:
                break
            visited_pages += 1
            note(category)
            rendered = _render_page(spec, member["title"])
            if not rendered:
                continue
            absorb(int(member["pageid"]), member["title"], _blocks_from_html(rendered))
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unknown strategy: {spec.strategy}")

    records.sort(key=lambda r: (r["page_id"], r["block_index"]))
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    raw = out_path.read_bytes()
    selection_method = (
        (
            "deterministic seeded PRNG draws two-letter Cyrillic start points; each "
            "start point walks namespace 0 with generator=allpages; plain text from "
            "prop=extracts explaintext=1"
        )
        if spec.strategy == "allpages_textextracts"
        else (
            "fixed sorted prose categories walked with list=categorymembers "
            "(cmsort=sortkey); plain text from action=parse rendered <p> elements, "
            "because Wikisource articles are transclusions the extracts API does not "
            "resolve"
        )
    )

    return {
        "source_id": spec.source_id,
        "site": spec.site,
        "api_url": spec.api_url,
        "license": spec.license_name,
        "license_url": spec.license_url,
        "retrieval_date": _datetime.datetime.now(_datetime.timezone.utc)
        .date()
        .isoformat(),
        "strategy": spec.strategy,
        "selection_method": selection_method,
        "selection_seed": seed if spec.strategy == "allpages_textextracts" else None,
        "start_alphabet": (
            START_ALPHABET if spec.strategy == "allpages_textextracts" else None
        ),
        "categories": (
            list(WIKISOURCE_CATEGORIES)
            if spec.strategy == "categorymembers_parse"
            else None
        ),
        "selection_points": selection_points,
        "visited_pages": visited_pages,
        "pages_contributing_blocks": len(retrieved_page_ids),
        "page_ids": retrieved_page_ids,
        "local_file": str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_block_count": raw_block_count,
        "retained_block_count": len(records),
        "preprocessing": {
            "block_unit": (
                "blank-line separated block of the plain-text extract"
                if spec.strategy == "allpages_textextracts"
                else "one rendered <p> element"
            ),
            "markup_removal": (
                "none; the API returns plain text"
                if spec.strategy == "allpages_textextracts"
                else "<sup> reference markers dropped, remaining tags removed, "
                "HTML entities decoded"
            ),
            "rejected_headings": "lines matching ^ *={2,}.*={2,} *$",
            "min_block_chars": MIN_BLOCK_CHARS,
            "max_block_chars": MAX_BLOCK_CHARS,
            "min_cyrillic_letter_ratio": MIN_CYRILLIC_RATIO,
            "max_blocks_per_page": MAX_BLOCKS_PER_PAGE,
            "deduplication": "exact duplicate block text removed within the source",
            "text_edits": (
                "none; blocks are accepted or rejected verbatim. No spelling, case, "
                "punctuation, typography, ё/е or whitespace normalisation is applied."
            ),
        },
    }


def load_natural_corpus() -> List[Dict[str, Any]]:
    """Load every retained natural block from the local git-ignored corpus files."""
    blocks: List[Dict[str, Any]] = []
    for spec in SOURCES:
        path = CORPORA_DIR / spec.filename
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                blocks.append(json.loads(line))
    return blocks


def metadata_path() -> Path:
    return CORPORA_DIR / "natural_ru_0014_metadata.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wikipedia-target", type=int, default=1600)
    parser.add_argument("--wikisource-target", type=int, default=800)
    parser.add_argument("--seed", type=int, default=FIXED_SEED)
    parser.add_argument("--only", choices=[s.source_id for s in SOURCES])
    args = parser.parse_args(argv)

    targets = {
        "ru_wikipedia": args.wikipedia_target,
        "ru_wikisource": args.wikisource_target,
    }

    fetched: Dict[str, Dict[str, Any]] = {}
    for spec in SOURCES:
        if args.only and spec.source_id != args.only:
            continue
        print(f"Fetching {spec.source_id} ...", file=sys.stderr, flush=True)
        fetched[spec.source_id] = fetch_source(spec, targets[spec.source_id], args.seed)

    # Re-read the metadata only now, so a concurrent single-source run that finished
    # while this one was fetching is merged rather than discarded.
    existing: Dict[str, Dict[str, Any]] = {}
    if metadata_path().is_file():
        for record in json.loads(metadata_path().read_text(encoding="utf-8")).get(
            "sources", []
        ):
            existing[record["source_id"]] = record
    existing.update(fetched)

    sources = [existing[spec.source_id] for spec in SOURCES if spec.source_id in existing]
    unique_texts = {
        block["text"] for block in load_natural_corpus() if block["text"].strip()
    }
    metadata = {
        "schema_version": "1.0.0",
        "task": "0014",
        "fixed_seed": args.seed,
        "sources": sources,
        "total_retained_blocks": sum(s["retained_block_count"] for s in sources),
        "total_unique_nonempty_blocks": len(unique_texts),
    }
    metadata_path().write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Retained {metadata['total_retained_blocks']} blocks "
        f"({metadata['total_unique_nonempty_blocks']} unique non-empty) -> "
        f"{metadata_path().relative_to(REPO_ROOT)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
