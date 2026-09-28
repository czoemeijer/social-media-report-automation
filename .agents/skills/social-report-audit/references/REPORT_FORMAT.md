# Report Structure & Writing Standards

This document defines the standardized Markdown report formats and analytical writing guidelines for the `social-report-audit` skill.

---

## 1. Analytical Integrity & Tone Guidelines

Reports must maintain an objective, empirical tone. Every sentence must fall into one of four distinct categories:

1. **FACT:** A directly observed, extracted metric from a verified source.
   - *Good:* „Příspěvek dosáhl 15 020 zobrazení a 398 reakcí."
2. **DERIVED METRIC:** A deterministic calculation using explicitly stated formulas.
   - *Good:* „Vypočtená míra zapojení (Calculated ER by Reach) činí 3,80 % při součtu 437 známých interakcí a dosahu cca 11 500."
3. **INTERPRETATION:** A cautious analytical observation directly supported by numbers.
   - *Good:* „Míra uložení u Reelu dosáhla 1,47 %, což značí nadprůměrnou referenční hodnotu receptu pro publikum."
   - *Avoid:* „Obsah byl pro diváky neuvěřitelně atraktivní a potvrdil geniální strategii."
4. **RECOMMENDATION / HYPOTHESIS:** A concrete, testable proposal for subsequent campaigns.
   - *Good:* „Doporučujeme u budoucích receptových videí otestovat výzvu k akci (CTA) v popisku zaměřenou na komentáře pro zvýšení konverzace."
   - *Avoid:* „Je nutné okamžitě změnit celý obsahový plán."

---

## 2. Report Templates

### Template A: Single Content Asset / Account Overview

```markdown
# Report výkonu: [Název profilu / Klienta] – [Období / Datum]

## 1. Přehled hlavních metrik

| Metrika | Aktuální hodnota | Předchozí období | Rozdíl / Trend | Poznámka |
| :--- | :--- | :--- | :--- | :--- |
| **Views (Zobrazení / Přehrání)** | [hodnota] | [předchozí] | [trend %] | Celkový počet přehrání |
| **Reach (Dosah / Oslovené účty)** | [hodnota] | [předchozí] | [trend %] | Unikátní účty v rámci assetu |
| **Likes (To se mi líbí / Reakce)** | [hodnota] | [předchozí] | [trend %] | Přímé pozitivní reakce |
| **Comments (Komentáře)** | [hodnota] | [předchozí] | [trend %] | Komentáře pod výstupem |
| **Shares / Reposts** | [hodnota] | [předchozí] | [trend %] | Sdílení dalším uživatelům |
| **Saves (Uložení)** | [hodnota] | [předchozí] | [trend %] | Uložení do záložek |
| **Engagement rate** | [hodnota %] | [předchozí] | [trend p.b.] | Calculated ER by Reach |

### Doplňkové ukazatele
- **Známé interakce (Known Engagement Actions):** [Likes + Comments + Shares + Saves]
- **Platformou reportované interakce:** [Hodnota z UI, pokud se liší, nebo "Odpovídá součtu známých interakcí"]
- **Míra uložení (Saves / Reach):** [X,XX %]
- **Poměr komentářů k lajkům (Comments / Likes):** [X,XX %]

---

## 2. Věcná interpretace výkonu
[2–4 věcné věty hodnotící výkon bez superlativů. Opírejte se pouze o doložená data.]

---

## 3. Porovnání s předchozím obdobím
[Stručný odstavec porovnávající trendy, nebo explicitní konstatování: *Data za předchozí období nebyla poskytnuta.*]

---

## 4. Pozorování a doporučení
1. **[Pozorování 1]:** [Faktické zjištění podložené čísly]
2. **[Doporučení 2]:** [Konkrétní akční krok k optimalizaci formátu, obsahu či publikace]
3. **[Doporučení 3]:** [Doporučení pro další období (např. CTA, testování formátu)]
```

---

### Template B: Multi-Creator Campaign Report

```markdown
# Report výkonu: [Název kampaně / Klienta] – [Období]

## 1. Souhrn za celou kampaň

| Metrika | Aktuální hodnota | Poznámka k agregaci |
| :--- | :--- | :--- |
| **Views (Zobrazení celkem)** | [Součet zobrazení] | Součet všech video přehrání a zobrazení |
| **Sum of Content Reach** | [Součet dosahů] | **Součet dosahů jednotlivých výstupů (obsahuje překryv publika)** |
| **Likes (Reakce celkem)** | [Součet likes] | Přímé reakce napříč výstupy |
| **Comments (Komentáře celkem)**| [Součet comments] | Komentáře celkem |
| **Shares / Reposts** | [Součet shares] | Sdílení celkem |
| **Saves (Uložení celkem)** | [Součet saves] | Uložení celkem |
| **Vážený Engagement Rate** | [X,XX %] | Vážený průměr: Celkové známé interakce / Součet dosahů $\times 100$ |

> **Upozornění k dosahu:** Hodnota dosahu představuje součet dosahů jednotlivých výstupů a nelze ji interpretovat jako unikátní čistý zásah kampaně bez dedupikovaných dat z platformy.

---

## 2. Výkon podle jednotlivých tvůrců

### A) [Jméno tvůrce 1]
[Tabulka metrik rozdělená podle formátů (Reel, Story) a platforem (IG, FB) + doplňkové ukazatele a poznámky k čitelnosti dat]

### B) [Jméno tvůrce 2]
[...]

---

## 3. Srovnání tvůrců a interpretace
[Věcné zhodnocení relativní efektivity jednotlivých tvůrců z hlediska dosahu, uložení a míry zapojení.]

---

## 4. Strategická doporučení pro klienta
1. **[Doporučení 1]:** ...
2. **[Doporučení 2]:** ...
3. **[Doporučení 3]:** ...
```
