"""tools/inventory_java_variants.py

Runs pinned Java PatternRuleLoader over Russian grammar.xml and produces
a complete, deterministic physical variant inventory comparing Java AbstractPatternRule
instances with Python CompiledRuleVariant / GrammarRule structures.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

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

        for (int i = 0; i < rules.size(); i++) {
            AbstractPatternRule r = rules.get(i);
            Map<String, Object> rMap = new LinkedHashMap<>();
            rMap.put("index", i);
            rMap.put("id", r.getId());
            rMap.put("sub_id", r.getSubId());
            rMap.put("full_id", r.getFullId());
            rMap.put("description", r.getDescription());
            rMap.put("category_id", r.getCategory().getId().toString());
            rMap.put("default_off", r.isDefaultOff());
            rMap.put("token_count", r.getPatternTokens().size());
            rMap.put("antipattern_count", r.getAntiPatterns().size());

            ruleList.add(rMap);
            perFullIdCounts.put(r.getFullId(), perFullIdCounts.getOrDefault(r.getFullId(), 0) + 1);
            perIdCounts.put(r.getId(), perIdCounts.getOrDefault(r.getId(), 0) + 1);
        }

        System.out.println("JSON_START");
        StringBuilder sb = new StringBuilder();
        sb.append("{\\n");
        sb.append("  \\"java_total_physical_rules\\": ").append(rules.size()).append(",\\n");
        sb.append("  \\"distinct_full_ids\\": ").append(perFullIdCounts.size()).append(",\\n");
        sb.append("  \\"per_full_id_counts\\": {\\n");
        int count = 0;
        for (Map.Entry<String, Integer> e : perFullIdCounts.entrySet()) {
            sb.append("    \\"").append(e.getKey()).append("\\": ").append(e.getValue());
            if (++count < perFullIdCounts.size()) sb.append(",");
            sb.append("\\n");
        }
        sb.append("  }\\n");
        sb.append("}");
        System.out.println(sb.toString());
        System.out.println("JSON_END");
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
        proc = subprocess.run(
            ["java", "-cp", f"{tmpdir}{os.pathsep}{jar}", "ExtractJavaVariants"],
            capture_output=True,
            text=True,
            check=True,
        )
        stdout = proc.stdout
        json_str = stdout.split("JSON_START\n")[1].split("\nJSON_END")[0]
        return json.loads(json_str)


def build_full_variant_inventory() -> Dict[str, Any]:
    java_data = get_java_physical_variants_inventory()
    loader = GrammarLoader()
    source_rules = loader.load_default()
    assert len(source_rules) == 892

    engine = RussianGrammarEngine(rules=source_rules, loader=loader)
    runnable_source_rules = engine.get_runnable_rules()

    py_variants_all = {}
    py_variants_runnable = {}
    multi_variant_source_rules = []
    or_generated_extra_variants = 0
    phrase_generated_extra_variants = 0

    for r in source_rules:
        variants = expand_rule_into_variants(r, global_phrases=loader.global_phrases)
        py_variants_all[r.full_id] = len(variants)
        if len(variants) > 1:
            multi_variant_source_rules.append(r.full_id)
            has_or = any(hasattr(el, "elements") and el.__class__.__name__ == "PatternOr" for el in r.pattern.elements)
            has_phrase = any(hasattr(el, "ref") and getattr(el, "ref") for el in r.pattern.elements)
            if has_or:
                or_generated_extra_variants += (len(variants) - 1)
            if has_phrase:
                phrase_generated_extra_variants += (len(variants) - 1)

    for r in runnable_source_rules:
        v_list = engine._compiled_variants.get(r.full_id, [])
        py_variants_runnable[r.full_id] = len(v_list)

    java_full_id_counts = java_data["per_full_id_counts"]

    discrepancies = []
    for full_id, java_cnt in java_full_id_counts.items():
        py_cnt = py_variants_all.get(full_id, 0)
        if py_cnt != java_cnt:
            discrepancies.append({
                "full_id": full_id,
                "java_count": java_cnt,
                "py_count": py_cnt,
            })

    total_java_physical = java_data["java_total_physical_rules"]
    total_py_variants_all = sum(py_variants_all.values())
    total_py_variants_runnable = sum(py_variants_runnable.values())

    inventory = {
        "source_xml_rules_total": len(source_rules),
        "java_total_physical_rules": total_java_physical,
        "python_all_compiled_variants_total": total_py_variants_all,
        "python_runnable_source_rules_total": len(runnable_source_rules),
        "python_runnable_compiled_variants_total": total_py_variants_runnable,
        "multi_variant_source_rules_count": len(multi_variant_source_rules),
        "multi_variant_source_rule_ids": multi_variant_source_rules,
        "or_generated_extra_variants": or_generated_extra_variants,
        "phrase_generated_extra_variants": phrase_generated_extra_variants,
        "exact_parity_across_all_892_rules": (len(discrepancies) == 0),
        "discrepancies": discrepancies,
        "per_full_id_counts": java_full_id_counts,
    }
    return inventory


if __name__ == "__main__":
    inv = build_full_variant_inventory()
    out_path = Path("compat/rule_variant_inventory.json")
    out_path.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved variant inventory to {out_path} ({len(inv['per_full_id_counts'])} rules)")
    print(json.dumps({k: v for k, v in inv.items() if k != "per_full_id_counts"}, indent=2, ensure_ascii=False))
