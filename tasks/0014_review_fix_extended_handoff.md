# Task 0014 REVIEW-FIX — расширенное техническое задание
## Strict differential parity, checking levels, config-sensitive evidence и финальный exact-SHA CI

> Этот документ предназначен для модели/исполнителя, у которого **нет предыдущего контекста проекта**.
> Не предполагай знание прошлых задач, принятых решений или причин текущей архитектуры.
> Сначала прочитай документ целиком, затем изучи указанные файлы репозитория и только после этого меняй код.

---

# 1. Проект и конечная цель

Репозиторий:

```text
bojlahg/pylat_ru
```

Ветка:

```text
main
```

Проект `pylat_ru` — нативная Python-реализация русской части LanguageTool, максимально совместимая с закреплённой версией Java LanguageTool.

Основная цель проекта:

- воспроизвести поведение русской проверки LanguageTool;
- использовать Python в production;
- **не требовать Java/JRE/JVM в production**;
- использовать Java LanguageTool только как development/test oracle;
- добиться воспроизводимой parity против конкретного pinned upstream;
- не заменять точное поведение LanguageTool эвристически похожим поведением сторонних NLP-библиотек.

Закреплённый upstream LanguageTool:

```text
LanguageTool version: 6.8
Pinned upstream commit:
e807fcde6a6506191e1470744d2345da28c26be6
```

Trusted Java oracle build:

```text
build id:
lt_6.8_source_build_jdk17_stefan
```

Trusted oracle JAR SHA-256:

```text
b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
```

Это не "примерная совместимость".
Если Java и Python расходятся на observable behavior, нужно либо:

1. исправить Python;
2. доказать узкий баг pinned upstream;
3. либо явно классифицировать действительно неизбежимое расхождение.

Широкие allowlist'ы, "примерно то же самое" и молчаливое игнорирование полей запрещены.

---

# 2. Что уже было реализовано до Task 0014

К Task 0014 проект уже прошёл несколько больших этапов.

## 2.1. XML grammar

Русский `grammar.xml` уже распарсен и исполняется Python-движком.

Принятая совместимость до текущего review-fix:

```text
Russian XML source rules: 892 / 892 runnable
Grammar examples:         2446 / 2446 runnable
Compiled variants:        907 / 907
XML filters:              7 / 7
```

В проекте уже реализованы сложные конструкции:

- pattern tokens;
- optional/min/max occurrences;
- skip/backtracking;
- antipatterns;
- unification;
- phrase references;
- synthesize;
- фильтры;
- source registration semantics;
- XML rule variants;
- UTF-16/code-point offset mapping.

Не переписывай XML engine заново.

## 2.2. Ordinary Java rules

Русские/общие Java rules, которые LanguageTool регистрирует отдельно от XML, уже перенесены в Python.

Принятое покрытие:

```text
ordinary Java rules: 23 / 23
```

В том числе:

- CommaWhitespaceRule
- UppercaseSentenceStartRule
- MultipleWhitespaceRule
- SentenceWhitespaceRule
- WhiteSpaceBeforeParagraphEnd
- WhiteSpaceAtBeginOfParagraph
- LongSentenceRule
- LongParagraphRule
- ParagraphRepeatBeginningRule
- PunctuationMarkAtParagraphEnd2
- RussianFillerWordsRule
- RussianUnpairedBracketsRule
- RussianVerbConjugationRule
- RussianDashRule
- RussianSpecificCaseRule
- MorfologikRussianSpellerRule
- MorfologikRussianYOSpellerRule
- RussianCompoundRule
- RussianSimpleReplaceRule
- RussianSimpleWordRepeatRule
- RussianWordCoherencyRule
- RussianWordRepeatRule
- RussianWordRootRepeatRule

Не надо заново проектировать регистрацию этих правил.

## 2.3. Spelling / Morfologik

Python-проект уже содержит собственную реализацию необходимых Morfologik/FSA-механизмов и русской орфографии.

Уже есть:

- чтение бинарных словарей;
- metadata;
- FSA;
- suffix sequence encoder;
- weighted edit distance;
- replacement pairs;
- spelling additions;
- ignore/prohibited/nosuggest handling;
- Russian ordinary speller;
- YO speller;
- bounded suggestion generation;
- кеширование;
- performance tests.

Не заменяй это `pymorphy`, Hunspell, Natasha или сетевым LanguageTool.

## 2.4. Global match filtering

В проекте уже реализовано поведение LanguageTool для глобальной фильтрации результатов:

```text
SameRuleGroupFilter
CleanOverlappingFilter
language-dependent level filtering
```

Уже учитываются:

- start-order stability;
- overlapping matches;
- priorities;
- picky tag;
- punctuation-only correction behavior;
- equal-priority longest match;
- last/current tie behavior;
- adjacent duplicate suggestions.

Не возвращайся к naïve global sort + greedy longest.

## 2.5. Language-model rule

Единственное оставшееся намеренно не реализованное правило:

```text
RussianConfusionProbabilityRule
```

Его статус:

```text
LANGUAGE_MODEL_DEFERRED
```

Rule ID Java side:

```text
CONFUSION_RULE
```

**Task 0014 review-fix НЕ должен реализовывать language-model rule.**


---

# 3. Что такое Task 0014

Task 0014 — это не новая пользовательская функциональность.

Это большая differential compatibility campaign:

```text
pylat_ru whole pipeline
vs
pinned Java LanguageTool 6.8 whole pipeline
```

Цель Task 0014:

1. создать большой детерминированный русский корпус;
2. прогнать один и тот же текст через Java и Python;
3. сравнить полный observable output;
4. найти скрытые расхождения, которые не покрывались unit/upstream tests;
5. минимизировать найденные mismatch cases;
6. исправить production Python;
7. сохранить regression evidence;
8. доказать отсутствие unexplained ordinary discrepancies;
9. не вносить Java dependency в production.

Task 0014 уже в основном реализован.
Текущая задача — **review-fix существующей реализации**, а не создание Task 0014 с нуля.

---

# 4. Текущий baseline

Текущий `main` на момент review:

```text
f5cd5fb630c71ba3ee251471aaceaee4134d4522
```

Основной Task-0014 implementation parent:

```text
e8c7d2a027bb651d583bee9fa1cd532ed5c4a1d0
```

Последний commit `f5cd...` — docs-only commit, который записал CI run для родителя `e8c7...`.

Это важно для final exact-SHA gate: старый CI нельзя считать финальным CI нового review-fix SHA.

---

# 5. Что уже сделано в существующем Task 0014

Существующую реализацию надо сохранить и исправить точечно.

Уже есть:

- persistent batched Java oracle;
- один long-lived JVM process;
- несколько whole-pipeline configuration profiles;
- deterministic corpus generator;
- deterministic semantic case IDs;
- corpus strata;
- external natural corpus support;
- source hashes;
- campaign runner;
- resumable/sharded execution;
- strict-ish comparator;
- mismatch classification;
- mismatch minimizer;
- regression fixtures;
- UTF-16 calibration fixture;
- summary generator;
- state/order isolation checks;
- wheel boundary tests;
- manifest binding;
- upstream-defect evidence.

---

# 6. Текущие corpus strata

Task 0014 использует пять слоёв корпуса.

## Stratum A — accepted upstream evidence

Тексты из уже принятых oracle/upstream fixtures:

- Task 0011;
- Task 0012;
- Task 0013;
- grammar examples.

Используются whole-text inputs.

Direct low-level speller inputs сюда намеренно не относятся.

## Stratum B — deterministic mutations

Детерминированные мутации реальных/принятых русских текстов.

Примеры:

- лишний пробел;
- удаление пробела;
- NBSP;
- tab;
- linebreak;
- paragraph break;
- punctuation edits;
- case mutation;
- spelling mutation;
- boundary mutation;
- punctuation/quote changes;
- Unicode decorations.

Seed фиксирован.

## Stratum C — spelling stress

Большой набор spelling-heavy inputs.

Цель:

- ordinary spelling;
- YO behavior;
- mixed scripts;
- prohibited/ignore/nosuggest;
- suggestion generation;
- proper names;
- morphology-related spelling interactions.

## Stratum D — natural Russian prose

Внешний естественный русский корпус.

Сейчас используются как минимум два независимых источника:

- Wikipedia;
- Wikisource.

Сами большие corpus-файлы не должны попадать в wheel/package.

В репозитории должны храниться только необходимые metadata/hash/provenance.

## Stratum E — Unicode / offset targeted

Cases для:

- non-BMP;
- emoji;
- combining characters;
- soft hyphen;
- UTF-16 offset mapping;
- punctuation around Unicode;
- nested offsets.

---

# 7. Текущие результаты Task 0014 до review-fix

Существующая кампания заявляет примерно:

```text
unique texts:       9615
profile executions: 17425

comparable cases:   17388
exact cases:        17388
non-exact:          0

Java oracle errors: 37
```

Также существующая реализация создала порядка:

```text
238 minimized regression cases
```

Эти числа НЕ являются новыми acceptance constants.

После исправления comparator/profile semantics кампания должна быть прогнана заново, и реальные totals могут измениться.

---

# 8. Известный pinned upstream defect

В существующей кампании обнаружено около 37 Java oracle error cases, связанных с:

```text
ParagraphRepeatBeginningRule
```

Pinned Java в определённой ситуации создаёт некорректный второй `RuleMatch` range.

Эти случаи уже были отдельно классифицированы как upstream defect.

Требование:

- не превращать их в exact;
- не скрывать;
- не считать Python mismatch;
- держать как явные `JAVA_ORACLE_ERROR`;
- после review-fix перепроверить count/fingerprint;
- если число изменилось из-за новых executions — объяснить изменение.

Не хардкодить число 37 как сакральную константу.

---

# 9. Главная проблема review

Task 0014 полезен и реально нашёл production bugs.

Но текущий "100% parity" пока нельзя считать достаточно строгим.

Review нашёл несколько дырок именно в **evidence layer**.

Основная задача review-fix:

```text
сделать доказательство parity действительно строгим
и затем заново прогнать differential campaign
```


---

# 10. DEFECT 1 — comparator не сравнивает full_rule_id

## 10.1. Текущее состояние

Java helper уже передаёт:

```java
match.getRule().getId()
match.getRule().getFullId()
```

Python `RuleMatch` уже хранит:

```python
rule_id
full_rule_id
```

Но Task-0014 comparison schema использует только `rule_id`.

В результате два findings могут иметь:

```text
same rule_id
different full_rule_id
```

и потенциально пройти как exact.

Для XML это особенно важно, потому что несколько физических rule variants/subrules могут иметь общий base ID.

Концептуально:

```text
RULE_X[1]
RULE_X[2]
```

не должны считаться одинаковым finding только потому, что base rule ID совпал.

## 10.2. Что изменить

В canonical differential `Finding` добавить:

```python
full_rule_id: str
```

Обновить:

```text
tools/differential_lt.py
tools/differential_batch_oracle_0014.py
```

Java protocol уже содержит fullId, поэтому менять формат Java output, вероятно, минимально или вообще не потребуется.

## 10.3. Strict comparator

`Finding.comparable()` должен включать `full_rule_id`.

Итоговый strict observable schema должен сравнивать минимум:

```text
rule_id
full_rule_id
category_id
category_name
message
short_message
UTF-16 offset
UTF-16 length
ordered suggestions
URL
finding sequence order
```

## 10.4. Diagnostics

Добавить mismatch kind:

```text
FULL_RULE_ID_MISMATCH
```

Он должен участвовать только в diagnostic classification.

Строгий verdict:

```text
is_exact_match
```

должен определяться equality полного ordered comparable output, а не диагностическим pairing.

## 10.5. Тесты

Добавить тесты:

1. одинаковый `rule_id`, разный `full_rule_id` → mismatch;
2. одинаковый XML base ID, разные subrule/full IDs → mismatch;
3. одинаковые `full_rule_id` → exact;
4. repeated findings с разными full IDs не collapse;
5. finding order остаётся значимым.

---

# 11. DEFECT 2 — comparator не сравнивает category_name

## 11.1. Текущее состояние

Java helper уже передаёт:

```java
match.getRule().getCategory().getId()
match.getRule().getCategory().getName()
```

Python `RuleMatch` уже хранит:

```text
category_id
category_name
```

Но current differential schema сравнивает только ID.

## 11.2. Что изменить

Добавить:

```python
category_name: str
```

в canonical `Finding`.

Обновить:

- Java parser;
- Python projection;
- comparable schema;
- JSON serialization;
- fixtures;
- summary;
- regression evidence.

## 11.3. Новый mismatch kind

```text
CATEGORY_NAME_MISMATCH
```

## 11.4. Тесты

Нужны как минимум:

```text
same category_id + different category_name => mismatch
same category_id + same category_name      => exact
```

---

# 12. Итоговый strict observable Finding schema

После review-fix canonical comparable finding должен включать:

```text
rule_id
full_rule_id
category_id
category_name
message
short_message
UTF-16 offset
UTF-16 length
ordered suggested replacements
URL
```

На уровне sequence также сравниваются:

```text
finding multiplicity
finding order
```

Suggestions:

- порядок значим;
- duplicate suggestions значимы;
- нельзя превращать в set;
- нельзя sort'ить.

Code-point offsets Python side допустимо хранить как diagnostics.

Они **не входят** в strict equality, потому что прямого Java equivalent нет.


---

# 13. DEFECT 3 — config profiles для LongSentence/LongParagraph не доказывают PICKY behavior

## 13.1. Контекст

`LongSentenceRule` и `LongParagraphRule` в pinned LanguageTool относятся к `Tag.picky`.

Pinned JLanguageTool умеет checking levels:

```text
DEFAULT
PICKY
```

На `DEFAULT` picky findings отбрасываются.

Python implementation уже учитывает этот факт.

## 13.2. Текущая ошибка evidence layer

Существующие профили:

```text
cfg_long_sentence_15
cfg_long_paragraph_30
```

меняют `maxWords`.

Но Java helper затем вызывает обычный:

```java
tool.check(text)
```

То есть default level.

Получается:

- configuration реально передана;
- правило может даже построить internal match;
- но final pipeline удаляет picky finding;
- Java и Python оба возвращают "ничего";
- differential говорит exact;
- threshold parity фактически не доказана.

---

# 14. Добавить checking level в Profile

`Profile` должен явно хранить checking level.

Например:

```python
level: str = "DEFAULT"
```

Допустимые значения:

```text
DEFAULT
PICKY
```

Можно использовать enum, если архитектурно удобнее.

## 14.1. Semantic identity

Checking level обязан входить в:

```text
Profile.to_dict()
Profile.signature()
CorpusCase semantic identity
```

Один и тот же text под DEFAULT и PICKY — это два разных semantic cases.

## 14.2. Java side

Для profile level использовать pinned JLanguageTool semantics.

Концептуально:

```java
tool.check(text, JLanguageTool.Level.DEFAULT)
tool.check(text, JLanguageTool.Level.PICKY)
```

Используй точный API pinned LanguageTool 6.8.

Не симулируй PICKY простым `enableRule`.

Checking level и rule enabled/disabled — разные механизмы.

## 14.3. Python side

Python whole pipeline должен получить аналогичное level behavior.

Предпочтительный public API:

```python
LanguageToolRU.check(text, level=...)
```

При этом:

```text
default level == DEFAULT
```

и существующий код:

```python
tool.check(text)
```

не должен менять behavior.

Если public API менять архитектурно нежелательно, development adapter допустим только при условии, что он использует production filtering implementation, а не дублирует правила отдельно.

---

# 15. Какие профили должны использовать PICKY

Минимум:

```text
cfg_long_sentence_15
cfg_long_paragraph_30
```

Они должны запускаться как:

```text
level=PICKY
```

Reference cases для проверки их effect также должны использовать соответствующий PICKY reference, иначе сравнение "config vs default" будет бессмысленным.

---

# 16. Проверки checking levels

Нужны focused tests.

## DEFAULT

```text
picky candidate exists internally
final DEFAULT result does not contain picky finding
```

## PICKY

```text
тот же candidate survives
```

## Java/Python

Для одинакового текста:

```text
Java DEFAULT == Python DEFAULT
Java PICKY   == Python PICKY
```

Также:

```text
DEFAULT profile signature != PICKY profile signature
```


---

# 17. DEFECT 4 — нет настоящего spelling UserConfig profile

## 17.1. Контекст

Russian ordinary speller имеет pinned configuration option:

```text
conf_ru_Value
```

Task 0012 уже реализовал эту семантику в Python.

Она влияет на поведение при Latin / non-Russian / mixed-script tokens.

## 17.2. Что сейчас есть

Сейчас есть профиль вроде:

```text
cfg_speller_yo
```

который:

```text
enable MORFOLOGIK_RULE_RU_RU_YO
disable MORFOLOGIK_RULE_RU_RU
```

Это проверяет enable/disable rules.

Но это НЕ проверяет:

```text
UserConfig conf_ru_Value
```

---

# 18. Добавить config profile для ordinary speller

Добавить отдельный профиль, например:

```text
cfg_speller_conf_ru_1
```

С configuration:

```python
{
    "MORFOLOGIK_RULE_RU_RU": {
        "conf_ru_Value": 1
    }
}
```

Можно также добавить explicit reference:

```text
cfg_speller_conf_ru_0
```

если это упрощает sensitivity evidence.

`cfg_speller_yo` можно оставить, но он не закрывает requirement UserConfig parity.

---

# 19. DEFECT 5 — наличие profile ещё не доказывает, что config реально повлиял на результат

Это самый важный evidence issue после comparator.

Текущая кампания может прогонять профиль по случайной deterministic выборке B/D, где параметр ничего не меняет.

Тогда:

```text
Java configured output == Java default output
Python configured output == Python default output
```

и differential "успешен", хотя configuration path фактически не exercised.

Нужно доказать не только:

```text
Java configured == Python configured
```

но и:

```text
configuration действительно observable
```

---

# 20. Config-sensitive targeted evidence

Для каждого обязательного configuration profile нужны специальные controlled whole-pipeline texts.

Минимум четыре группы.

## 20.1. Long sentence threshold

Profile:

```text
cfg_long_sentence_15
level=PICKY
```

Нужны cases около boundary:

```text
below
equal
above
```

Или точный эквивалент pinned semantics.

Нужно доказать:

```text
Java configured output != Java reference PICKY output
```

хотя бы для одного case.

И одновременно:

```text
Python configured == Java configured
```

## 20.2. Long paragraph threshold

Profile:

```text
cfg_long_paragraph_30
level=PICKY
```

Нужны controlled paragraphs:

```text
below
equal
above
guard-band / paragraph-end semantics
```

Pinned LongParagraphRule имеет специфическое поведение near paragraph end.

Не своди проверку к простому `word_count > max`.

Нужно использовать уже реализованную pinned-compatible semantics.

## 20.3. Filler words

Profile:

```text
cfg_filler_words_2
```

Нужен controlled текст, где изменение:

```text
minPercent
```

реально меняет final whole-pipeline result.

При необходимости также проверить:

```text
excludeDirectSpeech
```

Но minimum requirement — observable effect хотя бы одного non-default option.

## 20.4. Speller conf_ru_Value

Profile:

```text
cfg_speller_conf_ru_1
```

Нужны Latin/mixed-script cases, для которых pinned Java:

```text
conf_ru_Value=0
!=
conf_ru_Value=1
```

по final finding sequence.

---

# 21. Machine-readable config sensitivity accounting

Добавить явное evidence.

Можно:

- в `compat/differential_summary_0014.json`;
- или отдельным committed JSON.

Для каждого required profile хранить минимум:

```json
{
  "profile_id": "...",
  "reference_profile": "...",
  "targeted_cases": 0,
  "java_cases_with_observable_delta": 0,
  "python_cases_with_same_observable_delta": 0,
  "java_python_exact_cases": 0,
  "delta_rule_ids": []
}
```

Acceptance для каждого required profile:

```text
targeted_cases > 0

java_cases_with_observable_delta > 0

python_cases_with_same_observable_delta > 0

java_python_exact_cases == targeted_cases
```

Если хотя бы один required profile имеет:

```text
java_cases_with_observable_delta == 0
```

validation должна FAIL CLOSED.

Нельзя просто записать ноль в отчёт и продолжить.

---

# 22. Reference profile semantics

Configuration sensitivity сравнивает:

```text
configured Java
vs
reference Java
```

Reference должен отличаться только нужной configuration dimension.

Пример для LongSentence:

```text
reference:
PICKY
default maxWords

target:
PICKY
maxWords=15
```

Плохо:

```text
reference DEFAULT level
target PICKY level
```

Потому что тогда delta вызван level, а не config.

То же правило применять для других profiles.


---

# 23. Existing Java helper

Главный Java helper:

```text
tools/DifferentialCorpusOracle0014.java
```

Он development-only.

Production package его не импортирует и не включает.

Helper уже:

- поднимает Russian JLanguageTool;
- принимает profile configuration;
- enable/disable rules;
- отключает CONFUSION_RULE;
- возвращает ordered RuleMatch output;
- передаёт UTF-16 positions;
- сохраняет ordered suggestions;
- передаёт URL;
- передаёт full rule ID;
- передаёт category ID/name.

Расширяй helper минимально:

- checking level;
- при необходимости profile metadata.

Не превращай его в второй LanguageTool implementation.

Oracle должен оставаться максимально тонким адаптером pinned Java API.

---

# 24. Existing Python differential files

Сначала изучить минимум:

```text
tools/differential_lt.py
tools/differential_batch_oracle_0014.py
tools/differential_corpus_0014.py
tools/DifferentialCorpusOracle0014.java
```

Также:

```text
compat/differential_corpus_0014_manifest.json
compat/differential_summary_0014.json
compat/differential_state_isolation_0014.json
compat/differential_allowlist_0014.json
compat/differential_upstream_defects_0014.json
compat/oracle_manifest.json
compat/compatibility.json

tests/fixtures/differential_regressions_0014.json
tests/fixtures/oracle_utf16_calibration_0014.json

reports/0014_differential_corpus.md
```

И Task-0014 tests:

```text
tests/unit/test_differential_boundary_0014.py
tests/unit/test_differential_comparator_0014.py
tests/unit/test_differential_corpus_generator_0014.py
tests/unit/test_differential_manifest_0014.py
tests/unit/test_differential_regressions_0014.py
tests/unit/test_picky_level_filter_0014.py
tests/unit/test_pattern_token_whitespace_0014.py
```

Названия могут расшириться после review-fix.

---

# 25. Comparator architecture requirements

Strict verdict не должен зависеть от heuristic pairing.

Правильная модель:

```text
ordered Java sequence
vs
ordered Python sequence
```

Каждый finding превращается в canonical comparable tuple.

Если sequences полностью равны:

```text
exact
```

Иначе:

```text
non-exact
```

После этого diagnostic logic может пытаться понять причину:

- missing;
- extra;
- rule ID mismatch;
- full rule ID mismatch;
- category mismatch;
- category name mismatch;
- span mismatch;
- message mismatch;
- suggestion mismatch;
- URL mismatch;
- order mismatch.

Diagnostics не имеют права превращать mismatch в exact.

---

# 26. Mismatch vocabulary

Сохранить существующие mismatch kinds и добавить:

```text
FULL_RULE_ID_MISMATCH
CATEGORY_NAME_MISMATCH
```

Существующие, вероятно:

```text
MISSING_FINDING
EXTRA_FINDING
RULE_ID_MISMATCH
CATEGORY_MISMATCH
SPAN_MISMATCH
MESSAGE_MISMATCH
SHORT_MESSAGE_MISMATCH
SUGGESTION_CONTENT_MISMATCH
SUGGESTION_ORDER_MISMATCH
FINDING_ORDER_MISMATCH
URL_MISMATCH
JAVA_ORACLE_ERROR
PYTHON_ERROR
```

Tests должны проверять, что report vocabulary ограничен declared set.

---

# 27. UTF-16 requirement

Java `String` positions:

```text
UTF-16 code units
```

Python native indices:

```text
Unicode code points
```

В проекте уже есть mapper.

Differential strict comparison должен использовать:

```text
RuleMatch.utf16_offset
RuleMatch.utf16_length
```

Python code-point offset/length можно хранить только для debugging.

Нельзя случайно вернуть comparator к Python code-point indices.

---

# 28. Regression fixture после изменения schema

Поскольку strict finding schema меняется, existing regression fixture надо обновить.

Каждый committed expected finding должен включать новые поля:

```text
full_rule_id
category_name
```

Fixture должен быть bound к trusted Java oracle через:

- byte hash;
- manifest;
- semantic case identity.

Expected output не должен участвовать в semantic input identity.

---

# 29. Differential corpus identity

Semantic identity должна зависеть от:

```text
text
exact profile state
```

Profile state должен включать:

```text
profile_id semantics
enabled rules
disabled rules
rule_config
checking level
enable_all_default_off
```

Лучше hash'ить canonical structured profile, а не только profile_id string.

Output Java/Python не должен влиять на identity.

---

# 30. Determinism

Corpus generation должен оставаться deterministic.

Сохранить:

```text
fixed seed
stable ordering
stable IDs
stable profile serialization
stable source hashes
stable JSON ordering where applicable
LF-normalized committed artifacts
```

Повторный build одного и того же source state должен давать одинаковые signatures.

---

# 31. Natural corpus

Existing natural corpus можно переиспользовать.

Не нужно скачивать заново только ради review ceremony, если:

```text
local source file exists
SHA-256 matches recorded provenance
metadata matches
```

Если corpus missing:

- допускается восстановить по документированному способу;
- hash должен совпасть;
- нельзя silently подменить source.

Natural text не должен попадать в production wheel.


---

# 32. Minimum campaign coverage после review-fix

Финальная кампания должна сохранять минимум:

```text
unique texts >= 8000

profile executions >= 12000

spelling-stress texts >= 2000

natural Russian blocks >= 2000

Unicode/non-BMP targeted executions >= 500
```

Текущие показатели выше минимума, поэтому review-fix не должен случайно существенно уменьшить coverage.

---

# 33. Rerun campaign обязателен

После изменения comparator нельзя просто пересчитать старый summary.

Нужно реально заново прогнать campaign через corrected comparator.

Причина:

раньше cases с:

```text
wrong full_rule_id
wrong category_name
```

могли потенциально пройти exact.

Поэтому старый:

```text
17388 / 17388 exact
```

не является доказательством для нового schema.

---

# 34. Что делать, если corrected comparator найдёт новые mismatch

Не маскировать.

Для каждого mismatch:

1. сохранить original case;
2. минимизировать;
3. воспроизвести Java;
4. воспроизвести Python;
5. определить слой:
   - tokenizer
   - sentence segmentation
   - tagger
   - disambiguation
   - grammar matcher
   - Java rule
   - speller
   - overlap filter
   - metadata/output projection
6. проверить pinned source;
7. исправить Python, если Java behavior валиден;
8. добавить regression;
9. rerun affected subset;
10. затем rerun full campaign.

Если это pinned upstream defect:

- source evidence;
- narrow fingerprint;
- explicit classification;
- никакого broad allowlist.

---

# 35. Allowlist policy

Обычные unexplained discrepancies:

```text
0
```

Ordinary allowlist:

```text
0 entries
```

Если появится genuinely unavoidable difference:

- case-specific;
- rule-specific;
- source-proven;
- documented;
- no wildcards;
- no category-wide bypass;
- no "ignore all message mismatches".

Но задача считается успешной только если ordinary unexplained mismatches = 0.

---

# 36. State isolation

Existing state-isolation evidence сохранить.

Нужно доказать, что repeated campaign checks не зависят от порядка запуска.

Особенно важно для:

- coherency rule;
- repeated-word rules;
- caches;
- speller configuration;
- enabled/disabled states;
- profile-local UserConfig;
- shared dictionary caches.

Профили не должны мутировать друг друга.

---

# 37. Production boundary

Task 0014 — development/test tooling.

Production package не должен:

- запускать Java;
- импортировать differential tools;
- открывать subprocess для oracle;
- использовать localhost/network;
- включать external corpora;
- включать Java source/helper;
- включать `.oracle_cache`;
- включать trusted JAR.

Wheel isolation должен снова пройти.

---

# 38. Required focused tests

Добавить или расширить tests.

## Comparator

```text
full_rule_id exact
full_rule_id mismatch

category_name exact
category_name mismatch

same base XML ID but different subrule => mismatch

finding multiplicity preserved

finding order preserved

suggestion order preserved

suggestion duplicates preserved

new Finding schema JSON round-trip
```

## Profile / level

```text
DEFAULT profile serialization deterministic

PICKY profile serialization deterministic

DEFAULT signature != PICKY signature

same text DEFAULT/PICKY => different semantic identity

Java helper invokes correct pinned level

Python uses same production level filter

DEFAULT drops picky result

PICKY retains picky result
```

## Config sensitivity

```text
long sentence targeted cases > 0
long sentence Java delta > 0

long paragraph targeted cases > 0
long paragraph Java delta > 0

filler targeted cases > 0
filler Java delta > 0

speller conf_ru_Value targeted cases > 0
speller Java delta > 0

for every targeted case:
configured Java == configured Python

required profile with zero Java delta => validation failure
```

## Manifest / summary

```text
new strict fields declared

new mismatch kinds recognized

totals arithmetic exact

per-profile totals cover all executions

per-stratum totals cover all executions

config-sensitivity accounting exact

comparable exact + non-exact == comparable

final non-exact == 0

unexplained ordinary discrepancies == 0
```

## Regression

```text
all committed regression cases reproduce pinned Java

Python equals pinned Java strict schema

fixture semantic identities unique

fixture byte hash bound in manifest
```

---

# 39. Existing accepted tests must remain green

Не ломать принятые evidence layers прошлых задач.

Особенно:

```text
Task 0011 Java-rule oracle parity
Task 0012 spelling/rules oracle parity
Task 0013 upstream contract parity
Russian grammar examples
variant inventory
tagger
disambiguator
synthesizer
Morfologik
wheel isolation
```


---

# 40. Current CI reference

Старый Task-0014 implementation CI:

```text
Actions run:
32447074657

tested SHA:
e8c7d2a027bb651d583bee9fa1cd532ed5c4a1d0
```

Он прошёл:

```text
Python 3.10 success
Python 3.12 success

1120 passed
0 failed
0 errors
0 skipped
```

Но это только historical reference.

Review-fix добавит tests, поэтому final count должен быть выше или как минимум соответствовать реально собранному набору.

Не хардкодить 1120.

---

# 41. Особенность current main

После успешного CI был создан docs commit:

```text
f5cd5fb630c71ba3ee251471aaceaee4134d4522
```

Он записал номер CI run родителя.

Из-за этого:

```text
current main SHA != tested SHA
```

В review-fix эту ошибку процесса нельзя повторить.

---

# 42. Правильный final commit / CI workflow

После всех изменений:

1. закончить production code;
2. закончить tools;
3. закончить fixtures;
4. закончить manifests;
5. закончить report;
6. запустить local full pytest;
7. создать **один финальный review-fix commit**;
8. push в `main`;
9. записать его SHA как `FINAL_SHA`;
10. после push ничего не менять;
11. дождаться GitHub Actions для `FINAL_SHA`;
12. проверить обе matrix jobs;
13. **не делать новый docs commit после CI**;
14. CI run ID и URL указать только в final handoff сообщении.

---

# 43. Exact-SHA CI gate

Для обеих jobs должно быть доказано:

```text
git rev-parse HEAD == GITHUB_SHA == FINAL_SHA
```

Matrix:

```text
Python 3.10
Python 3.12
```

Для обеих:

```text
conclusion = success
0 failed
0 errors
0 skipped
```

JUnit zero-skip gate должен оставаться.

---

# 44. Full local validation

Перед финальным commit:

```bash
python -m pytest
```

Требование:

```text
0 failed
0 errors
0 skipped
```

Также focused Task-0014 tests.

Если есть отдельные commands Task 0014:

```bash
python -m tools.differential_corpus_0014 validate-oracle
python -m tools.differential_corpus_0014 build
python -m tools.differential_corpus_0014 run
python -m tools.differential_corpus_0014 summarize
python -m tools.differential_corpus_0014 minimize
python -m tools.differential_corpus_0014 verify-regressions
python -m tools.differential_corpus_0014 state-isolation
```

Проверь actual CLI текущей реализации перед запуском.

---

# 45. Suggested implementation order

Чтобы не устроить несколько полных прогонов корпуса зря, работать в таком порядке.

## Step 1

Изучить текущие файлы.

Ничего не менять до понимания:

- Finding schema;
- Java protocol fields;
- Profile;
- semantic identity;
- campaign result format;
- summary;
- regression fixture format.

## Step 2

Исправить comparator schema:

```text
full_rule_id
category_name
```

Добавить mismatch kinds и focused tests.

Пока не запускать full campaign.

## Step 3

Добавить checking level в Profile/Java/Python.

Focused DEFAULT/PICKY tests.

## Step 4

Добавить real spelling UserConfig profile:

```text
conf_ru_Value
```

## Step 5

Добавить deterministic config-sensitive targeted cases.

Сделать fail-closed sensitivity validator.

## Step 6

Обновить schema/version constants при необходимости.

Если corpus semantic format меняется, generator/schema version должен это отражать.

## Step 7

Запустить focused Task-0014 tests.

## Step 8

Запустить corrected full differential campaign.

## Step 9

Разобрать новые mismatches, если появились.

Не переходить дальше с non-exact cases.

## Step 10

Regenerate:

- regressions;
- manifests;
- summary;
- report;
- compatibility metadata.

## Step 11

Full pytest.

Wheel isolation.

## Step 12

Final commit → push → exact-SHA CI.

---

# 46. Файлы, которые вероятно изменятся

Минимально ожидаются:

```text
tools/differential_lt.py
tools/differential_batch_oracle_0014.py
tools/differential_corpus_0014.py
tools/DifferentialCorpusOracle0014.java
```

Возможно production API:

```text
src/pylat_ru/...
```

если checking level пока нельзя передать в public check.

Тесты:

```text
tests/unit/test_differential_comparator_0014.py
tests/unit/test_differential_corpus_generator_0014.py
tests/unit/test_differential_manifest_0014.py
tests/unit/test_differential_regressions_0014.py
tests/unit/test_picky_level_filter_0014.py
```

И новые tests при необходимости.

Artifacts:

```text
compat/differential_corpus_0014_manifest.json
compat/differential_summary_0014.json
compat/differential_state_isolation_0014.json
compat/differential_upstream_defects_0014.json
compat/differential_allowlist_0014.json
compat/oracle_manifest.json
compat/compatibility.json

tests/fixtures/differential_regressions_0014.json

reports/0014_differential_corpus.md
```


---

# 47. Что запрещено делать

Не надо:

- начинать Task 0015;
- реализовывать `RussianConfusionProbabilityRule`;
- менять pinned LanguageTool commit;
- использовать другую LT version;
- ослаблять comparator;
- сортировать suggestions;
- превращать finding sequence в set;
- игнорировать full rule ID;
- игнорировать category name;
- считать config profile покрытым только потому, что он существует;
- вручную прописывать "100%" в summary;
- подменять natural corpus;
- добавлять Java в production dependency;
- использовать network oracle;
- делать broad allowlist;
- переписывать уже принятую grammar/spelling архитектуру без доказанной необходимости;
- делать docs commit после final CI.

---

# 48. Acceptance criteria

Task 0014 review-fix можно считать выполненным только если выполнены все условия ниже.

## Strict finding parity

```text
rule_id                     PASS
full_rule_id                PASS
category_id                 PASS
category_name               PASS
message                     PASS
short_message               PASS
UTF-16 span                 PASS
suggestion content          PASS
suggestion order            PASS
suggestion duplicates       PASS
URL                         PASS
finding multiplicity        PASS
finding order               PASS
```

## Levels

```text
DEFAULT semantics            PASS
PICKY semantics              PASS
Java/Python level parity     PASS
```

## Config sensitivity

Для каждого:

```text
LongSentence maxWords
LongParagraph maxWords
FillerWords minPercent
Speller conf_ru_Value
```

обязательно:

```text
targeted cases > 0
Java observable delta > 0
Python corresponding delta > 0
Java/Python exact on targeted cases
```

## Differential corpus

```text
unique texts >= 8000
profile executions >= 12000

comparable non-exact ordinary cases = 0
unexplained ordinary discrepancies = 0
ordinary allowlist entries = 0
```

## Java oracle errors

Разрешены только явно доказанные pinned upstream defects.

Не смешивать с compatibility mismatches.

## Compatibility accounting

Должно остаться:

```text
XML source rules:       892 / 892
grammar examples:       2446 / 2446
compiled variants:      907 / 907
ordinary Java rules:    23 / 23
XML filters:            7 / 7
```

## Deferred LM

```text
RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED
```

## Tests

```text
0 failed
0 errors
0 skipped
```

Python 3.10 и 3.12.

## Production boundary

```text
wheel Java-free
corpus-free
oracle-free
network-free
```

---

# 49. Финальный отчёт исполнителя

В финальном сообщении обязательно вернуть конкретные значения.

Шаблон:

```text
Task 0014 review-fix final verification

review baseline:
f5cd5fb630c71ba3ee251471aaceaee4134d4522

final main SHA:
<SHA>

review-fix implementation commit:
<SHA>

Pinned LT:
e807fcde6a6506191e1470744d2345da28c26be6

Strict finding fields:
rule_id: PASS
full_rule_id: PASS
category_id: PASS
category_name: PASS
message: PASS
short_message: PASS
UTF-16 span: PASS
suggestion content/order/duplicates: PASS
URL: PASS
finding order/multiplicity: PASS

Checking levels:
DEFAULT: PASS
PICKY: PASS

Config-sensitive whole-pipeline evidence:

long sentence:
targeted <N>
observable Java deltas <N>
observable Python deltas <N>
Java/Python exact <N>/<N>

long paragraph:
targeted <N>
observable Java deltas <N>
observable Python deltas <N>
Java/Python exact <N>/<N>

filler:
targeted <N>
observable Java deltas <N>
observable Python deltas <N>
Java/Python exact <N>/<N>

speller conf_ru_Value:
targeted <N>
observable Java deltas <N>
observable Python deltas <N>
Java/Python exact <N>/<N>

Differential corpus:
unique texts: <N>
profile executions: <N>
comparable cases: <N>
exact comparable cases: <N>
non-exact comparable cases: 0

Java findings:
<N>

Python comparable findings:
<N>

Java oracle error cases:
<N>

Confirmed pinned-upstream defect cases:
<N>

Unexplained ordinary discrepancies:
0

Ordinary allowlist entries:
0

Committed minimized regressions:
<N>

Full pytest:
<N> passed
0 failed
0 errors
0 skipped

Wheel isolation:
PASS

Actions run ID:
<ID>

Actions run URL:
<URL>

Actions head_sha:
<SHA>

Python 3.10:
<N> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <SHA>

Python 3.12:
<N> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <SHA>

RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED

Task 0015:
not started

Repository changes after verified CI:
none

FINAL:
READY FOR REVIEW
```

---

# 50. Stop condition

После выполнения review-fix:

```text
STOP
```

Не начинать Task 0015.

Не делать дополнительные "улучшения на будущее".

Не менять unrelated production code.

Не пушить новый commit после exact-SHA CI.

Если full campaign после исправления comparator показывает хотя бы один unexplained ordinary non-exact case:

```text
Task 0014 ещё не закончен.
```

Сначала исправить/классифицировать mismatch и заново подтвердить parity.
