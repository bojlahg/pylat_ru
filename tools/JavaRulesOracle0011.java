import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
import org.languagetool.JLanguageTool;
import org.languagetool.Language;
import org.languagetool.Languages;
import org.languagetool.rules.Rule;
import org.languagetool.rules.RuleMatch;
import org.languagetool.rules.TextLevelRule;
import org.languagetool.AnalyzedSentence;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import org.languagetool.UserConfig;

/** Development-only metadata/result probe for Task 0011. */
public final class JavaRulesOracle0011 {
  private JavaRulesOracle0011() {}

  public static void main(String[] args) throws Exception {
    Language language = Languages.getLanguageForShortCode("ru");
    String configText = args.length >= 4 ? decode(args[3]) : "";
    String configuredRule = args.length >= 2 ? args[1] : "";
    UserConfig userConfig = createConfig(configuredRule, configText);
    JLanguageTool tool = new JLanguageTool(language, null, userConfig);
    if (args.length == 1 && args[0].equals("--metadata")) {
      for (Rule rule : tool.getAllRules()) {
        System.out.printf(
            "%s\t%s\t%s\t%s\t%s%n",
            rule.getClass().getSimpleName(),
            rule.getId(),
            rule.getCategory().getId(),
            rule.getCategory().getName(),
            rule.isDefaultOff());
      }
      return;
    }
    if (args.length == 2 && args[0].equals("--rule-metadata")) {
      for (Rule rule : tool.getAllRules()) {
        if (rule.getId().equals(args[1])) {
          System.out.printf("%s\t%d\t%s\t%s%n", rule.getFullId(),
              language.getRulePriority(rule), rule.getTags(),
              rule.isIncludedInErrorsCorrectedAllAtOnce());
        }
      }
      return;
    }
    if ((args.length == 3 || args.length == 4) && args[0].equals("--check")) {
      String ruleId = args[1];
      String text = new String(Base64.getDecoder().decode(args[2]), StandardCharsets.UTF_8);
      Rule target = tool.getAllRules().stream()
          .filter(rule -> rule.getId().equals(ruleId))
          .findFirst()
          .orElseThrow(() -> new IllegalArgumentException("Unknown rule: " + ruleId));
      List<RuleMatch> matches = new ArrayList<>();
      List<Integer> bases = new ArrayList<>();
      if (target instanceof TextLevelRule) {
        for (RuleMatch match : ((TextLevelRule) target).match(tool.analyzeText(text))) {
          matches.add(match);
          bases.add(0);
        }
      } else {
        int base = 0;
        for (AnalyzedSentence sentence : tool.analyzeText(text)) {
          for (RuleMatch match : target.match(sentence)) {
            matches.add(match);
            bases.add(base);
          }
          base += sentence.getCorrectedTextLength();
        }
      }
      printMatches(matches, bases);
      return;
    }
    if ((args.length == 3 || args.length == 4)
        && (args[0].equals("--combined") || args[0].equals("--combined-raw"))) {
      String text = decode(args[2]);
      for (String ruleId : TASK_0012_RULES) {
        tool.disableRule(ruleId);
      }
      if (!args[1].isEmpty()) {
        for (String ruleId : args[1].split(",")) {
          tool.enableRule(ruleId);
        }
      }
      if (args[0].equals("--combined-raw")) {
        tool.setCleanOverlappingMatches(false);
      }
      List<RuleMatch> matches = configText.contains("level=picky")
          ? tool.check(text, JLanguageTool.Level.PICKY)
          : tool.check(text);
      List<Integer> bases = new ArrayList<>();
      for (int i = 0; i < matches.size(); i++) bases.add(0);
      printMatches(matches, bases);
      return;
    }
    throw new IllegalArgumentException("Expected --metadata");
  }

  private static final List<String> TASK_0012_RULES = Arrays.asList(
      "MORFOLOGIK_RULE_RU_RU", "MORFOLOGIK_RULE_RU_RU_YO", "RU_COMPOUNDS",
      "RU_SIMPLE_REPLACE", "WORD_REPEAT_RULE", "RU_WORD_COHERENCY",
      "RU_WORD_REPEAT", "RU_WORD_ROOT_REPEAT");

  private static UserConfig createConfig(String ruleId, String configText) {
    Map<String, Object[]> values = new HashMap<>();
    if (!configText.isEmpty()) {
      Map<String, String> parsed = new HashMap<>();
      for (String part : configText.split(";")) {
        String[] pair = part.split("=", 2);
        parsed.put(pair[0], pair[1]);
      }
      if (ruleId.equals("FILLER_WORDS_RU")) {
        values.put(ruleId, new Object[]{
            Integer.parseInt(parsed.getOrDefault("minPercent", "8")),
            Boolean.parseBoolean(parsed.getOrDefault("excludeDirectSpeech", "true"))});
      } else if (parsed.containsKey("maxWords")) {
        values.put(ruleId, new Object[]{Integer.parseInt(parsed.get("maxWords"))});
      }
    }
    return new UserConfig(values);
  }

  private static void printMatches(List<RuleMatch> matches, List<Integer> bases) {
    for (int matchIndex = 0; matchIndex < matches.size(); matchIndex++) {
      RuleMatch match = matches.get(matchIndex);
      int base = bases.get(matchIndex);
      System.out.printf(
          "%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s%n",
          base + match.getFromPos(), base + match.getToPos(), match.getRule().getId(),
          match.getRule().getCategory().getId(), b64(match.getRule().getCategory().getName()),
          b64(match.getMessage()), b64(match.getShortMessage()),
          b64(String.join("\u0000", match.getSuggestedReplacements())),
          b64(match.getUrl() == null ? "" : match.getUrl().toString()));
    }
  }

  private static String decode(String value) {
    return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
  }

  private static String b64(String value) {
    return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
  }
}
