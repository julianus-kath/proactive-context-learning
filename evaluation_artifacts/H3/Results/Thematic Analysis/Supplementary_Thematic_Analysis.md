# Supplementary Analysis: Extended Thematic Coding and Quote Repository

_Anonymisation note: this file uses **P1** (co-Managing Director, strategic non-technical role) and **P2** (technical lead, ERP integrator-adjacent role) as in the main thesis and in [`Thematic_Analysis.md`](Thematic_Analysis.md). Earlier drafts of this file referenced the participants by name; those references have been replaced with P1/P2 in line with consent terms._


## Purpose

This supplementary document provides extended quotations and coding references for the main User Study Analysis Report. All citations follow APA 7 format with timestamp references.

---

## Theme Codebook

### Theme 1: Current Workflow Bottlenecks (CWB)

**Definition:** Statements describing current difficulties, inefficiencies, or pain points in data access workflows.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| CWB-1 | Technical Dependency | Reliance on technical staff for queries |
| CWB-2 | Communication Overhead | Time/cost to specify requirements |
| CWB-3 | System Rigidity | ERP limitations for custom queries |
| CWB-4 | Export-Transform Cycle | Manual data manipulation requirements |

**Key Quotations:**

**CWB-1: Technical Dependency**

> "Ich brauche dafür aber dann sicher mal ihn, dass er dann die neue Abfrage bauen kann."  
> (P1, Transcript, 02:14)

> "Was darüber hinausgeht, versteht er und kann dann zum Beispiel Abfragen bauen, die meine Fragen entweder schneller beantworten oder zusätzliche Dinge beantworten."  
> (P1, Transcript, 01:29)

**CWB-2: Communication Overhead**

> "Und was dann halt auch ist, ich muss mit meinem Verständnis von was ich gern hätte, ihm klar machen, was ich gern hätte. Er versteht zum Glück, weil er seit 20 Jahren uns betreut."  
> (P1, Transcript, 02:20-02:31)

> "Und da hatten wir schon mehrmals Probleme, bis der versteht, was ich wirklich will, dann macht er es und dann sehe ich aber vier Wochen später, was er wirklich gemacht hat."  
> (P1, Transcript, 02:38-02:48)

**CWB-3: System Rigidity**

> "Das ist für mich das größte Problem mit Sage, was ich habe. Aber logischerweise, das ist so eine Standardsoftware, nenne ich das. Da kann ich auch nicht mehr erwarten."  
> (P1, Transcript, 02:59-03:10)

> "Ich kann aber nicht in Sage rechnen, weil logisch, die können nicht jede Frage, die irgendjemand hat, beantworten."  
> (P1, Transcript, 02:07-02:13)

**CWB-4: Export-Transform Cycle**

> "Jetzt sind wir gerade dabei, Rückmeldung eines Mitarbeiters, die melden über die BDE zurück, welche Teile, über welchen Auftrag, in welcher Zeit haben die gemacht, auf welcher Maschine und wenn ich das auswerten möchte, dann gibt es da eine vorgefertigte Sage Auswertung und die kann ich in Excel exportieren und dann kann ich dort drin beispielsweise rechnen."  
> (P1, Transcript, 01:41-02:05)

---

### Theme 2: Schema Complexity (SC)

**Definition:** Statements relating to database structure complexity and navigation challenges.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| SC-1 | Table Volume | Large number of tables (940+) |
| SC-2 | Naming Conventions | Non-intuitive table/field names |
| SC-3 | Relational Understanding | Need to understand table relationships |

**Key Quotations:**

**SC-1 & SC-2: Table Volume and Naming**

> "Aber sobald man das halt und auf der einen Datenbank, auf die ich Zugriff hatten wir über 940 Tabellen, die halt auch alle spezielle Namen haben und so weiter."  
> (Julianus, Transcript, 04:39-04:48)

**SC-3: Relational Understanding**

> "Dann fangen wir natürlich mit dem relationalen Datenbankmodell an, das heißt, ich muss die Zusammenhänge verstehen."  
> (P2, Transcript, 15:05-15:15)

> "Das heißt, man muss dann Konstellationen machen und dann mal ausprobieren, ob die Antworten auch tatsächlich stimmen."  
> (P2, Transcript, 15:32-15:43)

> "Das ist natürlich aufwendig, das ist auch immer schwer abzuschätzen von den Zeiten her, gerade wenn es neue Fragen sind."  
> (P2, Transcript, 15:43-15:55)

---

### Theme 3: System Interaction Experience (SIE)

**Definition:** Observations about interacting with the NLI system.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| SIE-1 | Query Formulation | Ease/difficulty of expressing queries |
| SIE-2 | Response Latency | System response time perception |
| SIE-3 | Output Interpretation | Understanding system responses |
| SIE-4 | Iterative Refinement | Need to reformulate queries |

**Key Quotations:**

**SIE-2: Response Latency**

> "Der ist schon noch langsam."  
> (Participant, Transcript, 37:52)

> "Aber ist ja nicht so, dass ich ständig so Fragen hätte."  
> (Participant, Transcript, 38:05)

**SIE-4: Iterative Refinement**

From system logs:

> User: "DAnn habe ich mich ev. nicht korrekt ausgedrückt - Welche Artikelnummer weist die meisten verkauften Einheiten 2025 auf?"  
> (User_Study_Logs_1.json, Turn 3)

---

### Theme 4: Trust and Verification (TV)

**Definition:** Statements about trusting system outputs and verification behaviors.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| TV-1 | Source Verification | Asking for data sources |
| TV-2 | Result Validation | Checking outputs against knowledge |
| TV-3 | Trust Erosion | Events reducing confidence |
| TV-4 | Hallucination Detection | Identifying fabricated content |

**Key Quotations:**

**TV-1: Source Verification**

From system logs:
> User: "Woher hast Du diese Daten?"  
> (User_Study_Logs_1.json, Turn 8)

> User: "Wie heissen die Tabellen und Felder"  
> (User_Study_Logs_1.json, Turn 9)

**TV-2: Result Validation**

> User: "Wie kommst du auf den Verkaufspreis von 0.0 am 19.12.2025?"  
> (User_Study_Logs_1.json, Turn 31)

**TV-4: Hallucination Detection**

From transcript (approximate timestamp):
> "Das geht gar nicht... Das hier ist ja nicht okay, das erfundene Beispiel."  
> (Transcript, ~01:08:45)

---

### Theme 5: Perceived Value and Adoption (PVA)

**Definition:** Statements about system utility and willingness to adopt.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| PVA-1 | Use Case Fit | Appropriate applications |
| PVA-2 | Relative Advantage | Comparison to current tools |
| PVA-3 | Organizational Readiness | Infrastructure/culture fit |
| PVA-4 | Future Potential | Vision for enhanced capabilities |

**Key Quotations:**

**PVA-1: Use Case Fit**

> "Für den neuangestellten Mitarbeiter ist das schneller."  
> (Transcript, ~02:05:48)

**PVA-2: Relative Advantage**

> "Ich finde die Antworten waren ja nicht völlig aus dem Raum gegriffen, von daher ist das schon ein Schritt in die richtige Richtung."  
> (P2, Transcript, 02:05:15-02:05:32)

**PVA-3: Organizational Readiness**

> "Wir sind klein genug, dass wir machen können, was immer wir wollen... Wir haben denke ich viel Daten und keiner der uns hindert, sofern es unser ITler zulässt."  
> (P1, Transcript, 02:06:35-02:06:49)

**PVA-4: Future Potential**

> "Schön wäre es aber da sehe ich, wo so etwas personalisierter nutzbar wäre und schön wäre es, wenn das eben durch mich nutzbar ist. Und nicht immer dazu..."  
> (P1, Transcript, 03:10-03:27)

> "Und noch viel schöner wäre dann, wenn ich nicht selber sagen muss, auf was ich schauen muss, sondern das erzählt mir."  
> (P1, Transcript, 09:22)

---

### Theme 6: Data Quality Concerns (DQC)

**Definition:** Statements about data quality issues affecting analysis.

| Code | Sub-theme | Description |
|------|-----------|-------------|
| DQC-1 | Missing Data | Gaps in data capture |
| DQC-2 | Inconsistent Entry | Variation in data recording |
| DQC-3 | Historical Issues | Legacy data problems |

**Key Quotations:**

**DQC-1 & DQC-2: Data Quality**

> "Nein, Datenqualität wäre, glaube ich, immer unser Problem."  
> (P1, Transcript, 13:28)

> "Mein größtes Problem ist, denke ich, die Starrheit."  
> (P1, Transcript, 13:38)

---

## System Performance Evidence

### Query Success Patterns

**Successful Query Types (from logs):**

1. Single-table lookups
   - Example: "KAnnst du mir den Matchcode des Artikels 71091794 ausgeben?" → Success (Turn 4, 4406ms)

2. Simple aggregations
   - Example: "Welchen Artikel haben wir nach diesem Vierkantstahl am häufigsten verkauft?" → Success (Turn 5, 9054ms)

3. Customer identification
   - Example: "Welche ID hat der Kunde Flowtec?" → Success (Turn 47, 5070ms)

**Problematic Query Types (from logs):**

1. Complex temporal filtering with timestamp conversion errors
   - Example: Turn 39 - Buchung query resulted in timestamp overflow error

2. Cross-table queries with incorrect table selection
   - Example: Turn 46 - Flowtec delivery time query returned no results due to incorrect field matching

3. Queries requiring domain knowledge not captured in schema
   - Example: Turn 44 - "Trumpf Lasermaschine" not found (natural language term vs. booking text)

---

## NASA-TLX Detailed Analysis

### Raw Response Mapping

| Dimension | Response Text | Numeric Equivalent (1-7) |
|-----------|---------------|-------------------------|
| Mental Demand | Low | 2-3 |
| Temporal Demand | Low | 2-3 |
| Performance | Very Low | 1-2 |
| Effort | Low | 2-3 |
| Frustration | High | 5-6 |
| Physical Demand | Very Low | 1 |

### Interpretation Notes

The pattern of low demand/effort combined with high frustration and low perceived success suggests:

1. The conversational interface successfully reduces cognitive load for query formulation
2. Users were not under time pressure during evaluation
3. Despite ease of interaction, outcomes did not meet expectations
4. Frustration likely stems from result accuracy issues, not interaction difficulty

---

## UTAUT2 Construct-Level Analysis

### Performance Expectancy (PE) - Negative

All four items showed disagreement or neutrality:
- PE1: Disagree (data analysis improvement)
- PE2: Disagree (decision-making quality)
- PE3: Agree (speed - only positive)
- PE4: Neither (overall usefulness)

**Implication:** Users do not perceive the system as improving their analytical capabilities, except for speed in certain cases.

### Effort Expectancy (EE) - Mixed

- EE1: Strongly Agree (learning ease)
- EE2: Agree (natural interaction)
- EE3: Disagree (achieving desired outcomes)
- EE4: Agree (no technical support needed)

**Implication:** The system is easy to learn and interact with, but users struggle to achieve their specific goals.

### Hedonic Motivation (HM) - Positive

All items showed agreement:
- HM1: Agree (enjoyment)
- HM2: Strongly Agree (engaging)
- HM3: Agree (enjoyable interface)

**Implication:** Despite practical limitations, users find the experience engaging and enjoyable.

### Habit Formation (HF) - Strongly Negative

All items showed strong disagreement:
- HF1: Strongly Disagree (routine)
- HF2: Strongly Disagree (natural turn-to)
- HF3: Strongly Disagree (frequent use)

**Implication:** Users do not envision the system becoming a regular part of their workflow in its current state.

---

## References for Methodology

Braun, V., & Clarke, V. (2006). Using thematic analysis in psychology. *Qualitative Research in Psychology*, 3(2), 77-101. https://doi.org/10.1191/1478088706qp063oa

Creswell, J. W., & Poth, C. N. (2018). *Qualitative inquiry and research design: Choosing among five approaches* (4th ed.). SAGE Publications.

Hart, S. G. (2006). NASA-Task Load Index (NASA-TLX); 20 years later. *Proceedings of the Human Factors and Ergonomics Society Annual Meeting*, 50(9), 904-908.

Venkatesh, V., Thong, J. Y. L., & Xu, X. (2012). Consumer acceptance and use of information technology: Extending the unified theory of acceptance and use of technology. *MIS Quarterly*, 36(1), 157-178.

---

*End of Supplementary Analysis Document*
