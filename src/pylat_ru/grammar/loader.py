"""src/pylat_ru/grammar/loader.py

Fail-closed XML parser and loader for LanguageTool Russian grammar.xml.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union
import xml.etree.ElementTree as ET

from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.errors import GrammarFormatError, GrammarResourceError
from pylat_ru.grammar.model import (
    Example,
    GrammarRule,
    MatchReference,
    MessageTemplate,
    Pattern,
    PatternToken,
    PatternTokenException,
    SuggestionTemplate,
)


def _get_default_grammar_path() -> Path:
    """Resolve packaged grammar.xml resource path."""
    try:
        traversable = importlib.resources.files("pylat_ru.resources.rules.ru").joinpath("grammar.xml")
        with importlib.resources.as_file(traversable) as path:
            return Path(path)
    except Exception as e:
        # Fallback to direct path
        p = Path(__file__).resolve().parent.parent / "resources" / "rules" / "ru" / "grammar.xml"
        if p.is_file():
            return p
        raise GrammarResourceError(f"Cannot locate default grammar.xml resource: {e}") from e


class GrammarLoader:
    """Loader and parser for Russian grammar.xml rule definitions."""

    def __init__(self) -> None:
        pass

    def load_default(self) -> List[GrammarRule]:
        """Load and parse default packaged Russian grammar.xml."""
        path = _get_default_grammar_path()
        return self.load_from_file(path)

    def load_from_file(self, path: Union[str, Path]) -> List[GrammarRule]:
        """Load and parse grammar rules from a file path."""
        p = Path(path)
        if not p.is_file():
            raise GrammarResourceError(f"Grammar file not found: {p}")
        try:
            tree = ET.parse(str(p))
            return self._parse_tree(tree)
        except ET.ParseError as e:
            raise GrammarFormatError(f"XML parse error in {p}: {e}") from e

    def load_from_string(self, xml_str: str) -> List[GrammarRule]:
        """Load and parse grammar rules from an XML string."""
        try:
            root = ET.fromstring(xml_str)
            tree = ET.ElementTree(root)
            return self._parse_tree(tree)
        except ET.ParseError as e:
            raise GrammarFormatError(f"XML parse error: {e}") from e

    def _parse_tree(self, tree: ET.ElementTree) -> List[GrammarRule]:
        root = tree.getroot()
        if root.tag != "rules":
            raise GrammarFormatError(f"Expected root tag <rules>, found <{root.tag}>")

        rules: List[GrammarRule] = []
        source_order_idx = 0

        for cat_elem in root.findall("category"):
            cat_id = cat_elem.attrib.get("id", "")
            cat_name = cat_elem.attrib.get("name", cat_id)
            cat_default = cat_elem.attrib.get("default", "on")
            cat_tags = [t.strip() for t in cat_elem.attrib.get("tags", "").split() if t.strip()]

            for child in cat_elem:
                if child.tag == "rulegroup":
                    group_id = child.attrib.get("id", "")
                    group_name = child.attrib.get("name", group_id)
                    group_default = child.attrib.get("default", cat_default)
                    group_tags_str = child.attrib.get("tags")
                    group_tags = (
                        [t.strip() for t in group_tags_str.split() if t.strip()]
                        if group_tags_str
                        else cat_tags
                    )
                    group_url = child.findtext("url")

                    rule_num = 0
                    for r in child.findall("rule"):
                        rule_num += 1
                        r_id = r.attrib.get("id")
                        sub_id = r_id if r_id else str(rule_num)
                        full_id = f"{group_id}[{sub_id}]"
                        r_name = r.attrib.get("name", group_name)
                        r_default = r.attrib.get("default", group_default)
                        is_default_off = (r_default == "off")

                        r_tags_str = r.attrib.get("tags")
                        r_tags = (
                            [t.strip() for t in r_tags_str.split() if t.strip()]
                            if r_tags_str
                            else group_tags
                        )

                        rule_obj = self._parse_rule_elem(
                            rule_elem=r,
                            rule_id=r_id or group_id,
                            sub_id=sub_id,
                            full_id=full_id,
                            name=r_name,
                            category_id=cat_id,
                            category_name=cat_name,
                            rulegroup_id=group_id,
                            rulegroup_name=group_name,
                            default_off=is_default_off,
                            tags=r_tags,
                            source_order_idx=source_order_idx,
                            inherited_url=group_url,
                        )
                        rules.append(rule_obj)
                        source_order_idx += 1

                elif child.tag == "rule":
                    r_id = child.attrib.get("id", "")
                    full_id = r_id
                    r_name = child.attrib.get("name", r_id)
                    r_default = child.attrib.get("default", cat_default)
                    is_default_off = (r_default == "off")

                    r_tags_str = child.attrib.get("tags")
                    r_tags = (
                        [t.strip() for t in r_tags_str.split() if t.strip()]
                        if r_tags_str
                        else cat_tags
                    )

                    rule_obj = self._parse_rule_elem(
                        rule_elem=child,
                        rule_id=r_id,
                        sub_id=None,
                        full_id=full_id,
                        name=r_name,
                        category_id=cat_id,
                        category_name=cat_name,
                        rulegroup_id=None,
                        rulegroup_name=None,
                        default_off=is_default_off,
                        tags=r_tags,
                        source_order_idx=source_order_idx,
                        inherited_url=None,
                    )
                    rules.append(rule_obj)
                    source_order_idx += 1

        return rules

    def _parse_rule_elem(
        self,
        rule_elem: ET.Element,
        rule_id: str,
        sub_id: Optional[str],
        full_id: str,
        name: str,
        category_id: str,
        category_name: str,
        rulegroup_id: Optional[str],
        rulegroup_name: Optional[str],
        default_off: bool,
        tags: List[str],
        source_order_idx: int,
        inherited_url: Optional[str],
    ) -> GrammarRule:
        exec_state, blockers = classify_rule_element(rule_elem)

        # Parse primary pattern
        pat_elem = rule_elem.find("pattern")
        if pat_elem is not None:
            pattern = self._parse_pattern(pat_elem)
        else:
            pattern = Pattern()

        # Parse antipatterns
        antipatterns = [self._parse_pattern(ap) for ap in rule_elem.findall("antipattern")]

        # Parse message template and nested suggestions
        suggestions: List[SuggestionTemplate] = []
        msg_elem = rule_elem.find("message")
        if msg_elem is not None:
            message_tmpl, extracted_suggs = self._parse_message_and_suggestions(msg_elem)
            suggestions.extend(extracted_suggs)
        else:
            message_tmpl = MessageTemplate()

        # Parse short message
        short_elem = rule_elem.find("short")
        short_msg = short_elem.text.strip() if (short_elem is not None and short_elem.text) else None

        # Parse direct child suggestions
        for sug_elem in rule_elem.findall("suggestion"):
            suggestions.append(self._parse_template(sug_elem, SuggestionTemplate))

        # Parse examples
        examples = [self._parse_example(ex) for ex in rule_elem.findall("example")]

        # URL
        url_text = rule_elem.findtext("url") or inherited_url
        if url_text:
            url_text = url_text.strip()

        return GrammarRule(
            id=rule_id,
            sub_id=sub_id,
            full_id=full_id,
            name=name,
            category_id=category_id,
            category_name=category_name,
            rulegroup_id=rulegroup_id,
            rulegroup_name=rulegroup_name,
            default_off=default_off,
            tags=tags,
            source_order_index=source_order_idx,
            pattern=pattern,
            antipatterns=antipatterns,
            message_template=message_tmpl,
            short_message=short_msg,
            suggestions=suggestions,
            examples=examples,
            url=url_text,
            execution_state=exec_state,
            blockers=blockers,
        )

    def _parse_pattern(self, pat_elem: ET.Element) -> Pattern:
        case_sensitive = (pat_elem.attrib.get("case_sensitive") == "yes")
        raw_pos = (pat_elem.attrib.get("raw_pos") == "yes")

        tokens: List[PatternToken] = []
        has_marker = False
        marker_start_idx: Optional[int] = None
        marker_end_idx: Optional[int] = None

        # Iterate over child elements in document order
        for child in pat_elem:
            if child.tag == "marker":
                has_marker = True
                m_start = len(tokens)
                for m_child in child:
                    if m_child.tag == "token":
                        t = self._parse_token(m_child, pat_case_sensitive=case_sensitive, in_marker=True)
                        tokens.append(t)
                m_end = len(tokens)
                if marker_start_idx is None:
                    marker_start_idx = m_start
                marker_end_idx = m_end
            elif child.tag == "token":
                t = self._parse_token(child, pat_case_sensitive=case_sensitive, in_marker=False)
                tokens.append(t)

        return Pattern(
            tokens=tokens,
            case_sensitive=case_sensitive,
            raw_pos=raw_pos,
            has_marker=has_marker,
            marker_start_idx=marker_start_idx,
            marker_end_idx=marker_end_idx,
        )

    def _parse_token(self, tok_elem: ET.Element, pat_case_sensitive: bool, in_marker: bool) -> PatternToken:
        tok_cs = (tok_elem.attrib.get("case_sensitive") == "yes") or pat_case_sensitive
        text = tok_elem.text.strip() if tok_elem.text else None
        if text == "":
            text = None

        postag = tok_elem.attrib.get("postag")
        postag_regexp = (tok_elem.attrib.get("postag_regexp") == "yes")
        regexp = (tok_elem.attrib.get("regexp") == "yes")
        negate = (tok_elem.attrib.get("negate") == "yes")
        negate_pos = (tok_elem.attrib.get("negate_pos") == "yes")
        inflected = (tok_elem.attrib.get("inflected") == "yes")

        skip_val = None
        if "skip" in tok_elem.attrib:
            try:
                skip_val = int(tok_elem.attrib["skip"])
            except ValueError:
                skip_val = None

        min_val = int(tok_elem.attrib["min"]) if "min" in tok_elem.attrib else None
        max_val = int(tok_elem.attrib["max"]) if "max" in tok_elem.attrib else None
        chunk_val = tok_elem.attrib.get("chunk")
        spacebefore = tok_elem.attrib.get("spacebefore")

        exceptions: List[PatternTokenException] = []
        for exc_elem in tok_elem.findall("exception"):
            exc_cs = (exc_elem.attrib.get("case_sensitive") == "yes") or tok_cs
            exc_text = exc_elem.text.strip() if exc_elem.text else None
            if exc_text == "":
                exc_text = None

            exceptions.append(
                PatternTokenException(
                    text=exc_text,
                    postag=exc_elem.attrib.get("postag"),
                    postag_regexp=(exc_elem.attrib.get("postag_regexp") == "yes"),
                    regexp=(exc_elem.attrib.get("regexp") == "yes"),
                    negate=(exc_elem.attrib.get("negate") == "yes"),
                    negate_pos=(exc_elem.attrib.get("negate_pos") == "yes"),
                    inflected=(exc_elem.attrib.get("inflected") == "yes"),
                    case_sensitive=exc_cs,
                    scope=exc_elem.attrib.get("scope", "current"),
                    spacebefore=exc_elem.attrib.get("spacebefore"),
                )
            )

        return PatternToken(
            text=text,
            postag=postag,
            postag_regexp=postag_regexp,
            regexp=regexp,
            negate=negate,
            negate_pos=negate_pos,
            inflected=inflected,
            case_sensitive=tok_cs,
            skip=skip_val,
            min=min_val,
            max=max_val,
            chunk=chunk_val,
            spacebefore=spacebefore,
            exceptions=exceptions,
            is_in_marker=in_marker,
        )

    def _parse_text_segments(self, text: str) -> List[Union[str, MatchReference]]:
        """Split text by backreferences like \\1, \\2 into strings and MatchReferences."""
        if not text:
            return []
        import re

        tokens: List[Union[str, MatchReference]] = []
        pattern = re.compile(r"\\([1-9][0-9]*)")
        last_idx = 0

        for m in pattern.finditer(text):
            if m.start() > last_idx:
                tokens.append(text[last_idx : m.start()])
            no_val = int(m.group(1))
            tokens.append(MatchReference(no=no_val))
            last_idx = m.end()

        if last_idx < len(text):
            tokens.append(text[last_idx:])

        return tokens

    def _parse_message_and_suggestions(
        self, elem: ET.Element
    ) -> Tuple[MessageTemplate, List[SuggestionTemplate]]:
        suppress_misspelled = (elem.attrib.get("suppress_misspelled") == "yes")
        msg_elements: List[Union[str, MatchReference]] = []
        suggestions: List[SuggestionTemplate] = []

        if elem.text:
            msg_elements.extend(self._parse_text_segments(elem.text))

        for child in elem:
            if child.tag == "match":
                no_val = int(child.attrib.get("no", "1"))
                m_ref = MatchReference(
                    no=no_val,
                    case_conversion=child.attrib.get("case_conversion"),
                    include_skipped=child.attrib.get("include_skipped"),
                    postag=child.attrib.get("postag"),
                    postag_regexp=child.attrib.get("postag_regexp"),
                    postag_replace=child.attrib.get("postag_replace"),
                    set_postag=child.attrib.get("set_postag"),
                )
                msg_elements.append(m_ref)
            elif child.tag == "suggestion":
                # Parse suggestion template
                sug_tmpl = self._parse_template(child, SuggestionTemplate)
                suggestions.append(sug_tmpl)
                # Keep <suggestion>...</suggestion> tags inside message template
                msg_elements.append("<suggestion>")
                msg_elements.extend(sug_tmpl.elements)
                msg_elements.append("</suggestion>")
            else:
                if child.text:
                    msg_elements.extend(self._parse_text_segments(child.text))

            if child.tail:
                msg_elements.extend(self._parse_text_segments(child.tail))

        return MessageTemplate(elements=msg_elements, suppress_misspelled=suppress_misspelled), suggestions

    def _parse_template(self, elem: ET.Element, template_cls: Any) -> Any:
        suppress_misspelled = (elem.attrib.get("suppress_misspelled") == "yes")
        elements: List[Union[str, MatchReference]] = []

        if elem.text:
            elements.extend(self._parse_text_segments(elem.text))

        for child in elem:
            if child.tag == "match":
                no_val = int(child.attrib.get("no", "1"))
                m_ref = MatchReference(
                    no=no_val,
                    case_conversion=child.attrib.get("case_conversion"),
                    include_skipped=child.attrib.get("include_skipped"),
                    postag=child.attrib.get("postag"),
                    postag_regexp=child.attrib.get("postag_regexp"),
                    postag_replace=child.attrib.get("postag_replace"),
                    set_postag=child.attrib.get("set_postag"),
                )
                elements.append(m_ref)
            elif child.tag == "suggestion":
                # nested suggestion
                sub_sug = self._parse_template(child, SuggestionTemplate)
                elements.extend(sub_sug.elements)
            else:
                if child.text:
                    elements.extend(self._parse_text_segments(child.text))

            if child.tail:
                elements.extend(self._parse_text_segments(child.tail))

        return template_cls(elements=elements, suppress_misspelled=suppress_misspelled)

    def _parse_example(self, ex_elem: ET.Element) -> Example:
        ex_type = ex_elem.attrib.get("type")
        correction = ex_elem.attrib.get("correction")

        # Reconstruct full text and collect marker spans
        full_text_parts: List[str] = []
        marker_spans: List[Tuple[int, int]] = []
        cur_pos = 0

        if ex_elem.text:
            full_text_parts.append(ex_elem.text)
            cur_pos += len(ex_elem.text)

        for child in ex_elem:
            if child.tag == "marker":
                m_text = child.text or ""
                m_start = cur_pos
                full_text_parts.append(m_text)
                cur_pos += len(m_text)
                m_end = cur_pos
                marker_spans.append((m_start, m_end))
            else:
                if child.text:
                    full_text_parts.append(child.text)
                    cur_pos += len(child.text)

            if child.tail:
                full_text_parts.append(child.tail)
                cur_pos += len(child.tail)

        full_text = "".join(full_text_parts)

        # In LanguageTool XMLRuleHandler:
        # An example is incorrect if it has type="triggers_error", type="incorrect", or a correction attribute.
        # Otherwise, if it has type="correct"/"untouched" or lacks correction/triggers_error/incorrect, it is a correct example.
        if ex_type in ("triggers_error", "incorrect") or correction is not None:
            is_incorrect = (ex_type not in ("untouched", "correct"))
        else:
            is_incorrect = False

        return Example(
            text=full_text,
            is_incorrect=is_incorrect,
            correction=correction,
            marker_spans=marker_spans,
        )
