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
    ExecutionState,
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
        self.global_phrases: Dict[str, PatternPhrase] = {}

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
        self.global_phrases: Dict[str, PatternPhrase] = {}

        # Collect global unifications and phrases
        global_unifications: List[UnificationDef] = []
        for u_elem in root.findall("unification"):
            global_unifications.append(self._parse_unification(u_elem))

        for child in root:
            if child.tag == "unification":
                continue
            elif child.tag == "phrase":
                _validate_attrs(child, ALLOWED_PHRASE_ATTRS, "<phrase> under root")
                _validate_children(child, ALLOWED_PHRASE_CHILDREN, "<phrase> under root")
                phrase_obj = self._parse_phrase(child, False, False, "<phrase> under root")
                if phrase_obj.id:
                    self.global_phrases[phrase_obj.id] = phrase_obj
            elif child.tag == "category":
                cat_elem = child
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
                cat_url = cat_elem.findtext("url")
                cat_tab = cat_elem.attrib.get("tab")
                cat_tabname = cat_elem.attrib.get("tabname")
                cat_premium = _parse_bool_attr(cat_elem, "premium", f"<category id='{cat_id}'>", default=False)

                cat_unifications = list(global_unifications)
                for u_elem in cat_elem.findall("unification"):
                    cat_unifications.append(self._parse_unification(u_elem))

                for cat_child in cat_elem:
                    if cat_child.tag == "rulegroup":
                        group_rules, source_order_idx = self._parse_rulegroup(
                            cat_child, cat_id, cat_name, cat_default, cat_tags, cat_url, cat_tab, cat_tabname, cat_premium, cat_unifications, source_order_idx
                        )
                        rules.extend(group_rules)
                    elif cat_child.tag == "rule":
                        rule_obj, source_order_idx = self._parse_standalone_rule(
                            cat_child, cat_id, cat_name, cat_default, cat_tags, cat_url, cat_tab, cat_tabname, cat_premium, cat_unifications, source_order_idx
                        )
                        rules.append(rule_obj)
            elif child.tag == "rulegroup":
                group_rules, source_order_idx = self._parse_rulegroup(
                    child, "MISC", "Miscellaneous", "on", [], None, None, None, False, global_unifications, source_order_idx
                )
                rules.extend(group_rules)
            elif child.tag == "rule":
                rule_obj, source_order_idx = self._parse_standalone_rule(
                    child, "MISC", "Miscellaneous", "on", [], None, None, None, False, global_unifications, source_order_idx
                )
                rules.append(rule_obj)

        return rules

    def _parse_rulegroup(
        self,
        group_elem: ET.Element,
        cat_id: str,
        cat_name: str,
        cat_default: str,
        cat_tags: List[str],
        cat_url: Optional[str],
        cat_tab: Optional[str],
        cat_tabname: Optional[str],
        cat_premium: bool,
        cat_unifications: List[UnificationDef],
        source_order_idx: int,
    ) -> Tuple[List[GrammarRule], int]:
        _validate_attrs(group_elem, ALLOWED_RULEGROUP_ATTRS, "<rulegroup>")
        _validate_children(group_elem, ALLOWED_RULEGROUP_CHILDREN, "<rulegroup>")

        group_id = group_elem.attrib.get("id")
        if not group_id:
            raise GrammarFormatError("<rulegroup> missing required 'id' attribute")
        group_name = group_elem.attrib.get("name", group_id)
        group_default = group_elem.attrib.get("default", cat_default)
        if group_default not in ("on", "off", "temp_off"):
            raise GrammarFormatError(f"Invalid default value '{group_default}' on <rulegroup id='{group_id}'>")

        group_tags_str = group_elem.attrib.get("tags")
        group_tags = (
            [t.strip() for t in group_tags_str.split() if t.strip()]
            if group_tags_str
            else cat_tags
        )
        group_url = group_elem.findtext("url") or cat_url
        group_type = group_elem.attrib.get("type")
        group_prio = _parse_int_attr(group_elem, "prio", f"<rulegroup id='{group_id}'>")
        group_tone_tags = [t.strip() for t in group_elem.attrib.get("tone_tags", "").split() if t.strip()]
        group_goal_specific = (group_elem.attrib.get("is_goal_specific") == "true")
        group_tab = group_elem.attrib.get("tab") or cat_tab
        group_tabname = group_elem.attrib.get("tabname") or cat_tabname
        group_premium = _parse_bool_attr(group_elem, "premium", f"<rulegroup id='{group_id}'>", default=cat_premium)
        group_minprevmatches = _parse_int_attr(group_elem, "minprevmatches", f"<rulegroup id='{group_id}'>")
        group_distancetokens = _parse_int_attr(group_elem, "distancetokens", f"<rulegroup id='{group_id}'>")

        # Parse group-level short message if defined
        group_short_elem = group_elem.find("short")
        if group_short_elem is not None:
            _validate_attrs(group_short_elem, set(), f"<short> in group '{group_id}'")
            _validate_children(group_short_elem, set(), f"<short> in group '{group_id}'")
            group_short = group_short_elem.text.strip() if group_short_elem.text else None
        else:
            group_short = None

        # Parse group-level antipatterns
        group_antipatterns: List[Pattern] = []
        for ap_elem in group_elem.findall("antipattern"):
            group_antipatterns.append(self._parse_pattern(ap_elem, f"antipattern in group '{group_id}'"))

        # Parse group-level examples
        group_examples: List[Example] = []
        for ex_elem in group_elem.findall("example"):
            group_examples.append(self._parse_example(ex_elem, f"example in group '{group_id}'"))

        rules: List[GrammarRule] = []
        rule_num = 0
        for r in group_elem.findall("rule"):
            _validate_attrs(r, ALLOWED_RULE_ATTRS, f"<rule> inside group '{group_id}'")
            _validate_children(r, ALLOWED_RULE_CHILDREN, f"<rule> inside group '{group_id}'")

            rule_num += 1
            r_id = r.attrib.get("id")
            assigned_id = r_id if r_id else group_id
            sub_id = str(rule_num)
            full_id = f"{assigned_id}[{sub_id}]"
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
                inherited_tab=group_tab,
                inherited_tabname=group_tabname,
                inherited_premium=group_premium,
                inherited_minprevmatches=group_minprevmatches,
                inherited_distancetokens=group_distancetokens,
                inherited_antipatterns=group_antipatterns,
                inherited_examples=group_examples,
                inherited_short=group_short,
                unifications=cat_unifications,
            )
            rules.append(rule_obj)
            source_order_idx += 1

        return rules, source_order_idx

    def _parse_standalone_rule(
        self,
        rule_elem: ET.Element,
        cat_id: str,
        cat_name: str,
        cat_default: str,
        cat_tags: List[str],
        cat_url: Optional[str],
        cat_tab: Optional[str],
        cat_tabname: Optional[str],
        cat_premium: bool,
        cat_unifications: List[UnificationDef],
        source_order_idx: int,
    ) -> Tuple[GrammarRule, int]:
        _validate_attrs(rule_elem, ALLOWED_RULE_ATTRS, "<rule>")
        _validate_children(rule_elem, ALLOWED_RULE_CHILDREN, "<rule>")

        r_id = rule_elem.attrib.get("id", "")
        if not r_id:
            raise GrammarFormatError("Standalone <rule> missing required 'id' attribute")
        sub_id = "1"
        full_id = f"{r_id}[{sub_id}]"
        r_name = rule_elem.attrib.get("name", r_id)
        r_default = rule_elem.attrib.get("default", cat_default)
        if r_default not in ("on", "off", "temp_off"):
            raise GrammarFormatError(f"Invalid default value '{r_default}' on <rule id='{full_id}'>")
        is_default_off = (r_default in ("off", "temp_off"))

        r_tags_str = rule_elem.attrib.get("tags")
        r_tags = (
            [t.strip() for t in r_tags_str.split() if t.strip()]
            if r_tags_str
            else cat_tags
        )

        rule_obj = self._parse_rule_elem(
            rule_elem=rule_elem,
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
            inherited_url=cat_url,
            inherited_type=None,
            inherited_prio=None,
            inherited_tone_tags=[],
            inherited_goal_specific=False,
            inherited_tab=cat_tab,
            inherited_tabname=cat_tabname,
            inherited_premium=cat_premium,
            inherited_minprevmatches=None,
            inherited_distancetokens=None,
            inherited_antipatterns=[],
            inherited_examples=[],
            inherited_short=None,
            unifications=cat_unifications,
        )
        source_order_idx += 1
        return rule_obj, source_order_idx

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
        inherited_tab: Optional[str] = None,
        inherited_tabname: Optional[str] = None,
        inherited_premium: bool = False,
        inherited_minprevmatches: Optional[int] = None,
        inherited_distancetokens: Optional[int] = None,
        inherited_antipatterns: List[Pattern] = None,
        inherited_examples: List[Example] = None,
        inherited_short: Optional[str] = None,
        unifications: List[UnificationDef] = None,
    ) -> GrammarRule:
        exec_state, blockers = classify_rule_element(rule_elem)

        # Parse primary pattern
        pat_elem = rule_elem.find("pattern")
        if pat_elem is not None:
            if exec_state in (ExecutionState.CORE_0007_RUNNABLE, ExecutionState.ADVANCED_0008_RUNNABLE):
                pattern = self._parse_pattern(pat_elem, f"pattern in rule '{full_id}'")
            else:
                try:
                    pattern = self._parse_pattern(pat_elem, f"pattern in rule '{full_id}'")
                except GrammarFormatError:
                    pattern = Pattern()
        else:
            pattern = Pattern()

        # Parse antipatterns (include inherited group antipatterns)
        antipatterns = list(inherited_antipatterns or [])
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
            short_msg = inherited_short

        # Parse direct child suggestions
        for sug_elem in rule_elem.findall("suggestion"):
            suggestions.append(self._parse_template(sug_elem, SuggestionTemplate, f"<suggestion> in rule '{full_id}'"))

        # Parse examples (include inherited group examples)
        examples = list(inherited_examples or [])
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
        rule_tab = rule_elem.attrib.get("tab") or inherited_tab
        rule_tabname = rule_elem.attrib.get("tabname") or inherited_tabname
        rule_premium = _parse_bool_attr(rule_elem, "premium", f"rule '{full_id}'", default=inherited_premium)
        rule_minprevmatches = _parse_int_attr(rule_elem, "minprevmatches", f"rule '{full_id}'", default=inherited_minprevmatches)
        rule_distancetokens = _parse_int_attr(rule_elem, "distancetokens", f"rule '{full_id}'", default=inherited_distancetokens)

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
            tab=rule_tab,
            tabname=rule_tabname,
            premium=rule_premium,
            minprevmatches=rule_minprevmatches,
            distancetokens=rule_distancetokens,
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
        exceptions: List[PatternTokenException] = []
        for child in elem:
            if child.tag == "token":
                children.append(self._parse_token(child, pat_case_sensitive, in_marker, f"<token> in {context}"))
            elif child.tag == "or":
                children.append(self._parse_or(child, pat_case_sensitive, in_marker, f"<or> in {context}"))
            elif child.tag == "phrase":
                children.append(self._parse_phrase(child, pat_case_sensitive, in_marker, f"<phrase> in {context}"))
            elif child.tag == "exception":
                exceptions.append(self._parse_exception(child, pat_case_sensitive, f"<exception> in {context}"))
        return PatternAnd(elements=children, exceptions=exceptions, is_in_marker=in_marker)

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

    def _parse_exception(self, exc_elem: ET.Element, tok_cs: bool, context: str) -> PatternTokenException:
        _validate_attrs(exc_elem, ALLOWED_EXCEPTION_ATTRS, context)
        _validate_children(exc_elem, ALLOWED_EXCEPTION_CHILDREN, context)

        exc_cs = _parse_bool_attr(exc_elem, "case_sensitive", context, default=tok_cs)
        exc_text_parts = [exc_elem.text or ""]
        for exc_child in exc_elem:
            if exc_child.tail:
                exc_text_parts.append(exc_child.tail)
        combined_exc_text = "".join(exc_text_parts).strip()
        exc_text = combined_exc_text if combined_exc_text else None

        scope_val = exc_elem.attrib.get("scope", "current")
        if scope_val not in ("current", "next", "previous"):
            raise GrammarFormatError(f"Invalid scope '{scope_val}' in <exception> in {context}")

        raw_pos = _parse_bool_attr(exc_elem, "raw_pos", context, default=False)

        match_elem = exc_elem.find("match")
        match_ref = self._parse_match(match_elem, f"<match> in {context}") if match_elem is not None else None

        spacebefore = exc_elem.attrib.get("spacebefore")
        if spacebefore is not None and spacebefore not in ("yes", "no"):
            raise GrammarFormatError(f"Invalid spacebefore '{spacebefore}' in <exception> in {context}")

        return PatternTokenException(
            text=exc_text,
            postag=exc_elem.attrib.get("postag"),
            postag_regexp=_parse_bool_attr(exc_elem, "postag_regexp", context, default=False),
            regexp=_parse_bool_attr(exc_elem, "regexp", context, default=False),
            negate=_parse_bool_attr(exc_elem, "negate", context, default=False),
            negate_pos=_parse_bool_attr(exc_elem, "negate_pos", context, default=False),
            inflected=_parse_bool_attr(exc_elem, "inflected", context, default=False),
            case_sensitive=exc_cs,
            scope=scope_val,
            spacebefore=spacebefore,
            raw_pos=raw_pos,
            match=match_ref,
        )

    def _parse_token(self, tok_elem: ET.Element, pat_case_sensitive: bool, in_marker: bool, context: str) -> PatternToken:
        _validate_attrs(tok_elem, ALLOWED_TOKEN_ATTRS, context)
        _validate_children(tok_elem, ALLOWED_TOKEN_CHILDREN, context)

        tok_cs = _parse_bool_attr(tok_elem, "case_sensitive", context, default=pat_case_sensitive)
        raw_text_parts = [tok_elem.text or ""]
        for child in tok_elem:
            if child.tail:
                raw_text_parts.append(child.tail)
        combined_text = "".join(raw_text_parts).strip()
        text = combined_text if combined_text else None

        postag = tok_elem.attrib.get("postag")
        postag_regexp = _parse_bool_attr(tok_elem, "postag_regexp", context, default=False)
        regexp = _parse_bool_attr(tok_elem, "regexp", context, default=False)
        negate = _parse_bool_attr(tok_elem, "negate", context, default=False)
        negate_pos = _parse_bool_attr(tok_elem, "negate_pos", context, default=False)
        inflected = _parse_bool_attr(tok_elem, "inflected", context, default=False)

        skip_val = _parse_int_attr(tok_elem, "skip", context, default=None)
        if skip_val is not None and (skip_val < -1 or skip_val > 127):
            raise GrammarFormatError(f"'skip' attribute value must be between -1 and 127: {skip_val} in {context}")

        min_val = _parse_int_attr(tok_elem, "min", context, default=None)
        if min_val is not None and min_val not in (0, 1):
            raise GrammarFormatError(f"minOccurrences must be 0 or 1: {min_val} in {context}")

        max_val = _parse_int_attr(tok_elem, "max", context, default=None)
        if max_val is not None and (max_val == 0 or max_val < -1 or max_val > 127):
            raise GrammarFormatError(f"maxOccurrences must be between -1 and 127 (excluding 0): {max_val} in {context}")

        chunk_val = tok_elem.attrib.get("chunk")
        spacebefore = tok_elem.attrib.get("spacebefore")
        if spacebefore is not None and spacebefore not in ("yes", "no"):
            raise GrammarFormatError(f"Invalid spacebefore '{spacebefore}' in {context}")

        raw_pos = _parse_bool_attr(tok_elem, "raw_pos", context, default=False)
        setpostag = tok_elem.attrib.get("setpostag")

        match_elem = tok_elem.find("match")
        match_ref = self._parse_match(match_elem, f"<match> in {context}") if match_elem is not None else None

        exceptions: List[PatternTokenException] = []
        for exc_elem in tok_elem.findall("exception"):
            exceptions.append(self._parse_exception(exc_elem, tok_cs, f"<exception> in {context}"))

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
            raw_pos=raw_pos,
            setpostag=setpostag,
            exceptions=exceptions,
            match=match_ref,
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
        if no_val is None or no_val < 0:
            raise GrammarFormatError(f"Attribute 'no' in <match> must be >= 0 in {context}")

        case_conversion = match_elem.attrib.get("case_conversion")
        if case_conversion and case_conversion.lower() not in (
            "none", "alllower", "allupper", "startlower", "startupper", "firstupper", "preserve", "notashkeel"
        ):
            raise GrammarFormatError(f"Invalid case_conversion '{case_conversion}' in {context}")

        include_skipped = match_elem.attrib.get("include_skipped")
        if include_skipped and include_skipped.lower() not in ("all", "none", "following"):
            raise GrammarFormatError(f"Invalid include_skipped '{include_skipped}' in {context}")

        setpos = match_elem.attrib.get("setpos")
        lemma_text = match_elem.text.strip() if match_elem.text else None
        if lemma_text == "":
            lemma_text = None

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
            lemma=lemma_text,
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
