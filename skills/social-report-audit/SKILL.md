---
name: social-report-audit
description: >-
  Aktivuj tento skill kdykoliv uživatel zmíní "audit reportu", "vytvoř report", požádá o klientský report pro sociální sítě (Instagram, Facebook apod.), vloží sadu metrik nebo dodá složky se screenshoty statistik (i s rozpadem podle jednotlivých tvůrců/creatorů). Zajišťuje extrakci dat ze screenshotů, mapování na standardní metriky, validaci, agregaci, výpočet sekundárních ukazatelů a vygenerování věcného markdown reportu.
---

# Social Media Report & Audit Skill (`social-report-audit`)

Tento skill slouží k auditování a vytváření pravidelných, profesionálních a konzistentně strukturovaných reportů pro klienty na sociálních sítích (Instagram, Facebook). Umožňuje zadat aktuální metriky ve volném/zkratkovitém formátu, nebo je vytáhnout přímo ze screenshotů statistik, a okamžitě vygenerovat hotový analytický výstup – včetně rozpadu podle jednotlivých tvůrců.

---

## 🎯 Spouštěcí podmínky (Triggery)

Aktivuj tento skill automaticky, pokud:

- Uživatel zmíní fráze jako **„audit reportu“**, **„vytvoř report“**, **„report pro klienta“**.
- Uživatel zadá sadu metrik obsahující zobrazení, dosah, interakce či engagement rate (i zkratkovitě).
- Uživatel vloží složku/soubory se screenshoty statistik Instagramu nebo Facebooku ke zpracování.

---

## 📁 Struktura vstupních dat (při práci se soubory/screenshoty)

Skill očekává vstupní data organizovaná takto:

```
[Název reportu]/
  ├── [Tvůrce 1]/
  │     ├── screenshot_insights_1.png
  │     ├── screenshot_insights_2.png
  │     └── ...
  ├── [Tvůrce 2]/
  │     ├── screenshot_insights_1.png
  │     └── ...
  └── ...
```

- **Název nadřazené složky** = název reportu / kampaně / klienta (použij v nadpisu výsledného reportu).
- **Každá podsložka** = jeden tvůrce/creator – jeho jméno použij jako identifikátor v tabulce.
- Uvnitř podsložky tvůrce mohou být screenshoty statistik (Instagram Insights, Facebook/Meta Business Suite), případně i .csv/.xlsx exporty.
- Pokud uživatel zadá data ručně (bez souborů), přeskoč extrakci ze screenshotů a použij přímo zadaná čísla.

---

## 📊 Pevná struktura standardních metrik

Skill povinně rozpoznává a mapuje vstupní data (ať už textová nebo ze screenshotů) na následující standardní metriky:

1. **Views (Zobrazení / Přehrání)**
2. **Saves (Uložení)**
3. **Reach (Dosah / Oslovené účty)** – často zadáváno s předponou `cca X` nebo `~X`
4. **Likes (To se mi líbí / Reakce)**
5. **Comments (Komentáře)**
6. **Shares / reposts (Sdílení a přeposlání)**
7. **Engagement rate (Míra zapojení v %)** – často zadáváno jako `cca X %`

---

## 📸 Extrakce dat ze screenshotů (Instagram / Facebook)

### Rozpoznávání zdroje screenshotu

Před extrakcí dat rozpoznej, ze které platformy screenshot pochází, podle vizuálních prvků UI:
- **Instagram Insights** – sekce „Zobrazení", „Interakce s obsahem", „Návštěvy profilu", zaoblené karty, Instagram styl.
- **Facebook Insights / Meta Business Suite** – modré UI prvky, terminologie „Dosah", „Interakce", „Zhlédnutí".

### Mapování terminologie platforem na standardní metriky

| Zobrazeno na screenshotu (CZ/EN) | Namapuj na standardní metriku |
|---|---|
| Zobrazení / Views / Přehrání | Views |
| Uložení / Saves | Saves |
| Dosah / Reach / Oslovené účty | Reach |
| Líbí se mi / Likes / Reakce | Likes |
| Komentáře / Comments | Comments |
| Sdílení / Přeposlání / Shares | Shares / reposts |
| Míra zapojení / Engagement rate | Engagement rate |

### Pravidla pro čtení ze screenshotů

1. **Čti čísla přesně tak, jak jsou zobrazená** – včetně zkratek (např. „11,5 tis." = 11 500; „15,02 tis." = 15 020).
2. **Pokud je číslo částečně useknuté, rozmazané nebo nejisté**, neodhaduj – označ metriku jako nejistou a v reportu na to upozorni („hodnota nebyla čitelná, ověřte prosím ručně").
3. **Pokud jeden tvůrce dodal víc screenshotů ze stejného příspěvku** (různé záložky statistik), slouč je do jedné sady metrik pro daný příspěvek, nikde nepočítej duplicitně.
4. **Pokud screenshot obsahuje víc příspěvků najednou** (přehledová obrazovka), rozděl data podle jednotlivých příspěvků, pokud jsou rozlišitelné, jinak agreguj jako „souhrn za období".
5. **Pokud jeden tvůrce má víc příspěvků/screenshotů celkem**, sečti/agreguj hodnoty za daného tvůrce (u ER počítej vážený průměr podle reach, ne prostý průměr).

---

## ⚙️ Postup zpracování dat a logika výpočtů

### 1. Parsování a mapování

- Přijmi vstupní čísla v libovolném volném či zkráceném formátu (např. `views 15.02k, saves 9, reach cca 11.5k, likes 398, comm 28, shares 2, ER 3.8%`) nebo je vytáhni ze screenshotů dle pravidel výše.
- Namapuj hodnoty na 7 pevných standardních metrik.
- **Detekce chybějících metrik:** Pokud některá z klíčových metrik chybí nebo je nečitelná, explicitně na to v reportu upozorni a doplňkové výpočty závislé na této metrice označ jako nedostupné.

### 2. Výpočet doplňkových ukazatelů a audit dat

- **Celkové interakce:** $\text{Likes} + \text{Comments} + \text{Shares/reposts} + \text{Saves}$
- **Audit Engagement Rate (vypočteno z Reach):**
  $$
  \text{ER (z Reach)} = \frac{\text{Celkové interakce}}{\text{Reach}} \times 100
  $$
  *Pokud se zadané ER liší od vypočteného, uveď v poznámce kontrolní přepočet.*
- **Saves / Reach ratio (%):** $\frac{\text{Saves}}{\text{Reach}} \times 100$ *(indikátor hodnoty a uložitelnosti obsahu)*
- **Comments / Likes ratio (%):** $\frac{\text{Comments}}{\text{Likes}} \times 100$ *(indikátor hloubky diskuse a komunitní odezvy)*

### 3. Porovnání s předchozím obdobím (pokud je k dispozici)

- Pokud jsou k dispozici historická data:
  $$
  \text{Trend (\%)} = \frac{\text{Aktuální} - \text{Předchozí}}{\text{Předchozí}} \times 100
  $$
- Vyjádři změnu s vizuálním označením směru (např. `+15,4 % ↗` nebo `-8,2 % ↘`).

---

## 📝 Struktura výstupního Markdown reportu

### A) Report za jednoduchou sadu metrik (bez rozpadu na tvůrce)

```markdown
# Report výkonu: [Název profilu / Klienta] – [Období / Datum]

## 1. Tabulka metrik

| Metrika | Aktuální hodnota | Předchozí období | Rozdíl / Trend | Poznámka |
| :--- | :--- | :--- | :--- | :--- |
| **Views (Zobrazení)** | ... | [předchozí] | [trend %] | Celkový počet zobrazení |
| **Reach (Dosah)** | ... | [předchozí] | [trend %] | Unikátní oslovené účty |
| **Likes (To se mi líbí)** | ... | [předchozí] | [trend %] | Přímé pozitivní reakce |
| **Comments (Komentáře)** | ... | [předchozí] | [trend %] | Komentáře pod příspěvky |
| **Shares / reposts** | ... | [předchozí] | [trend %] | Sdílení dalším uživatelům |
| **Saves (Uložení)** | ... | [předchozí] | [trend %] | Uložení do záložek |
| **Engagement rate** | ... | [předchozí] | [trend %] | Vypočteno z Reach |

### Doplňkové ukazatele
- **Celkový počet interakcí:** [Součet]
- **Míra uložení (Saves / Reach):** [X,XX %]
- **Poměr komentářů k lajkům (Comments / Likes):** [X,XX %]

---

## 2. Věcná interpretace výkonu
[2–4 věcné věty hodnotící výkon bez prázdných superlativů.]

## 3. Porovnání s předchozím obdobím
[Stručný odstavec, nebo: *Data za předchozí období nebyla poskytnuta.*]

## 4. Doporučení a pozorování pro klienta
1. **[Pozorování 1]:** ...
2. **[Doporučení 2]:** ...
3. **[Doporučení 3]:** ...
```

### B) Report se screenshoty a rozpadem podle tvůrců

```markdown
# Report výkonu: [Název reportu] – [Období]

## Souhrn za všechny tvůrce
[souhrnná tabulka metrik + doplňkové ukazatele, agregováno přes všechny tvůrce]

## Výkon podle tvůrců

### [Jméno tvůrce 1]
[tabulka metrik tohoto tvůrce + poznámky k nečitelným/chybějícím hodnotám]

### [Jméno tvůrce 2]
[tabulka metrik tohoto tvůrce]

...

## Interpretace a doporučení
[Napříč tvůrci – kdo performoval nejlépe/nejhůř a proč, na základě dat. Konkrétní, věcné, opřené o čísla.]
```

---

## ✍️ Styl výstupu a komunikační tón

- **Věcný, profesionální, analytický.**
- **Žádné nepodložené superlativy** (vyvaruj se frází jako *„skvělý výsledek"*, *„famózní úspěch"* – nech mluvit konkrétní čísla a metriky).
- Používej spisovnou češtinu a standardní české formátování čísel (oddělovač tisíců mezerou `15 020`, desetinná čárka `3,80 %`).

---

## 🧪 Vzorová testovací data

```text
Views: 15 020
Saves: 9
Reach: cca 11 500
Likes: 398
Comments: 28
Shares / reposts: 2
Engagement rate: cca 3,80 %
```

### Očekávaný kontrolní výpočet:

- **Celkové interakce:** $398 + 28 + 2 + 9 = 437$
- **Kontrola ER:** $\frac{437}{11 500} \times 100 = 3,80 \%$
- **Saves / Reach:** $\frac{9}{11 500} \times 100 = 0,08 \%$
- **Comments / Likes:** $\frac{28}{398} \times 100 = 7,04 \%$
