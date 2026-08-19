"""src/pylat_ru/grammar/loader.py

Fail-closed XML parser and loader for LanguageTool Russian grammar.xml.
Validates exact allowed element hierarchies, child sets, attributes, and
enumerated values according to upstream LanguageTool XML Schema.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import xml.etree.ElementTree as ET

from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.errors import GrammarFormatError, GrammarResourceError
from pylat_ru.grammar.model import (
    EquivalenceDef,
    Example,
    FeatureDef,
    FilterConfig,
    GrammarRule,
    MatchReference,
    MessageTemplate,
    Pattern,
    PatternAnd,
    PatternElement,
    PatternOr,
    PatternPhrase,
    PatternToken,
    PatternTokenException,
    PatternUnify,
    PatternUnifyIgnore,
    SuggestionTemplate,
    UnificationDef,
)

# Canonical schema definitions
ALLOWED_ROOT_ATTRS = {
    "lang",
    "idprefix",
    "premium",
    "xsi:noNamespaceSchemaLocation",
    "xmlns:xsi",
    "unification",
    "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation",
    "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
}
ALLOWED_ROOT_CHILDREN = {"category", "rulegroup", "rule", "unification", "phrase"}

ALLOWED_CATEGORY_ATTRS = {
    "id", "name", "type", "default", "tab", "tabname", "tags",
    "is_goal_specific", "prio", "premium", "external", "tone_tags",
}
ALLOWED_CATEGORY_CHILDREN = {"rulegroup", "rule", "url", "unification"}

ALLOWED_RULEGROUP_ATTRS = {
    "id", "name", "default", "type", "tab", "tabname", "tags",
    "is_goal_specific", "prio", "tone_tags", "premium",
    "minprevmatches", "distancetokens",
}
ALLOWED_RULEGROUP_CHILDREN = {"rule", "url", "short", "antipattern", "example"}

ALLOWED_RULE_ATTRS = {
    "id", "name", "default", "type", "tags", "prio", "is_goal_specific",
    "sub_id", "tone_tags", "premium", "minprevmatches", "distancetokens",
}
ALLOWED_RULE_CHILDREN = {"pattern", "antipattern", "message", "short", "suggestion", "example", "url", "filter"}

ALLOWED_PATTERN_ATTRS = {"case_sensitive", "raw_pos"}
ALLOWED_PATTERN_CHILDREN = {"token", "marker", "or", "and", "unify", "unify-ignore", "phrase"}

ALLOWED_MARKER_ATTRS: Set[str] = set()
ALLOWED_MARKER_CHILDREN = {"token", "or", "and", "unify", "unify-ignore", "phrase"}

ALLOWED_TOKEN_ATTRS = {
    "postag", "postag_regexp", "regexp", "negate", "negate_pos",
    "inflected", "case_sensitive", "skip", "min", "max", "chunk",
    "spacebefore", "raw_pos", "setpostag",
}
ALLOWED_TOKEN_CHILDREN = {"exception", "match"}

ALLOWED_EXCEPTION_ATTRS = {
    "postag", "postag_regexp", "regexp", "negate", "negate_pos",
    "inflected", "case_sensitive", "scope", "spacebefore", "raw_pos",
}
ALLOWED_EXCEPTION_CHILDREN = {"match"}

ALLOWED_FILTER_ATTRS = {"class", "args"}
ALLOWED_FILTER_CHILDREN: Set[str] = set()

ALLOWED_MESSAGE_ATTRS = {"suppress_misspelled"}
ALLOWED_MESSAGE_CHILDREN = {"match", "suggestion", "marker", "b", "i", "em", "tt", "span"}

ALLOWED_SUGGESTION_ATTRS = {"suppress_misspelled"}
ALLOWED_SUGGESTION_CHILDREN = {"match", "suggestion"}

ALLOWED_MATCH_ATTRS = {
    "no", "case_conversion", "include_skipped", "postag",
    "postag_regexp", "postag_replace", "setpos",
    "regexp_match", "regexp_replace", "sub_type",
}
ALLOWED_MATCH_CHILDREN: Set[str] = set()

ALLOWED_EXAMPLE_ATTRS = {"type", "correction", "reason"}
ALLOWED_EXAMPLE_CHILDREN = {"marker"}

ALLOWED_UNIFICATION_ATTRS = {"feature"}
ALLOWED_UNIFICATION_CHILDREN = {"equivalence", "feature"}

ALLOWED_FEATURE_ATTRS = {"name", "id"}
ALLOWED_FEATURE_CHILDREN = {"token"}

ALLOWED_EQUIVALENCE_ATTRS = {"type"}
ALLOWED_EQUIVALENCE_CHILDREN = {"token"}

ALLOWED_AND_ATTRS: Set[str] = set()
ALLOWED_AND_CHILDREN = {"token", "or", "phrase", "exception"}

ALLOWED_OR_ATTRS: Set[str] = set()
ALLOWED_OR_CHILDREN = {"token", "and", "phrase"}

ALLOWED_UNIFY_ATTRS = {"negate"}
ALLOWED_UNIFY_CHILDREN = {"feature", "equivalence", "token", "and", "or", "phrase", "unify-ignore", "marker"}

ALLOWED_UNIFY_IGNORE_ATTRS: Set[str] = set()
ALLOWED_UNIFY_IGNORE_CHILDREN = {"token", "and", "or", "phrase"}

ALLOWED_PHRASE_ATTRS = {"id", "idref", "ref", "raw_pos"}
ALLOWED_PHRASE_CHILDREN = {"token", "or", "and"}


def _get_default_grammar_path() -> Path:
    """Resolve packaged grammar.xml resource path."""
    try:
        traversable = importlib.resources.files("pylat_ru.resources.rules.ru").joinpath("grammar.xml")
        with importlib.resources.as_file(traversable) as path:
            return Path(path)
    except Exception as e:
        p = Path(__file__).resolve().parent.parent / "resources" / "rules" / "ru" / "grammar.xml"
        if p.is_file():
            return p
        raise GrammarResourceError(f"Cannot locate default grammar.xml resource: {e}") from e


def _validate_attrs(elem: ET.Element, allowed: Set[str], context: str) -> None:
    for attr in elem.attrib:
        if attr not in allowed:
            raise GrammarFormatError(f"Unknown attribute '{attr}' on <{elem.tag}> in {context}")


def _validate_children(elem: ET.Element, allowed: Set[str], context: str) -> None:
    for child in elem:
        if child.tag not in allowed:
            raise GrammarFormatError(f"Disallowed child <{child.tag}> inside <{elem.tag}> in {context}")


def _parse_bool_attr(elem: ET.Element, attr: str, context: str, default: bool = False) -> bool:
    if attr not in elem.attrib:
        return default
    val = elem.attrib[attr]
    if val == "yes":
        return True
    if val == "no":
        return False
    raise GrammarFormatError(f"Invalid boolean value '{val}' for attribute '{attr}' on <{elem.tag}> in {context}")


def _parse_int_attr(elem: ET.Element, attr: str, context: str, default: Optional[int] = None) -> Optional[int]:
    if attr not in elem.attrib:
        return default
    val = elem.attrib[attr]
    try:
        return int(val)
    except ValueError as e:
        raise GrammarFormatError(f"Invalid integer value '{val}' for attribute '{attr}' on <{elem.tag}> in {context}") from e


class GrammarLoader:
    """Strict fail-closed loader and parser for Russian grammar.xml rule definitions."""

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

        _validate_attrs(root, ALLOWED_ROOT_ATTRS, "root <rules>")
        _validate_children(root, ALLOWED_ROOT_CHILDREN, "root <rules>")

        lang_val = root.attrib.get("lang")
        if not lang_val:
            raise GrammarFormatError("Root element <rules> must specify 'lang' attribute")

        rules: List[GrammarRule] = []
        source_order_idx = 0

        # Collect global unifications if any
        global_unifications: List[UnificationDef] = []
        for u_elem in root.findall("unification"):
            global_unifications.append(self._parse_unification(u_elem))

        for cat_elem in root.findall("category"):
            _validate_attrs(cat_elem, ALLOWED_CATEGORY_ATTRS, "<category>")
            _validate_children(cat_elem, ALLOWED_CATEGORY_CHILDREN, "<category>")

            cat_id = cat_elem.attrib.get("id")
            if not cat_id:
                raise GrammarFormatError("<category> missing required 'id' attribute")
            cat_name = cat_elem.attrib.get("name", cat_id)
            cat_default = cat_elem.attrib.get("default", "on")
            if cat_default not in ("on", "off", "temp_off"):
                raise GrammarFormatError(f"Invalid default value '{cat_default}' on <category id='{cat_id}'>")

            cat_tags = [t.strip() for t in cat_elem.attrib.get("tags", "").split() if t.strip()]

            # Category-level unifications
            cat_unifications = list(global_unifications)
            for u_elem in cat_elem.findall("unification"):
                cat_unifications.append(self._parse_unification(u_elem))

            for child in cat_elem:
                if child.tag == "rulegroup":
                    _validate_attrs(child, ALLOWED_RULEGROUP_ATTRS, "<rulegroup>")
                    _validate_children(child, ALLOWED_RULEGROUP_CHILDREN, "<rulegroup>")

                    group_id = child.attrib.get("id")
                    if not group_id:
                        raise GrammarFormatError("<rulegroup> missing required 'id' attribute")
                    group_name = child.attrib.get("name", group_id)
                    group_default = child.attrib.get("default", cat_default)
                    if group_default not in ("on", "off", "temp_off"):
                        raise GrammarFormatError(f"Invalid default value '{group_default}' on <rulegroup id='{group_id}'>")

                    group_tags_str = child.attrib.get("tags")
                    group_tags = (
                        [t.strip() for t in group_tags_str.split() if t.strip()]
                        if group_tags_str
                        else cat_tags
                    )
                    group_url = child.findtext("url")
                    group_type = child.attrib.get("type")
                    group_prio = _parse_int_attr(child, "prio", f"<rulegroup id='{group_id}'>")
                    group_tone_tags = [t.strip() for t in child.attrib.get("tone_tags", "").split() if t.strip()]
                    group_goal_specific = (child.attrib.get("is_goal_specific") == "true")

                    # Parse group-level antipatterns
                    group_antipatterns: List[Pattern] = []
                    for ap_elem in child.findall("antipattern"):
                        group_antipatterns.append(self._parse_pattern(ap_elem, f"antipattern in group '{group_id}'"))

                    # Parse group-level examples
                    group_examples: List[Example] = []
                    for ex_elem in child.findall("example"):
                        group_examples.append(self._parse_example(ex_elem, f"example in group '{group_id}'"))

                    rule_num = 0
                    for r in child.findall("rule"):
                        _validate_attrs(r, ALLOWED_RULE_ATTRS, f"<rule> inside group '{group_id}'")
                        _validate_children(r, ALLOWED_RULE_CHILDREN, f"<rule> inside group '{group_id}'")

                        rule_num += 1
                        r_id = r.attrib.get("id")
                        sub_id = r_id if r_id else str(rule_num)
                        full_id = f"{group_id}[{sub_id}]"
                        r_name = r.attrib.get("name", group_name)
                        r_default = r.attrib.get("default", group_default)
                        if r_default not in ("on", "off", "temp_off"):
                            raise GrammarFormatError(f"Invalid default value '{r_default}' on <rule id='{full_id}'>")
                        is_default_off = (r_default in ("off", "temp_off"))

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
                            inherited_type=group_type,
                            inherited_prio=group_prio,
                            inherited_tone_tags=group_tone_tags,
                            inherited_goal_specific=group_goal_specific,
                            inherited_antipatterns=group_antipatterns,
                            inherited_examples=group_examples,
                            unifications=cat_unifications,
                        )
                        rules.append(rule_obj)
                        source_order_idx += 1

                elif child.tag == "rule":
                    _validate_attrs(child, ALLOWED_RULE_ATTRS, "<rule>")
                    _validate_children(child, ALLOWED_RULE_CHILDREN, "<rule>")

                    r_id = child.attrib.get("id", "")
                    if not r_id:
                        raise GrammarFormatError("Standalone <rule> missing required 'id' attribute")
                    sub_id = "1"
                    full_id = f"{r_id}[{sub_id}]"
                    r_name = child.attrib.get("name", r_id)
                    r_default = child.attrib.get("default", cat_default)
                    if r_default not in ("on", "off", "temp_off"):
                        raise GrammarFormatError(f"Invalid default value '{r_default}' on <rule id='{full_id}'>")
                    is_default_off = (r_default in ("off", "temp_off"))

                    r_tags_str = child.attrib.get("tags")
                    r_tags = (
                        [t.strip() for t in r_tags_str.split() if t.strip()]
                        if r_tags_str
                        else cat_tags
                    )

                    rule_obj = self._parse_rule_elem(
                        rule_elem=child,
                        rule_id=r_id,
                        sub_id=sub_id,
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
                        inherited_type=None,
                        inherited_prio=None,
                        inherited_tone_tags=[],
                        inherited_goal_specific=False,
                        inherited_antipatterns=[],
                        inherited_examples=[],
                        unifications=cat_unifications,
                    )
                    rules.append(rule_obj)
                    source_order_idx += 1

        return rules

    def _parse_feature(self, f_elem: ET.Element, context: str) -> FeatureDef:
        _validate_attrs(f_elem, ALLOWED_FEATURE_ATTRS, context)
        _validate_children(f_elem, ALLOWED_FEATURE_CHILDREN, context)
        f_name = f_elem.attrib.get("name") or f_elem.attrib.get("id") or ""
        f_tokens = [self._parse_token(t, False, False, f"<token> in {context}") for t in f_elem.findall("token")]
        return FeatureDef(name=f_name, tokens=f_tokens)

    def _parse_equivalence(self, eq_elem: ET.Element, context: str) -> EquivalenceDef:
        _validate_attrs(eq_elem, ALLOWED_EQUIVALENCE_ATTRS, context)
        _validate_children(eq_elem, ALLOWED_EQUIVALENCE_CHILDREN, context)
        eq_type = eq_elem.attrib.get("type")
        eq_tokens = [self._parse_token(t, False, False, f"<token> in {context}") for t in eq_elem.findall("token")]
        return EquivalenceDef(type=eq_type, tokens=eq_tokens)

    def _parse_unification(self, u_elem: ET.Element) -> UnificationDef:
        _validate_attrs(u_elem, ALLOWED_UNIFICATION_ATTRS, "<unification>")
        _validate_children(u_elem, ALLOWED_UNIFICATION_CHILDREN, "<unification>")

        feature = u_elem.attrib.get("feature")
        features: List[FeatureDef] = []
        for f_elem in u_elem.findall("feature"):
            features.append(self._parse_feature(f_elem, "<feature> in <unification>"))

        equivs: List[EquivalenceDef] = []
        for eq_elem in u_elem.findall("equivalence"):
            equivs.append(self._parse_equivalence(eq_elem, "<equivalence> in <unification>"))

        return UnificationDef(feature=feature, features=features, equivalences=equivs)

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
        inherited_type: Optional[str],
        inherited_prio: Optional[int],
        inherited_tone_tags: List[str],
        inherited_goal_specific: bool,
        inherited_antipatterns: List[Pattern],
        inherited_examples: List[Example],
        unifications: List[UnificationDef],
    ) -> GrammarRule:
        exec_state, blockers = classify_rule_element(rule_elem)

        # Parse primary pattern
        pat_elem = rule_elem.find("pattern")
        if pat_elem is not None:
            pattern = self._parse_pattern(pat_elem, f"pattern in rule '{full_id}'")
        else:
            pattern = Pattern()

        # Parse antipatterns (include inherited group antipatterns)
        antipatterns = list(inherited_antipatterns)
        for ap in rule_elem.findall("antipattern"):
            antipatterns.append(self._parse_pattern(ap, f"antipattern in rule '{full_id}'"))

        # Parse filters
        filters: List[FilterConfig] = []
        for f_elem in rule_elem.findall("filter"):
            _validate_attrs(f_elem, ALLOWED_FILTER_ATTRS, f"<filter> in rule '{full_id}'")
            _validate_children(f_elem, ALLOWED_FILTER_CHILDREN, f"<filter> in rule '{full_id}'")
            f_class = f_elem.attrib.get("class")
            if not f_class:
                raise GrammarFormatError(f"<filter> missing required 'class' attribute in rule '{full_id}'")
            f_args = f_elem.attrib.get("args") or (f_elem.text.strip() if f_elem.text else None)
            filters.append(FilterConfig(class_name=f_class, args=f_args))

        # Parse message template and nested suggestions
        suggestions: List[SuggestionTemplate] = []
        msg_elem = rule_elem.find("message")
        if msg_elem is not None:
            message_tmpl, extracted_suggs = self._parse_message_and_suggestions(msg_elem, full_id)
            suggestions.extend(extracted_suggs)
        else:
            message_tmpl = MessageTemplate()

        # Parse short message
        short_elem = rule_elem.find("short")
        if short_elem is not None:
            _validate_attrs(short_elem, set(), f"<short> in rule '{full_id}'")
            _validate_children(short_elem, set(), f"<short> in rule '{full_id}'")
            short_msg = short_elem.text.strip() if short_elem.text else None
        else:
            short_msg = None

        # Parse direct child suggestions
        for sug_elem in rule_elem.findall("suggestion"):
            suggestions.append(self._parse_template(sug_elem, SuggestionTemplate, f"<suggestion> in rule '{full_id}'"))

        # Parse examples (include inherited group examples)
        examples = list(inherited_examples)
        for ex in rule_elem.findall("example"):
            examples.append(self._parse_example(ex, f"<example> in rule '{full_id}'"))

        # URL
        url_text = rule_elem.findtext("url") or inherited_url
        if url_text:
            url_text = url_text.strip()

        rule_type = rule_elem.attrib.get("type", inherited_type)
        prio = _parse_int_attr(rule_elem, "prio", f"rule '{full_id}'", default=inherited_prio)
        rule_tone_tags = (
            [t.strip() for t in rule_elem.attrib.get("tone_tags", "").split() if t.strip()]
            if "tone_tags" in rule_elem.attrib
            else inherited_tone_tags
        )
        is_goal_specific = (
            rule_elem.attrib.get("is_goal_specific") == "true"
            if "is_goal_specific" in rule_elem.attrib
            else inherited_goal_specific
        )

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
            filters=filters,
            unifications=unifications,
            message_template=message_tmpl,
            short_message=short_msg,
            suggestions=suggestions,
            examples=examples,
            url=url_text,
            rule_type=rule_type,
            prio=prio,
            tone_tags=rule_tone_tags,
            is_goal_specific=is_goal_specific,
            execution_state=exec_state,
            blockers=blockers,
        )

    def _parse_pattern(self, pat_elem: ET.Element, context: str) -> Pattern:
        _validate_attrs(pat_elem, ALLOWED_PATTERN_ATTRS, context)
        _validate_children(pat_elem, ALLOWED_PATTERN_CHILDREN, context)

        case_sensitive = _parse_bool_attr(pat_elem, "case_sensitive", context, default=False)
        raw_pos = _parse_bool_attr(pat_elem, "raw_pos", context, default=False)

        elements: List[PatternElement] = []
        tokens: List[PatternToken] = []
        has_marker = False
        marker_start_idx: Optional[int] = None
        marker_end_idx: Optional[int] = None

        for child in pat_elem:
            if child.tag == "marker":
                if has_marker:
                    raise GrammarFormatError(f"Multiple <marker> elements in {context}")
                _validate_attrs(child, ALLOWED_MARKER_ATTRS, f"<marker> in {context}")
                _validate_children(child, ALLOWED_MARKER_CHILDREN, f"<marker> in {context}")

                has_marker = True
                m_start = len(tokens)
                for m_child in child:
                    elem = self._parse_pattern_child(m_child, pat_case_sensitive=case_sensitive, in_marker=True, context=f"<{m_child.tag}> in <marker> in {context}")
                    elements.append(elem)
                    if isinstance(elem, PatternToken):
                        tokens.append(elem)
                m_end = len(tokens)
                marker_start_idx = m_start
                marker_end_idx = m_end
            else:
                elem = self._parse_pattern_child(child, pat_case_sensitive=case_sensitive, in_marker=False, context=f"<{child.tag}> in {context}")
                elements.append(elem)
                if isinstance(elem, PatternToken):
                    tokens.append(elem)

        return Pattern(
            elements=elements,
            tokens=tokens,
            case_sensitive=case_sensitive,
            raw_pos=raw_pos,
            has_marker=has_marker,
            marker_start_idx=marker_start_idx,
            marker_end_idx=marker_end_idx,
        )

    def _parse_pattern_child(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternElement:
        if elem.tag == "token":
            return self._parse_token(elem, pat_case_sensitive, in_marker, context)
        elif elem.tag == "and":
            return self._parse_and(elem, pat_case_sensitive, in_marker, context)
        elif elem.tag == "or":
            return self._parse_or(elem, pat_case_sensitive, in_marker, context)
        elif elem.tag == "unify":
            return self._parse_unify(elem, pat_case_sensitive, in_marker, context)
        elif elem.tag == "unify-ignore":
            return self._parse_unify_ignore(elem, pat_case_sensitive, in_marker, context)
        elif elem.tag == "phrase":
            return self._parse_phrase(elem, pat_case_sensitive, in_marker, context)
        else:
            raise GrammarFormatError(f"Unexpected pattern element <{elem.tag}> in {context}")

    def _parse_and(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternAnd:
        _validate_attrs(elem, ALLOWED_AND_ATTRS, context)
        _validate_children(elem, ALLOWED_AND_CHILDREN, context)
        children: List[PatternElement] = []
        for child in elem:
            if child.tag == "token":
                children.append(self._parse_token(child, pat_case_sensitive, in_marker, f"<token> in {context}"))
            elif child.tag == "or":
                children.append(self._parse_or(child, pat_case_sensitive, in_marker, f"<or> in {context}"))
            elif child.tag == "phrase":
                children.append(self._parse_phrase(child, pat_case_sensitive, in_marker, f"<phrase> in {context}"))
        return PatternAnd(elements=children, is_in_marker=in_marker)

    def _parse_or(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternOr:
        _validate_attrs(elem, ALLOWED_OR_ATTRS, context)
        _validate_children(elem, ALLOWED_OR_CHILDREN, context)
        children: List[PatternElement] = []
        for child in elem:
            if child.tag == "token":
                children.append(self._parse_token(child, pat_case_sensitive, in_marker, f"<token> in {context}"))
            elif child.tag == "and":
                children.append(self._parse_and(child, pat_case_sensitive, in_marker, f"<and> in {context}"))
            elif child.tag == "phrase":
                children.append(self._parse_phrase(child, pat_case_sensitive, in_marker, f"<phrase> in {context}"))
        return PatternOr(elements=children, is_in_marker=in_marker)

    def _parse_unify(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternUnify:
        _validate_attrs(elem, ALLOWED_UNIFY_ATTRS, context)
        _validate_children(elem, ALLOWED_UNIFY_CHILDREN, context)
        negate_val = _parse_bool_attr(elem, "negate", context, default=False)
        features: List[FeatureDef] = []
        equivalences: List[EquivalenceDef] = []
        children: List[PatternElement] = []

        for child in elem:
            if child.tag == "feature":
                features.append(self._parse_feature(child, f"<feature> in {context}"))
            elif child.tag == "equivalence":
                equivalences.append(self._parse_equivalence(child, f"<equivalence> in {context}"))
            elif child.tag == "unify-ignore":
                children.append(self._parse_unify_ignore(child, pat_case_sensitive, in_marker, f"<unify-ignore> in {context}"))
            elif child.tag == "marker":
                _validate_attrs(child, ALLOWED_MARKER_ATTRS, f"<marker> in {context}")
                _validate_children(child, ALLOWED_MARKER_CHILDREN, f"<marker> in {context}")
                for m_child in child:
                    m_elem = self._parse_pattern_child(m_child, pat_case_sensitive, in_marker=True, context=f"<{m_child.tag}> in <marker> in {context}")
                    children.append(m_elem)
            else:
                children.append(self._parse_pattern_child(child, pat_case_sensitive, in_marker, f"<{child.tag}> in {context}"))

        return PatternUnify(
            negate=negate_val,
            features=features,
            equivalences=equivalences,
            elements=children,
            is_in_marker=in_marker,
        )

    def _parse_unify_ignore(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternUnifyIgnore:
        _validate_attrs(elem, ALLOWED_UNIFY_IGNORE_ATTRS, context)
        _validate_children(elem, ALLOWED_UNIFY_IGNORE_CHILDREN, context)
        children: List[PatternElement] = []
        for child in elem:
            if child.tag == "token":
                children.append(self._parse_token(child, pat_case_sensitive, in_marker, f"<token> in {context}"))
            elif child.tag == "and":
                children.append(self._parse_and(child, pat_case_sensitive, in_marker, f"<and> in {context}"))
            elif child.tag == "or":
                children.append(self._parse_or(child, pat_case_sensitive, in_marker, f"<or> in {context}"))
            elif child.tag == "phrase":
                children.append(self._parse_phrase(child, pat_case_sensitive, in_marker, f"<phrase> in {context}"))
        return PatternUnifyIgnore(elements=children, is_in_marker=in_marker)

    def _parse_phrase(self, elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternPhrase:
        _validate_attrs(elem, ALLOWED_PHRASE_ATTRS, context)
        _validate_children(elem, ALLOWED_PHRASE_CHILDREN, context)
        pid = elem.attrib.get("id")
        pref = elem.attrib.get("ref") or elem.attrib.get("idref")
        raw_pos = _parse_bool_attr(elem, "raw_pos", context, default=False)
        children: List[PatternElement] = []
        for child in elem:
            if child.tag == "token":
                children.append(self._parse_token(child, pat_case_sensitive, in_marker, f"<token> in {context}"))
            elif child.tag == "and":
                children.append(self._parse_and(child, pat_case_sensitive, in_marker, f"<and> in {context}"))
            elif child.tag == "or":
                children.append(self._parse_or(child, pat_case_sensitive, in_marker, f"<or> in {context}"))
        return PatternPhrase(id=pid, ref=pref, raw_pos=raw_pos, elements=children, is_in_marker=in_marker)

    def _parse_token(self, tok_elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternToken:
        _validate_attrs(tok_elem, ALLOWED_TOKEN_ATTRS, context)
        _validate_children(tok_elem, ALLOWED_TOKEN_CHILDREN, context)

        tok_cs = _parse_bool_attr(tok_elem, "case_sensitive", context, default=pat_case_sensitive)
        text = tok_elem.text.strip() if tok_elem.text else None
        if text == "":
            text = None

        postag = tok_elem.attrib.get("postag")
        postag_regexp = _parse_bool_attr(tok_elem, "postag_regexp", context, default=False)
        regexp = _parse_bool_attr(tok_elem, "regexp", context, default=False)
        negate = _parse_bool_attr(tok_elem, "negate", context, default=False)
        negate_pos = _parse_bool_attr(tok_elem, "negate_pos", context, default=False)
        inflected = _parse_bool_attr(tok_elem, "inflected", context, default=False)

        skip_val = _parse_int_attr(tok_elem, "skip", context, default=None)
        min_val = _parse_int_attr(tok_elem, "min", context, default=None)
        max_val = _parse_int_attr(tok_elem, "max", context, default=None)
        chunk_val = tok_elem.attrib.get("chunk")
        spacebefore = tok_elem.attrib.get("spacebefore")

        exceptions: List[PatternTokenException] = []
        for exc_elem in tok_elem.findall("exception"):
            _validate_attrs(exc_elem, ALLOWED_EXCEPTION_ATTRS, f"<exception> in {context}")
            _validate_children(exc_elem, ALLOWED_EXCEPTION_CHILDREN, f"<exception> in {context}")

            exc_cs = _parse_bool_attr(exc_elem, "case_sensitive", f"<exception> in {context}", default=tok_cs)
            exc_text = exc_elem.text.strip() if exc_elem.text else None
            if exc_text == "":
                exc_text = None

            scope_val = exc_elem.attrib.get("scope", "current")
            if scope_val not in ("current", "next", "previous"):
                raise GrammarFormatError(f"Invalid scope '{scope_val}' in <exception> in {context}")

            exceptions.append(
                PatternTokenException(
                    text=exc_text,
                    postag=exc_elem.attrib.get("postag"),
                    postag_regexp=_parse_bool_attr(exc_elem, "postag_regexp", f"<exception> in {context}", default=False),
                    regexp=_parse_bool_attr(exc_elem, "regexp", f"<exception> in {context}", default=False),
                    negate=_parse_bool_attr(exc_elem, "negate", f"<exception> in {context}", default=False),
                    negate_pos=_parse_bool_attr(exc_elem, "negate_pos", f"<exception> in {context}", default=False),
                    inflected=_parse_bool_attr(exc_elem, "inflected", f"<exception> in {context}", default=False),
                    case_sensitive=exc_cs,
                    scope=scope_val,
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
        self, elem: ET.Element, rule_id: str
    ) -> Tuple[MessageTemplate, List[SuggestionTemplate]]:
        context = f"<message> in rule '{rule_id}'"
        _validate_attrs(elem, ALLOWED_MESSAGE_ATTRS, context)
        _validate_children(elem, ALLOWED_MESSAGE_CHILDREN, context)

        suppress_misspelled = _parse_bool_attr(elem, "suppress_misspelled", context, default=False)
        msg_elements: List[Union[str, MatchReference]] = []
        suggestions: List[SuggestionTemplate] = []

        if elem.text:
            msg_elements.extend(self._parse_text_segments(elem.text))

        for child in elem:
            if child.tag == "match":
                m_ref = self._parse_match(child, f"<match> in {context}")
                msg_elements.append(m_ref)
            elif child.tag == "suggestion":
                sug_tmpl = self._parse_template(child, SuggestionTemplate, f"<suggestion> in {context}")
                suggestions.append(sug_tmpl)
                msg_elements.append("<suggestion>")
                msg_elements.extend(sug_tmpl.elements)
                msg_elements.append("</suggestion>")
            else:
                if child.text:
                    msg_elements.extend(self._parse_text_segments(child.text))

            if child.tail:
                msg_elements.extend(self._parse_text_segments(child.tail))

        return MessageTemplate(elements=msg_elements, suppress_misspelled=suppress_misspelled), suggestions

    def _parse_template(self, elem: ET.Element, template_cls: Any, context: str) -> Any:
        _validate_attrs(elem, ALLOWED_SUGGESTION_ATTRS, context)
        _validate_children(elem, ALLOWED_SUGGESTION_CHILDREN, context)

        suppress_misspelled = _parse_bool_attr(elem, "suppress_misspelled", context, default=False)
        elements: List[Union[str, MatchReference]] = []

        if elem.text:
            elements.extend(self._parse_text_segments(elem.text))

        for child in elem:
            if child.tag == "match":
                m_ref = self._parse_match(child, f"<match> in {context}")
                elements.append(m_ref)
            elif child.tag == "suggestion":
                sub_sug = self._parse_template(child, SuggestionTemplate, f"nested <suggestion> in {context}")
                elements.extend(sub_sug.elements)
            else:
                if child.text:
                    elements.extend(self._parse_text_segments(child.text))

            if child.tail:
                elements.extend(self._parse_text_segments(child.tail))

        return template_cls(elements=elements, suppress_misspelled=suppress_misspelled)

    def _parse_match(self, match_elem: ET.Element, context: str) -> MatchReference:
        _validate_attrs(match_elem, ALLOWED_MATCH_ATTRS, context)
        _validate_children(match_elem, ALLOWED_MATCH_CHILDREN, context)

        no_val = _parse_int_attr(match_elem, "no", context, default=1)
        if no_val is None or no_val < 1:
            raise GrammarFormatError(f"Attribute 'no' in <match> must be >= 1 in {context}")

        case_conversion = match_elem.attrib.get("case_conversion")
        if case_conversion and case_conversion not in ("alllower", "allupper", "startlower", "startupper", "firstupper", "preserve"):
            raise GrammarFormatError(f"Invalid case_conversion '{case_conversion}' in {context}")

        include_skipped = match_elem.attrib.get("include_skipped")
        if include_skipped and include_skipped not in ("all", "none", "following"):
            raise GrammarFormatError(f"Invalid include_skipped '{include_skipped}' in {context}")

        setpos = match_elem.attrib.get("setpos")

        return MatchReference(
            no=no_val,
            case_conversion=case_conversion,
            include_skipped=include_skipped,
            postag=match_elem.attrib.get("postag"),
            postag_regexp=match_elem.attrib.get("postag_regexp"),
            postag_replace=match_elem.attrib.get("postag_replace"),
            setpos=setpos,
            regexp_match=match_elem.attrib.get("regexp_match"),
            regexp_replace=match_elem.attrib.get("regexp_replace"),
            sub_type=match_elem.attrib.get("sub_type"),
        )

    def _parse_example(self, ex_elem: ET.Element, context: str) -> Example:
        _validate_attrs(ex_elem, ALLOWED_EXAMPLE_ATTRS, context)
        _validate_children(ex_elem, ALLOWED_EXAMPLE_CHILDREN, context)

        ex_type = ex_elem.attrib.get("type")
        if ex_type and ex_type not in ("incorrect", "correct", "untouched", "triggers_error"):
            raise GrammarFormatError(f"Invalid example type '{ex_type}' in {context}")

        correction = ex_elem.attrib.get("correction")
        reason = ex_elem.attrib.get("reason")

        full_text_parts: List[str] = []
        marker_spans: List[Tuple[int, int]] = []
        cur_pos = 0

        if ex_elem.text:
            full_text_parts.append(ex_elem.text)
            cur_pos += len(ex_elem.text)

        for child in ex_elem:
            if child.tag == "marker":
                _validate_attrs(child, set(), f"<marker> in {context}")
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

        if ex_type in ("triggers_error", "incorrect") or correction is not None:
            is_incorrect = (ex_type not in ("untouched", "correct"))
        else:
            is_incorrect = False

        return Example(
            text=full_text,
            is_incorrect=is_incorrect,
            correction=correction,
            marker_spans=marker_spans,
            reason=reason,
        )
