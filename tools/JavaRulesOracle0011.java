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

/** Development-only metadata/result probe for Task 0011. */
public final class JavaRulesOracle0011 {
  private JavaRulesOracle0011() {}

  public static void main(String[] args) throws Exception {
    Language language = Languages.getLanguageForShortCode("ru");
    JLanguageTool tool = new JLanguageTool(language);
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
    if (args.length == 3 && args[0].equals("--check")) {
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
      for (int matchIndex = 0; matchIndex < matches.size(); matchIndex++) {
        RuleMatch match = matches.get(matchIndex);
        int base = bases.get(matchIndex);
        System.out.printf(
            "%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s%n",
            base + match.getFromPos(),
            base + match.getToPos(),
            match.getRule().getId(),
            match.getRule().getCategory().getId(),
            b64(match.getRule().getCategory().getName()),
            b64(match.getMessage()),
            b64(match.getShortMessage()),
            b64(String.join("\u0000", match.getSuggestedReplacements())),
            b64(match.getUrl() == null ? "" : match.getUrl().toString()));
      }
      return;
    }
    throw new IllegalArgumentException("Expected --metadata");
  }

  private static String b64(String value) {
    return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
  }
}
