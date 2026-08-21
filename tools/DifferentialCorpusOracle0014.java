import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.languagetool.JLanguageTool;
import org.languagetool.UserConfig;
import org.languagetool.language.Russian;
import org.languagetool.rules.Rule;
import org.languagetool.rules.RuleMatch;

/**
 * Development-only persistent batch oracle for Task 0014.
 *
 * <p>Starts one JVM, builds one {@link JLanguageTool} per configuration profile, and serves
 * whole-pipeline Russian check requests over a framed stdin/stdout protocol.  Every field is
 * transported base64-encoded so text, messages and suggestions survive untouched.
 *
 * <p>The protocol is deliberately line oriented and echoes the case id in every response so a
 * desynchronised stream is detected by the Python side instead of silently misattributing results.
 *
 * <p>Requests (one per line, tab separated):
 *
 * <pre>
 * PROFILE   &lt;profile_id&gt; &lt;b64 enabled_csv&gt; &lt;b64 disabled_csv&gt; &lt;b64 config_spec&gt; &lt;0|1 enable_all_default_off&gt; &lt;DEFAULT|PICKY&gt;
 * CHECK     &lt;case_id&gt; &lt;profile_id&gt; &lt;b64 text&gt;
 * INVENTORY &lt;profile_id&gt;
 * PING
 * QUIT
 * </pre>
 *
 * <p>{@code config_spec} is {@code ruleId=key:value,key:value;ruleId2=...} with the same key names
 * the pinned Java rules read from {@link UserConfig}.
 *
 * <p>Responses:
 *
 * <pre>
 * PROFILE_OK &lt;profile_id&gt; &lt;rule_count&gt;
 * RESULT     &lt;case_id&gt; &lt;finding_count&gt;
 * F          &lt;fromPos&gt; &lt;toPos&gt; &lt;b64 ruleId&gt; &lt;b64 fullId&gt; &lt;b64 categoryId&gt; &lt;b64 categoryName&gt; &lt;b64 message&gt; &lt;b64 shortMessage&gt; &lt;b64 suggestions&gt; &lt;b64 url&gt;
 * END        &lt;case_id&gt;
 * RULE       &lt;profile_id&gt; &lt;b64 id&gt; &lt;b64 fullId&gt; &lt;b64 categoryId&gt; &lt;defaultOff&gt; &lt;b64 className&gt;
 * ERROR      &lt;case_id&gt; &lt;b64 message&gt;
 * PONG
 * BYE
 * </pre>
 *
 * <p>{@code fromPos}/{@code toPos} are the raw Java {@code RuleMatch} positions, i.e. UTF-16 code
 * unit offsets into the checked {@code String}.  Suggestions are joined with U+0001 before
 * encoding so order and duplicates are preserved exactly.
 *
 * <p>This class is never packaged or imported by the installed Python library.
 */
public final class DifferentialCorpusOracle0014 {

  /** Language-model rule excluded from the ordinary/non-LM differential surface. */
  private static final String LANGUAGE_MODEL_RULE_ID = "CONFUSION_RULE";

  private static final String SUGGESTION_SEPARATOR = "\u0001";

  private DifferentialCorpusOracle0014() {}

  public static void main(String[] args) throws Exception {
    BufferedReader in =
        new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
    PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
    Map<String, JLanguageTool> profiles = new LinkedHashMap<>();
    Map<String, JLanguageTool.Level> levels = new LinkedHashMap<>();

    String line;
    while ((line = in.readLine()) != null) {
      if (line.isEmpty()) {
        continue;
      }
      String[] fields = line.split("\t", -1);
      String command = fields[0];
      try {
        if (command.equals("QUIT")) {
          out.println("BYE");
          return;
        } else if (command.equals("PING")) {
          out.println("PONG");
        } else if (command.equals("PROFILE")) {
          String profileId = fields[1];
          JLanguageTool tool =
              buildProfile(
                  decode(fields[2]), decode(fields[3]), decode(fields[4]), fields[5].equals("1"));
          profiles.put(profileId, tool);
          levels.put(profileId, JLanguageTool.Level.valueOf(fields[6]));
          out.println("PROFILE_OK\t" + profileId + "\t" + tool.getAllActiveRules().size());
        } else if (command.equals("INVENTORY")) {
          String profileId = fields[1];
          JLanguageTool tool = requireProfile(profiles, profileId);
          for (Rule rule : tool.getAllRules()) {
            out.println(
                String.join(
                    "\t",
                    "RULE",
                    profileId,
                    b64(rule.getId()),
                    b64(rule.getFullId()),
                    b64(rule.getCategory().getId().toString()),
                    rule.isDefaultOff() ? "1" : "0",
                    b64(rule.getClass().getSimpleName())));
          }
          out.println("END\t" + profileId);
        } else if (command.equals("CHECK")) {
          String caseId = fields[1];
          JLanguageTool tool = requireProfile(profiles, fields[2]);
          String text = decode(fields[3]);
          List<RuleMatch> matches = tool.check(text, levels.get(fields[2]));
          List<String> lines = new ArrayList<>();
          for (RuleMatch match : matches) {
            if (match.getRule().getId().equals(LANGUAGE_MODEL_RULE_ID)) {
              continue;
            }
            URL url = match.getUrl();
            lines.add(
                String.join(
                    "\t",
                    "F",
                    Integer.toString(match.getFromPos()),
                    Integer.toString(match.getToPos()),
                    b64(match.getRule().getId()),
                    b64(match.getRule().getFullId()),
                    b64(match.getRule().getCategory().getId().toString()),
                    b64(match.getRule().getCategory().getName()),
                    b64(match.getMessage()),
                    b64(match.getShortMessage()),
                    b64(String.join(SUGGESTION_SEPARATOR, match.getSuggestedReplacements())),
                    b64(url == null ? "" : url.toString())));
          }
          out.println("RESULT\t" + caseId + "\t" + lines.size());
          for (String resultLine : lines) {
            out.println(resultLine);
          }
          out.println("END\t" + caseId);
        } else {
          out.println("ERROR\t-\t" + b64("Unknown command: " + command));
        }
      } catch (Exception e) {
        String caseId = fields.length > 1 ? fields[1] : "-";
        out.println(
            "ERROR\t" + caseId + "\t" + b64(e.getClass().getName() + ": " + e.getMessage()));
      }
    }
    out.println("BYE");
  }

  private static JLanguageTool requireProfile(Map<String, JLanguageTool> profiles, String id) {
    JLanguageTool tool = profiles.get(id);
    if (tool == null) {
      throw new IllegalStateException("Unknown profile: " + id);
    }
    return tool;
  }

  /**
   * Builds one pinned Russian pipeline for a profile.
   *
   * <p>Rule configuration must be supplied to the {@link JLanguageTool} constructor because pinned
   * rules read {@link UserConfig} once, at construction time.
   */
  private static JLanguageTool buildProfile(
      String enabledCsv, String disabledCsv, String configSpec, boolean enableAllDefaultOff) {
    Russian russian = Russian.getInstance();
    JLanguageTool tool = new JLanguageTool(russian, null, parseConfig(configSpec));

    if (enableAllDefaultOff) {
      for (Rule rule : tool.getAllRules()) {
        if (rule.isDefaultOff() && !rule.getId().equals(LANGUAGE_MODEL_RULE_ID)) {
          tool.enableRule(rule.getId());
        }
      }
    }
    for (String ruleId : splitCsv(enabledCsv)) {
      tool.enableRule(ruleId);
    }
    for (String ruleId : splitCsv(disabledCsv)) {
      tool.disableRule(ruleId);
    }
    // The language-model rule stays outside the ordinary differential surface in every profile.
    tool.disableRule(LANGUAGE_MODEL_RULE_ID);
    return tool;
  }

  private static List<String> splitCsv(String value) {
    if (value.isEmpty()) {
      return new ArrayList<>();
    }
    return Arrays.asList(value.split(","));
  }

  /**
   * Parses {@code ruleId=key:value,key:value;...} into the positional {@code Object[]} shape each
   * pinned rule expects from {@link UserConfig#getConfigValueByID}.
   */
  private static UserConfig parseConfig(String configSpec) {
    Map<String, Object[]> values = new HashMap<>();
    if (configSpec.isEmpty()) {
      return new UserConfig(values);
    }
    for (String entry : configSpec.split(";")) {
      if (entry.isEmpty()) {
        continue;
      }
      String[] idAndBody = entry.split("=", 2);
      String ruleId = idAndBody[0];
      Map<String, String> parsed = new LinkedHashMap<>();
      if (idAndBody.length > 1 && !idAndBody[1].isEmpty()) {
        for (String pair : idAndBody[1].split(",")) {
          String[] keyValue = pair.split(":", 2);
          parsed.put(keyValue[0], keyValue.length > 1 ? keyValue[1] : "");
        }
      }
      if (ruleId.equals("FILLER_WORDS_RU")) {
        values.put(
            ruleId,
            new Object[] {
              Integer.parseInt(parsed.getOrDefault("minPercent", "8")),
              Boolean.parseBoolean(parsed.getOrDefault("excludeDirectSpeech", "true"))
            });
      } else if (parsed.containsKey("conf_ru_Value")) {
        values.put(ruleId, new Object[] {Integer.parseInt(parsed.get("conf_ru_Value"))});
      } else if (parsed.containsKey("maxWords")) {
        values.put(ruleId, new Object[] {Integer.parseInt(parsed.get("maxWords"))});
      } else {
        throw new IllegalArgumentException("Unsupported rule configuration: " + entry);
      }
    }
    return new UserConfig(values);
  }

  private static String decode(String value) {
    return value.isEmpty()
        ? ""
        : new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
  }

  private static String b64(String value) {
    return Base64.getEncoder()
        .encodeToString((value == null ? "" : value).getBytes(StandardCharsets.UTF_8));
  }
}
