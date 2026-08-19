"""tools/inventory_java_variants.py

Runs pinned Java PatternRuleLoader over Russian grammar.xml and produces
a complete, deterministic physical variant inventory comparing Java AbstractPatternRule
instances with Python CompiledRuleVariant / GrammarRule structures with full ordered
token signatures.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import expand_rule_into_variants
from pylat_ru.grammar.model import ExecutionState, GrammarRule
from tools.differential_lt import JavaLanguageToolOracle


JAVA_INVENTORY_SRC = """
import org.languagetool.rules.patterns.PatternRuleLoader;
import org.languagetool.rules.patterns.AbstractPatternRule;
import org.languagetool.rules.patterns.PatternRule;
import org.languagetool.rules.patterns.PatternToken;
import org.languagetool.language.Russian;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class ExtractJavaVariants {
    public static void main(String[] args) throws Exception {
        Russian russian = Russian.getInstance();
        PatternRuleLoader loader = new PatternRuleLoader();
        File xmlFile = new File("third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml");
        InputStream is = new FileInputStream(xmlFile);
        List<AbstractPatternRule> rules = loader.getRules(is, "/org/languagetool/rules/ru/grammar.xml", russian);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("java_total_physical_rules", rules.size());

        List<Map<String, Object>> ruleList = new ArrayList<>();
        Map<String, Integer> perFullIdCounts = new LinkedHashMap<>();
        Map<String, Integer> perIdCounts = new LinkedHashMap<>();
        Map<String, Integer> currentOrdinal = new HashMap<>();

        for (int i = 0; i < rules.size(); i++) {
            AbstractPatternRule r = rules.get(i);
            String fullId = r.getFullId();
            int ord = currentOrdinal.getOrDefault(fullId, 0);
            currentOrdinal.put(fullId, ord + 1);

            Map<String, Object> rMap = new LinkedHashMap<>();
            rMap.put("global_index", i);
            rMap.put("id", r.getId());
            rMap.put("sub_id", r.getSubId());
            rMap.put("full_id", fullId);
            rMap.put("variant_ordinal", ord);
            rMap.put("description", r.getDescription());
            rMap.put("category_id", r.getCategory().getId().toString());
            rMap.put("default_off", r.isDefaultOff());
            rMap.put("token_count", r.getPatternTokens().size());

            List<Map<String, Object>> tokenSigs = new ArrayList<>();
            for (PatternToken t : r.getPatternTokens()) {
                Map<String, Object> tMap = new LinkedHashMap<>();
                String text = t.getString();
                if (text != null && text.isEmpty()) {
                    text = null;
                }
                tMap.put("text", text);
                tMap.put("regexp", t.isRegularExpression());
                tMap.put("postag", t.getPOStag());
                tMap.put("postag_regexp", t.isPOStagRegularExpression());
                tMap.put("negate", t.getNegation());
                tMap.put("negate_pos", t.getPOSNegation());
                tMap.put("inflected", t.isInflected());
                tMap.put("case_sensitive", t.isCaseSensitive());
                tMap.put("chunk", t.getChunkTag() != null ? t.getChunkTag().toString() : null);
                tMap.put("skip", t.getSkipNext());
                tMap.put("min", t.getMinOccurrence());
                tMap.put("max", t.getMaxOccurrence());
                tMap.put("is_in_marker", t.isInsideMarker());

                int excCount = 0;
                try {
                    java.lang.reflect.Field rfField = PatternToken.class.getDeclaredField("rareFields");
                    rfField.setAccessible(true);
                    Object rf = rfField.get(t);
                    if (rf != null) {
                        java.lang.reflect.Field cneField = rf.getClass().getDeclaredField("currentAndNextExceptions");
                        cneField.setAccessible(true);
                        PatternToken[] cne = (PatternToken[]) cneField.get(rf);
                        if (cne != null) excCount += cne.length;

                        java.lang.reflect.Field peField = rf.getClass().getDeclaredField("previousExceptions");
                        peField.setAccessible(true);
                        PatternToken[] pe = (PatternToken[]) peField.get(rf);
                        if (pe != null) excCount += pe.length;
                    }
                } catch (Exception ignored) {
                    excCount = t.getExceptionList().size();
                }
                tMap.put("exception_count", excCount);
                tokenSigs.add(tMap);
            }
            rMap.put("tokens_signature", tokenSigs);

            ruleList.add(rMap);
            perFullIdCounts.put(fullId, perFullIdCounts.getOrDefault(fullId, 0) + 1);
            perIdCounts.put(r.getId(), perIdCounts.getOrDefault(r.getId(), 0) + 1);
        }

        out.put("rules", ruleList);
        out.put("per_full_id_counts", perFullIdCounts);
        out.put("per_id_counts", perIdCounts);

        Gson gson = new GsonBuilder().serializeNulls().setPrettyPrinting().create();
        String jsonStr = gson.toJson(out);
        File outFile = new File(args[0]);
        try (Writer writer = new OutputStreamWriter(new FileOutputStream(outFile), StandardCharsets.UTF_8)) {
            writer.write(jsonStr);
        }
        System.out.println("WRITTEN_TO:" + outFile.getAbsolutePath());
    }
}
"""


def get_java_physical_variants_inventory() -> Dict[str, Any]:
    oracle = JavaLanguageToolOracle()
    oracle.validate_oracle()
    jar = oracle.get_jar_path()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_file = Path(tmpdir) / "ExtractJavaVariants.java"
        src_file.write_text(JAVA_INVENTORY_SRC, encoding="utf-8")
        subprocess.run(
            ["javac", "-encoding", "UTF-8", "-cp", str(jar), str(src_file)],
            check=True,
        )
        json_out_file = Path(tmpdir) / "java_variants.json"
        proc = subprocess.run(
            [
                "java",
                "-Dfile.encoding=UTF-8",
                "-cp",
                f"{tmpdir}{os.pathsep}{jar}",
                "ExtractJavaVariants",
                str(json_out_file),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(json_out_file.read_text(encoding="utf-8"))


def _normalize_token_sig(tok_raw: Any, is_in_marker: bool) -> Dict[str, Any]:
    min_val = tok_raw.min if tok_raw.min is not None else 1
    max_val = tok_raw.max if tok_raw.max is not None else 1
    skip_val = tok_raw.skip if tok_raw.skip is not None else 0
    raw_text = tok_raw.text
    if raw_text is not None:
        raw_text = "".join(raw_text.split())
        if not raw_text:
            raw_text = None
    postag_val = tok_raw.postag
    return {
        "text": raw_text,
        "regexp": bool(tok_raw.regexp) if raw_text is not None else False,
        "postag": postag_val,
        "postag_regexp": bool(tok_raw.postag_regexp) if postag_val is not None else False,
        "negate": bool(tok_raw.negate),
        "negate_pos": bool(tok_raw.negate_pos),
        "inflected": bool(tok_raw.inflected),
        "case_sensitive": bool(tok_raw.case_sensitive),
        "chunk": tok_raw.chunk,
        "skip": skip_val,
        "min": min_val,
        "max": max_val,
        "is_in_marker": bool(is_in_marker),
        "exception_count": len(tok_raw.exceptions) if tok_raw.exceptions else 0,
    }


def build_full_variant_inventory() -> Dict[str, Any]:
    java_data = get_java_physical_variants_inventory()
    loader = GrammarLoader()
    source_rules = loader.load_default()
    assert len(source_rules) == 892

    engine = RussianGrammarEngine(rules=source_rules, loader=loader)
    runnable_source_rules = engine.get_runnable_rules()

    # Build Python variant signatures
    python_variants_by_full_id: Dict[str, List[Dict[str, Any]]] = {}
    python_all_variants_ordered: List[Dict[str, Any]] = []

    py_variants_all_counts = {}
    py_variants_runnable_counts = {}
    multi_variant_source_rules = []
    or_generated_extra_variants = 0
    phrase_generated_extra_variants = 0

    global_py_idx = 0
    for r in source_rules:
        variants = expand_rule_into_variants(r, global_phrases=loader.global_phrases)
        py_variants_all_counts[r.full_id] = len(variants)
        python_variants_by_full_id[r.full_id] = []

        if len(variants) > 1:
            multi_variant_source_rules.append(r.full_id)
            has_or = any(hasattr(el, "elements") and el.__class__.__name__ == "PatternOr" for el in r.pattern.elements)
            has_phrase = any(hasattr(el, "ref") and getattr(el, "ref") for el in r.pattern.elements)
            if has_or:
                or_generated_extra_variants += (len(variants) - 1)
            if has_phrase:
                phrase_generated_extra_variants += (len(variants) - 1)

        for ord_idx, v in enumerate(variants):
            token_sigs = [_normalize_token_sig(t.raw, t.is_in_marker) for t in v.tokens]
            v_sig = {
                "global_index": global_py_idx,
                "id": r.id,
                "sub_id": r.sub_id,
                "full_id": r.full_id,
                "variant_ordinal": ord_idx,
                "description": r.name,
                "category_id": r.category_id,
                "default_off": r.default_off,
                "token_count": len(token_sigs),
                "tokens_signature": token_sigs,
            }
            python_variants_by_full_id[r.full_id].append(v_sig)
            python_all_variants_ordered.append(v_sig)
            global_py_idx += 1

    for r in runnable_source_rules:
        v_list = engine._compiled_variants.get(r.full_id, [])
        py_variants_runnable_counts[r.full_id] = len(v_list)

    java_rules_list = java_data["rules"]
    java_full_id_counts = java_data["per_full_id_counts"]

    # Compare Java vs Python
    discrepancies = []
    for full_id, java_cnt in java_full_id_counts.items():
        py_cnt = py_variants_all_counts.get(full_id, 0)
        if py_cnt != java_cnt:
            discrepancies.append({
                "type": "COUNT_MISMATCH",
                "full_id": full_id,
                "java_count": java_cnt,
                "py_count": py_cnt,
            })

    # Compare ordered variant signatures
    signature_discrepancies = []
    for i, j_var in enumerate(java_rules_list):
        if i >= len(python_all_variants_ordered):
            signature_discrepancies.append({
                "type": "MISSING_PYTHON_VARIANT",
                "java_index": i,
                "full_id": j_var["full_id"],
            })
            continue
        p_var = python_all_variants_ordered[i]
        if j_var["full_id"] != p_var["full_id"]:
            signature_discrepancies.append({
                "type": "GLOBAL_ORDER_MISMATCH",
                "index": i,
                "java_full_id": j_var["full_id"],
                "py_full_id": p_var["full_id"],
            })
        elif j_var["tokens_signature"] != p_var["tokens_signature"]:
            signature_discrepancies.append({
                "type": "TOKEN_SIGNATURE_MISMATCH",
                "index": i,
                "full_id": j_var["full_id"],
                "ordinal": j_var["variant_ordinal"],
                "java_sig": j_var["tokens_signature"],
                "py_sig": p_var["tokens_signature"],
            })

    total_java_physical = java_data["java_total_physical_rules"]
    total_py_variants_all = sum(py_variants_all_counts.values())
    total_py_variants_runnable = sum(py_variants_runnable_counts.values())

    oracle = JavaLanguageToolOracle()
    jar_path = oracle.get_jar_path()
    oracle_jar_sha = hashlib.sha256(jar_path.read_bytes()).hexdigest()

    inventory = {
        "schema_version": "1.0.0",
        "provenance": {
            "pinned_lt_version": "6.8",
            "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "oracle_build_id": "lt_6.8_source_build_jdk17_stefan",
            "oracle_jar_sha256": oracle_jar_sha,
            "generator_path": "tools/inventory_java_variants.py",
        },
        "source_xml_rules_total": len(source_rules),
        "java_total_physical_rules": total_java_physical,
        "python_all_compiled_variants_total": total_py_variants_all,
        "python_runnable_source_rules_total": len(runnable_source_rules),
        "python_runnable_compiled_variants_total": total_py_variants_runnable,
        "multi_variant_source_rules_count": len(multi_variant_source_rules),
        "multi_variant_source_rule_ids": multi_variant_source_rules,
        "or_generated_extra_variants": or_generated_extra_variants,
        "phrase_generated_extra_variants": phrase_generated_extra_variants,
        "exact_count_parity_across_all_892_rules": (len(discrepancies) == 0),
        "exact_signature_and_order_parity": (len(signature_discrepancies) == 0),
        "count_discrepancies": discrepancies,
        "signature_discrepancies": signature_discrepancies,
        "per_full_id_counts": java_full_id_counts,
        "ordered_physical_variants": python_all_variants_ordered,
    }
    return inventory


if __name__ == "__main__":
    inv = build_full_variant_inventory()
    out_path = Path("compat/rule_variant_inventory.json")
    out_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved variant inventory to {out_path} ({len(inv['ordered_physical_variants'])} variants)")
    summary = {k: v for k, v in inv.items() if k not in ("per_full_id_counts", "ordered_physical_variants")}
    print(json.dumps(summary, indent=2, ensure_ascii=False))

