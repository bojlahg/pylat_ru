"""XML rule loader and engine for Russian disambiguation rules."""

from __future__ import annotations

import importlib.resources
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken
from pylat_ru.disambiguation.errors import DisambiguationFormatError, DisambiguationResourceError
from pylat_ru.disambiguation.filters import (
    DisambiguationFilter,
    NoDisambiguationRussianPartialPosTagFilter,
)
from pylat_ru.disambiguation.pattern_matcher import (
    PatternToken,
    PatternTokenException,
)
from pylat_ru.disambiguation.rules import (
    DisambiguatedExample,
    DisambiguationPatternRule,
    DisambiguationPatternRuleReplacer,
    DisambiguatorAction,
    MatchElement,
)
from pylat_ru.tagging.russian import RussianTagger


KNOWN_FILTERS = {
    "org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter": NoDisambiguationRussianPartialPosTagFilter,
}


class DisambiguationRuleLoader:
    """Parses LanguageTool disambiguation.xml rules into DisambiguationPatternRule objects."""

    def __init__(self, tagger: Optional[RussianTagger] = None) -> None:
        self.tagger = tagger or RussianTagger.get_instance()

    def parse_file(self, file_path: Union[str, Path]) -> List[DisambiguationPatternRule]:
        """Parse disambiguation rules from a filesystem path."""
        p = Path(file_path)
        if not p.is_file():
            raise DisambiguationResourceError(f"Disambiguation XML file not found: {file_path}")
        tree = ET.parse(str(p))
        return self._parse_tree(tree)

    def parse_xml_string(self, xml_content: str) -> List[DisambiguationPatternRule]:
        """Parse disambiguation rules from an XML string."""
        tree = ET.ElementTree(ET.fromstring(xml_content))
        return self._parse_tree(tree)

    def _parse_tree(self, tree: ET.ElementTree) -> List[DisambiguationPatternRule]:
        root = tree.getroot()
        if root.tag != "rules":
            raise DisambiguationFormatError(f"Expected root tag 'rules', got '{root.tag}'")

        rules: List[DisambiguationPatternRule] = []

        for elem in root:
            if elem.tag == "rulegroup":
                rules.extend(self._parse_rulegroup(elem))
            elif elem.tag == "rule":
                rule = self._parse_rule(elem, rulegroup_id=None, rulegroup_antipatterns=[])
                if rule is not None:
                    rules.append(rule)
            elif elem.tag is ET.Comment:
                continue
            else:
                raise DisambiguationFormatError(f"Unexpected top-level tag in disambiguation XML: {elem.tag}")

        return rules

    def _parse_rulegroup(self, rg_elem: ET.Element) -> List[DisambiguationPatternRule]:
        rg_id = rg_elem.attrib.get("id", "")
        rg_name = rg_elem.attrib.get("name", rg_id)
        rg_antipatterns: List[DisambiguationPatternRule] = []

        for ap_elem in rg_elem.findall("antipattern"):
            ap_rule = self._parse_antipattern(ap_elem, parent_id=rg_id)
            if ap_rule is not None:
                rg_antipatterns.append(ap_rule)

        rules: List[DisambiguationPatternRule] = []
        for rule_elem in rg_elem.findall("rule"):
            rule = self._parse_rule(rule_elem, rulegroup_id=rg_id, rulegroup_antipatterns=rg_antipatterns)
            if rule is not None:
                rules.append(rule)

        return rules

    def _parse_rule(
        self,
        rule_elem: ET.Element,
        rulegroup_id: Optional[str],
        rulegroup_antipatterns: List[DisambiguationPatternRule],
    ) -> Optional[DisambiguationPatternRule]:
        rule_id = rule_elem.attrib.get("id") or rule_elem.attrib.get("name") or (rulegroup_id or "UNKNOWN")
        rule_name = rule_elem.attrib.get("name", rule_id)
        sub_id = rule_elem.attrib.get("id")

        pattern_elem = rule_elem.find("pattern")
        if pattern_elem is None:
            raise DisambiguationFormatError(f"Rule '{rule_id}' missing <pattern> element")

        pattern_tokens = self._parse_pattern(pattern_elem)

        # Parse rule-level antipatterns
        rule_antipatterns: List[DisambiguationPatternRule] = list(rulegroup_antipatterns)
        for ap_elem in rule_elem.findall("antipattern"):
            ap_rule = self._parse_antipattern(ap_elem, parent_id=rule_id)
            if ap_rule is not None:
                rule_antipatterns.append(ap_rule)

        # Parse filter
        filter_instance: Optional[DisambiguationFilter] = None
        filter_args: Optional[str] = None
        filter_elem = rule_elem.find("filter")
        if filter_elem is not None:
            filter_cls = filter_elem.attrib.get("class", "")
            filter_args = filter_elem.attrib.get("args", "")
            if filter_cls in KNOWN_FILTERS:
                filter_instance = KNOWN_FILTERS[filter_cls](tagger=self.tagger)
            else:
                raise DisambiguationFormatError(f"Unsupported disambiguation filter class: '{filter_cls}'")

        # Parse disambig
        disambig_elem = rule_elem.find("disambig")
        action = DisambiguatorAction.REPLACE
        disambiguated_pos: Optional[str] = None
        new_token_readings: List[AnalyzedToken] = []
        match_element: Optional[MatchElement] = None

        if disambig_elem is not None:
            raw_action = disambig_elem.attrib.get("action")
            if raw_action:
                try:
                    action = DisambiguatorAction(raw_action)
                except ValueError:
                    raise DisambiguationFormatError(f"Unknown disambig action '{raw_action}' in rule '{rule_id}'")
            else:
                action = DisambiguatorAction.REPLACE

            if "postag" in disambig_elem.attrib:
                disambiguated_pos = disambig_elem.attrib.get("postag")

            for wd_elem in disambig_elem.findall("wd"):
                pos = wd_elem.attrib.get("pos")
                lemma = wd_elem.attrib.get("lemma")
                tok_text = wd_elem.text.strip() if wd_elem.text else ""
                new_token_readings.append(AnalyzedToken(token=tok_text, pos_tag=pos, lemma=lemma))

            match_child = disambig_elem.find("match")
            if match_child is not None:
                no_str = match_child.attrib.get("no", "1")
                # In LT XML, no is 1-based (or offset), convert to 0-indexed offset from first match
                no_val = int(no_str) - 1 if int(no_str) > 0 else 0
                match_postag = match_child.attrib.get("postag")
                match_element = MatchElement(no=no_val, postag=match_postag)

        # Parse examples
        examples: List[DisambiguatedExample] = []
        untouched: List[str] = []
        for ex_elem in rule_elem.findall("example"):
            ex_type = ex_elem.attrib.get("type", "ambiguous")
            raw_xml = (ex_elem.text or "") + "".join(
                ET.tostring(child, encoding="unicode") for child in ex_elem
            )
            raw_xml = raw_xml.strip()
            if ex_type == "untouched":
                untouched.append(raw_xml)
            else:
                examples.append(
                    DisambiguatedExample(
                        example=raw_xml,
                        example_type=ex_type,
                        input_form=ex_elem.attrib.get("inputform"),
                        output_form=ex_elem.attrib.get("outputform"),
                    )
                )

        return DisambiguationPatternRule(
            id=rule_id,
            name=rule_name,
            sub_id=sub_id,
            rulegroup_id=rulegroup_id,
            pattern_tokens=pattern_tokens,
            action=action,
            disambiguated_pos=disambiguated_pos,
            match_element=match_element,
            new_token_readings=new_token_readings,
            filter=filter_instance,
            filter_args=filter_args,
            antipatterns=rule_antipatterns,
            examples=examples,
            untouched_examples=untouched,
        )

    def _parse_antipattern(
        self, ap_elem: ET.Element, parent_id: str
    ) -> Optional[DisambiguationPatternRule]:
        pattern_tokens = self._parse_pattern(ap_elem)
        return DisambiguationPatternRule(
            id=f"{parent_id}_antipattern",
            name=f"{parent_id}_antipattern",
            pattern_tokens=pattern_tokens,
            action=DisambiguatorAction.IMMUNIZE,
        )

    def _parse_pattern(self, pattern_elem: ET.Element) -> List[PatternToken]:
        case_sensitive = pattern_elem.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1")
        tokens: List[PatternToken] = []

        for child in pattern_elem:
            if child.tag == "token":
                tokens.append(self._parse_token(child, is_inside_marker=False, parent_case_sensitive=case_sensitive))
            elif child.tag == "marker":
                for m_child in child:
                    if m_child.tag == "token":
                        tokens.append(self._parse_token(m_child, is_inside_marker=True, parent_case_sensitive=case_sensitive))
                    elif m_child.tag == "and":
                        tokens.append(self._parse_and(m_child, is_inside_marker=True, parent_case_sensitive=case_sensitive))
            elif child.tag == "and":
                tokens.append(self._parse_and(child, is_inside_marker=False, parent_case_sensitive=case_sensitive))
            elif child.tag is ET.Comment:
                continue
            else:
                raise DisambiguationFormatError(f"Unexpected element in <pattern>: <{child.tag}>")

        return tokens

    def _parse_token(
        self, token_elem: ET.Element, is_inside_marker: bool, parent_case_sensitive: bool
    ) -> PatternToken:
        string_val = token_elem.text.strip() if token_elem.text else None
        if string_val == "":
            string_val = None

        is_regex = token_elem.attrib.get("regexp", "no").lower() in ("yes", "true", "1")
        is_case_sensitive = parent_case_sensitive or (
            token_elem.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1")
        )
        is_negated = token_elem.attrib.get("negate", "no").lower() in ("yes", "true", "1")
        is_inflected = token_elem.attrib.get("inflected", "no").lower() in ("yes", "true", "1")

        postag = token_elem.attrib.get("postag")
        is_postag_regex = token_elem.attrib.get("postag_regexp", "no").lower() in ("yes", "true", "1")
        is_postag_negated = token_elem.attrib.get("negate_pos", "no").lower() in ("yes", "true", "1")

        skip_str = token_elem.attrib.get("skip", "0")
        skip = int(skip_str) if skip_str != "-1" else -1

        exceptions: List[PatternTokenException] = []
        for exc_elem in token_elem.findall("exception"):
            exc = self._parse_exception(exc_elem, parent_case_sensitive=is_case_sensitive)
            exceptions.append(exc)

        return PatternToken(
            string=string_val,
            is_regex=is_regex,
            is_case_sensitive=is_case_sensitive,
            is_negated=is_negated,
            is_inflected=is_inflected,
            postag=postag,
            is_postag_regex=is_postag_regex,
            is_postag_negated=is_postag_negated,
            skip=skip,
            is_inside_marker=is_inside_marker,
            exceptions=exceptions,
        )

    def _parse_and(
        self, and_elem: ET.Element, is_inside_marker: bool, parent_case_sensitive: bool
    ) -> PatternToken:
        and_sub_tokens: List[PatternToken] = []
        for tok_child in and_elem.findall("token"):
            sub_tok = self._parse_token(
                tok_child, is_inside_marker=is_inside_marker, parent_case_sensitive=parent_case_sensitive
            )
            and_sub_tokens.append(sub_tok)

        return PatternToken(
            is_inside_marker=is_inside_marker,
            and_tokens=and_sub_tokens,
        )

    def _parse_exception(
        self, exc_elem: ET.Element, parent_case_sensitive: bool
    ) -> PatternTokenException:
        string_val = exc_elem.text.strip() if exc_elem.text else None
        if string_val == "":
            string_val = None

        is_regex = exc_elem.attrib.get("regexp", "no").lower() in ("yes", "true", "1")
        is_case_sensitive = parent_case_sensitive or (
            exc_elem.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1")
        )
        is_negated = exc_elem.attrib.get("negate", "no").lower() in ("yes", "true", "1")
        is_inflected = exc_elem.attrib.get("inflected", "no").lower() in ("yes", "true", "1")

        postag = exc_elem.attrib.get("postag")
        is_postag_regex = exc_elem.attrib.get("postag_regexp", "no").lower() in ("yes", "true", "1")
        is_postag_negated = exc_elem.attrib.get("negate_pos", "no").lower() in ("yes", "true", "1")

        scope = exc_elem.attrib.get("scope", "current")

        return PatternTokenException(
            string=string_val,
            is_regex=is_regex,
            is_case_sensitive=is_case_sensitive,
            is_negated=is_negated,
            is_inflected=is_inflected,
            postag=postag,
            is_postag_regex=is_postag_regex,
            is_postag_negated=is_postag_negated,
            scope=scope,
        )


class XmlRuleDisambiguator:
    """Applies rules loaded from disambiguation.xml sequentially to AnalyzedSentences."""

    def __init__(
        self,
        resource_path: Optional[Union[str, Path]] = None,
        tagger: Optional[RussianTagger] = None,
    ) -> None:
        self.resource_path = resource_path or "ru/disambiguation.xml"
        self.tagger = tagger or RussianTagger.get_instance()
        self.loader = DisambiguationRuleLoader(tagger=self.tagger)
        self.rules: List[DisambiguationPatternRule] = self._load_rules()
        self.replacers: List[DisambiguationPatternRuleReplacer] = [
            DisambiguationPatternRuleReplacer(r) for r in self.rules
        ]

    def _load_rules(self) -> List[DisambiguationPatternRule]:
        if isinstance(self.resource_path, Path) and self.resource_path.is_file():
            return self.loader.parse_file(self.resource_path)

        p_str = str(self.resource_path).lstrip("/\\")
        if p_str.startswith("ru/"):
            res_name = p_str[3:]
        else:
            res_name = p_str

        # Try package resources
        try:
            res = (
                importlib.resources.files("pylat_ru")
                .joinpath("resources", "ru", res_name)
            )
            if res.is_file():
                return self.loader.parse_xml_string(res.read_text(encoding="utf-8"))
        except Exception:
            pass

        # Fallback to local files
        candidates = [
            Path(__file__).resolve().parent.parent / "resources" / "ru" / res_name,
            Path("src/pylat_ru/resources/ru") / res_name,
            Path("third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru") / res_name,
        ]
        for c in candidates:
            if c.is_file():
                return self.loader.parse_file(c)

        raise DisambiguationResourceError(f"Disambiguation XML resource not found: {self.resource_path}")

    def disambiguate(self, sentence: AnalyzedSentence) -> AnalyzedSentence:
        """Run all loaded disambiguation rules sequentially over the sentence."""
        current_sentence = sentence
        for replacer in self.replacers:
            current_sentence = replacer.replace(current_sentence)
        return current_sentence
