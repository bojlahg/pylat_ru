# LanguageTool Russian Tagset Specification

## 1. Overview

LanguageTool's Russian pipeline uses a part-of-speech (POS) and morphological feature tagset originally converted and adapted from the [AOT project](http://www.aot.ru/) (`morphs.mrd` / `RusSrc`) by Yakov Reztsov.

The canonical tag vocabulary is defined in:
- `third_party/languagetool/.../resource/ru/tags_russian.txt` (exact tag listing)
- `third_party/languagetool/.../resource/ru/tagset.txt` (descriptive grammar notes and AOT ancode conversion tables)

This document describes the tagset structure, feature atoms, empty colon components, and guidelines for downstream grammar matching.

---

## 2. Quantitative Inventory

Analysis of the pinned `tags_russian.txt` reveals:

- **Total raw lines**: 1,201
- **Unique stripped tags**: 1,200
- **Duplicate occurrences**: 1 (`NN:Inanim:Masc:PL:P` appears twice; line 462 has trailing spaces `"NN:Inanim:Masc:PL:P  "`, line 463 is clean)
- **Tags with empty colon components**: 154 (12.8% of all tags)
- **Coarse POS prefixes**: 19
- **Distinct feature atoms**: 62

---

## 3. Coarse POS Prefixes (19)

| POS Prefix | Description | Russian Term | Example |
| :--- | :--- | :--- | :--- |
| **`NN`** | Noun | Существительное | `NN:Inanim:Masc:Sin:Nom`, `NN:Name:Fem:Sin:R` |
| **`VB`** | Verb | Глагол | `VB:Real:Sin:P3`, `VB:INF:` |
| **`ADJ`** | Adjective | Прилагательное | `ADJ:Posit:Fem:Nom`, `ADJ:Short:PL` |
| **`ADV`** | Adverb | Наречие | `ADV` |
| **`DPT`** | Adverbial Participle (Gerund) | Деепричастие | `DPT:Past:`, `DPT:Real:` |
| **`PT`** | Participle | Причастие | `PT:Real:DST:Fem:Nom`, `PT:Past:STR:Masc:Nom` |
| **`PT_Short`** | Short Participle | Краткое причастие | `PT_Short:Past::STR:Masc` |
| **`ABR`** | Abbreviation | Аббревиатура | `ABR`, `ABR:Fem`, `ABR:PL` |
| **`PNN`** | Pronoun | Местоимение | `PNN:Masc:Sin:Nom`, `PNN:PL:Nom` |
| **`PRDC`** | Predicative | Предикатив / категория состояния | `PRDC` |
| **`PREP`** | Preposition | Предлог | `PREP` |
| **`CONJ`** | Conjunction | Союз | `CONJ` |
| **`PARTICLE`** | Particle | Частица | `PARTICLE` |
| **`PARENTHESIS`** | Parenthesis / Intro word | Вводное слово | `PARENTHESIS` |
| **`INTERJECTION`**| Interjection | Междометие | `INTERJECTION` |
| **`Num`** | Numeral | Числительное | `Num:Nom`, `Num:Masc:Nom` |
| **`NumC`** | Countable Numeral | Числительное количественное | `NumC:Nom`, `NumC:PL:R` |
| **`Ord`** | Ordinal Numeral | Числительное порядковое | `Ord:Fem:Nom` |
| **`Misc`** | Miscellaneous / Special | Разное | `Misc:Lat` |

---

## 4. Feature Atoms (62)

The 62 feature atoms occurring across all tags are categorized as follows:

### 4.1 Animacy
- `Anim`: Animated (одушевлённое)
- `Inanim`: Inanimated (неодушевлённое)
- `Inanimanim`: Dual animated/inanimated (одушевлённое + неодушевлённое)

### 4.2 Gender
- `Masc`: Masculine (мужской род)
- `Fem`: Feminine (женский род)
- `Neut`: Neuter (средний род)

### 4.3 Number
- `Sin`: Singular (единственное число)
- `PL`: Plural (множественное число)

### 4.4 Case
- `Nom`: Nominative (именительный)
- `R`: Genitive (родительный)
- `2R`: Second genitive / partitive (второй родительный / количественно-отделительный)
- `D`: Dative (дательный)
- `V`: Accusative (винительный)
- `T`: Instrumental (творительный)
- `P`: Prepositional / Locative (предложный)
- `2P`: Second prepositional / locative (второй предложный / местный)
- `Z`: Vocative (звательный)

### 4.5 Tense & Verb Forms
- `INF`: Infinitive (инфинитив)
- `Past`: Past tense (прошедшее время)
- `Real`: Present tense (настоящее время)
- `Fut`: Future tense (будущее время)
- `IMP`: Imperative (повелительное наклонение)
- `bezl`: Impersonal verb (безличный глагол)

### 4.6 Person
- `P1`: 1st person (1 лицо)
- `P2`: 2nd person (2 лицо)
- `P3`: 3rd person (3 лицо)

### 4.7 Aspect & Transitivity
- `IMPFV`: Imperfective aspect (несовершенный вид)
- `PFV`: Perfective aspect (совершенный вид)
- `2PFV`: Biaspectual (двувидовой)
- `TRANS`: Transitive (переходный)
- `INTR`: Intransitive (непереходный)

### 4.8 Voice (Participles)
- `DST`: Active voice (действительное причастие)
- `STR`: Passive voice (страдательное причастие)

### 4.9 Adjective / Degree / Proper Noun Markers
- `Short`: Short form (краткая форма)
- `Posit`: Positive degree (положительная степень)
- `Comp`: Comparative degree (сравнительная степень)
- `Sup`: Superlative degree (превосходная степень)
- `MPR`: Possessive adjective-pronoun (притяжательное прилагательное-местоимение)
- `Name`: Given name (имя собственное)
- `Patr`: Patronymic (отчество)
- `Fam`: Surname (фамилия)
- `Talk`: Colloquial / spoken form (разговорная форма)

---

## 5. Critical Losslessness Rules

LanguageTool's XML grammar rules (`grammar.xml`) and disambiguation rules match POS tag strings via regular expressions and exact strings. Therefore:

1. **`raw` String is Authoritative**: Never replace raw tags with custom enums or reformatted strings.
2. **Preserve Empty Colon Slots**:
   - `VB:INF:` has a trailing empty component (`parts=('VB', 'INF', '')`).
   - `NN::Masc:PL:Nom` has an empty component at index 1 (`parts=('NN', '', 'Masc', 'PL', 'Nom')`).
   - `DPT:Past:` has a trailing empty component (`parts=('DPT', 'Past', '')`).
   - `PT_Short:Past::STR:Fem` has an empty slot at index 2 (`parts=('PT_Short', 'Past', '', 'STR', 'Fem')`).
   Normalizing away or collapsing `::` into single colons breaks regex pattern matching like `postag="VB:INF:.*"`.
3. **No Feature Reordering**: Preserve the exact sequence of components as emitted by the binary dictionary.
