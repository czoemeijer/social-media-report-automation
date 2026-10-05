---
name: story-series-extract
description: Extract and structure performance metrics from Instagram/Facebook Story sequence screenshots for creator and campaign summaries. Outputs clean, standardized series metrics (Total views with breakdown, initial reach, profile visits, interactions breakdown, drop-off rate, and poll/quiz results) without complex calculations.
---

# Story Series Extract Skill (`story-series-extract`)

This skill extracts and structures performance metrics from Instagram or Facebook Story series/sequences for influencer marketing campaigns and creator reports.

It is designed for **fast, straightforward, deterministic extraction** directly from screenshot evidence without unnecessary calculations, statistical guesswork, or complex audit formulas.

---

## 1. Activation Triggers

Use this skill when:
- The user provides screenshots of Instagram Story insights (Overview, Navigation, Profile Activity, Stickers/Polls).
- The user asks for a summary of a Story series ("Souhrnný výkon série").
- The user requests extraction of creator campaign story metrics (Views breakdown, Initial Reach, Interactions breakdown, Drop-off rate, Poll/Quiz results).

---

## 2. Standardized Output Format

The output must always follow this exact structure:

```markdown
Souhrnný výkon série
Zobrazení: {Celkem} ({Story 1} + {Story 2} + ...)
Reach: {Reach 1. storky} - maximální dosah na začátku série
Návštěvy profilu: {Celkem}
Interakce: {Celkem} ({Story 1} + {Story 2} + ...)
Míra opuštění: {Míra}%
Výsledek ankety/kvízu: {Výsledek}
```

Optional context header when campaign or creator details are available:
```markdown
### Kampaň: [Název kampaně]
- **Tvůrce:** [Jméno / @handle tvůrce]
- **Počet stories v sérii:** [Počet]
```

---

## 3. Extraction & Metric Rules

Extract values directly from native Instagram Story Insights cards:

### 1. Zobrazení (Views)
- **Definice:** Celkový počet zobrazení všech stories v dané sérii a rozpad po jednotlivých střípcích.
- **Zdroj:** Karta *Overview -> Views* nebo číslo v kruhovém grafu zobrazení.
- **Formát:** `{Celková_zobrazení} ({Zobrazení_Story_1} + {Zobrazení_Story_2} + ...)`
- **Příklad:** `600 (320 + 280)` nebo `840 (450 + 390)`

### 2. Reach (Dosah)
- **Definice:** Dosah (počet unikátních účtů / Viewers) první story v sérii, která reprezentuje maximální zásah na začátku sekvence.
- **Zdroj:** Karta *Viewers / Accounts reached* na **1. střípku** série.
- **Formát:** `{Reach_Story_1} - maximální dosah na začátku série`
- **Příklad:** `250 - maximální dosah na začátku série` nebo `380 - maximální dosah na začátku série`

### 3. Návštěvy profilu (Profile visits)
- **Definice:** Celkový počet prokliků / návštěv profilu ze všech střípků série.
- **Zdroj:** Sekce *Profile activity -> Profile visits*.
- **Formát:** `{Celkový_součet}` (pokud je všude 0, uvést `0`; pokud více než 0 na více střípcích, lze uvést součet a rozpad).
- **Příklad:** `6` nebo `0`

### 4. Interakce (Interactions)
- **Definice:** Celkový počet interakcí (likes, replies, shares, sticker taps) a jejich rozpad po jednotlivých stories.
- **Zdroj:** Karta *Overview -> Interactions* (nebo součet jednotlivých interakcí z detailu střípku).
- **Formát:** `{Celkové_interakce} ({Interakce_Story_1} + {Interakce_Story_2} + ...)`
- **Příklad:** `20 (12 + 8)` nebo `25 (15 + 10)`

### 5. Míra opuštění (Drop-off Rate)
- **Definice:** Procento diváků, kteří opustili sérii mezi prvním a posledním střípkem (pokles zásahu sekvence).
- **Vzorec:**
  $$\text{Míra opuštění} = \frac{\text{Reach}_{\text{první storky}} - \text{Reach}_{\text{poslední storky}}}{\text{Reach}_{\text{první storky}}} \times 100$$
- **Formát čísla:** V české typografii s desetinnou čárkou a symbolem `%` (např. `16,0 %` nebo `20,0 %`).
- *Poznámka:* Pokud je k dispozici pouze údaj *Navigation -> Exited* (Opuštění), lze uvést také počet opuštění dle navigace.

### 6. Výsledek ankety/kvízu (Poll / Quiz Result)
- **Definice:** Procentuální nebo číselný výsledek z interaktivní nálepky ankety, kvízu nebo hlasování.
- **Zdroj:** Přímo ze screenshotu storky s anketou/kvízem nebo detailu nálepky.
- **Příklady:**
  - `88 % zvolilo správnou odpověď`
  - `ovocné 65 % / zeleninové 35 %`
  - `78 % pro možnost A / 22 % pro možnost B`
  - Pokud série neobsahuje anketu ani kvíz: `Nerelevantní (série neobsahuje anketu ani kvíz)`

---

## 4. Ověření duplicit, scrollů a re-screenshotů v čase (Anti-Duplicate Protocol)

> **Kritické pravidlo:** Počet screenshotů ve složce se **nerovná** počtu Stories. Tvůrci velmi často odevzdávají více screenshotů k téže jedné storce (např. posun obrazovky dolů pro zobrazení navigace nebo druhý snímek pořízený o několik hodin později pro doložení komentářů a diváků).

Před jakýmkoliv vyhodnocením počtu stories a metrik musí agent provést následující kontrolu:

1. **Vizuální shoda náhledu v horní liště (Story Tray):**
   - V horní liště Instagram Insights je zobrazen zásobník aktivních příběhů za 24 hodin.
   - Zkontrolujte miniaturu příběhu, u které je aktivní indikátor (fialový trojúhelníček / označení).
   - Pokud mají dva screenshoty **shodný náhled, stejnou grafiku, text či téma**, jedná se o **tu samou story**, nikoli o dvě různé stories ani o repost!
2. **Kontrola času pořízení a baterie (Status Bar):**
   - Vždy porovnejte čas v levém horním rohu telefonu (stavová lišta, např. `10:00` vs. `09:00` následující ráno) a stav baterie.
   - Pokud první snímek v čase `10:00` ukazuje u Story 1 zobrazení `500` a druhý snímek v čase `09:00` ukazuje `800 diváků`:
     - Jde o **re-screenshot stejné storky pořízený s časovým odstupem**, nejčastěji pro doložení komentářů nebo seznamu diváků.
     - **NIKDY** nezapočítávejte takový snímek jako další storku a **NIKDY** ho neklasifikujte jako „repost“.
3. **Rozlišení vertikálního scrollu od samostatné storky:**
   - Přehled jedné Instagram Story se skládá z několika částí (Horejšek: Views & graf, Střed: Interakce a Navigace, Spodek: Aktivita na profilu a Okruh uživatelů).
   - Pokud snímky ze stejného času zachycují různé výškové části stránky (např. `story_part_1.png`, `story_part_2.png`, `story_part_3.png`), jde o **vertikální scrolly téže 1 storky**.
4. **Časová konzistence pro výpočet série a Drop-off Rate:**
   - Pro výpočet souhrnných zobrazení a míry opuštění série (Story 1 → Story 2 → Story 3) použijte data z **jednoho časového okamžiku** (stejný čas pořízení ve stavové liště).
   - Nemíchejte průběžný stav Story 2 po 4 hodinách s finálním stavem Story 1 po 24 hodinách. Pokud je doložen finální dosah po 24 h, uveďte jej jako doplňující údaj k dané storce.
5. **Kritéria pro skutečný Repost:**
   - Storka je repostem Reelu/příspěvku **pouze tehdy**, pokud obsahuje nálepku přesdílení příspěvku s výzvou k přehrání a má **vlastní samostatný slot (miniaturu)** v horní liště příběhů.

---

## 5. Referenční vzor (Příklad ze vzorových dat)

### Vstupní data:
- **Story 1 (Úvodní slide):**
  - Views: 320
  - Viewers (Reach): 250
  - Interactions: 12 (Likes: 12)
  - Profile visits: 4
  - Navigation: Forwards: 210, Exited: 25, Back: 15
- **Story 2 (Interaktivní anketa – Ovocné vs. zeleninové smoothie):**
  - Views: 280
  - Viewers (Reach): 210
  - Interactions: 8 (Likes: 8)
  - Profile visits: 2
  - Navigation: Forwards: 190, Exited: 20, Back: 10
  - Anketa: ovocné 65 % / zeleninové 35 %

### Výsledný výstup:
```markdown
Souhrnný výkon série
Zobrazení: 600 (320 + 280)
Reach: 250 - maximální dosah na začátku série
Návštěvy profilu: 6
Interakce: 20 (12 + 8)
Míra opuštění: 16,0 %
Výsledek ankety/kvízu: ovocné 65 % / zeleninové 35 %
```

---

## 6. Automatizační skript

Pro programatické zpracování nebo hromadné vyhodnocení je k dispozici skript:
```bash
python3 skills/story-series-extract/scripts/extract_story_series.py input_stories.json
```
Skript validuje formát, sečte zobrazení a interakce, spočítá míru opuštění a vygeneruje standardizovaný blok v Markdownu i JSON.
