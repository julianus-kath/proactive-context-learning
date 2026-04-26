# H3 Ground Truth Analysis: Production User-Study Verification

## Executive Summary

This analysis presents the verification labels for the H3 production user study (N = 79 system turns), cross-referenced with verbal verification statements from the joint think-aloud transcript and against live database state. Numbers in this document match the thesis (Section 5.4 of `Thesis_Tex/src/chapters/5_results.tex`) and the canonical macro file (`Thesis_Tex/src/generated/h2b_h3_metrics.tex`).

**Key finding.** Of the 65 turns that received a semantic verdict, the system reached **16.92 % strict accuracy** (CORRECT only) and **32.31 % acceptable accuracy** (CORRECT + PARTIAL). The combined hallucination rate on those 65 verified turns was **6.15 %**. SQL was generated on **74.68 %** of the 79 logged turns, and every generated statement executed without error. The thesis interprets these numbers as a partial confirmation of H3 (operational usability) without support for unconditional decision-support value.

This document supersedes the January 2026 baseline analysis that was based on a pre-reconciliation cohort of 26 verbally verified turns. The reconciliation history (baseline → final) is recorded in [`Unverified_Reconciliation_Summary.md`](Unverified_Reconciliation_Summary.md). The authoritative ground-truth file is [`h3_Complete_Ground_Truth.reconciled.csv`](h3_Complete_Ground_Truth.reconciled.csv).

---

## 1. Methodology

### 1.1 Data sources
- **System logs:** 79 interaction turns across the joint user-study session (Session 1 / P1: 52 turns, Session 2 / P2: 27 turns)
- **Transcript:** 931 utterances with timestamps and diarised speaker attribution ([`Transcript_User_Study_cleaned.csv`](../Thematic%20Analysis/Transcript_User_Study_cleaned.csv))
- **Verification source:** Concurrent think-aloud commentary and post-hoc inspection of live Sage database state for turns where the transcript was silent

### 1.2 Classification schema

| Category | Definition | Example cue |
|----------|------------|-------------|
| CORRECT | Result matches Sage ERP verification | "sowas stimmt" |
| PARTIAL | Partially correct, minor deviation, or correct interpretation with a wrong column | "Das stimmt fast" |
| INCORRECT | Verifiably wrong result | "Das ist nicht richtig" |
| ERROR | Query failed, returned no rows, or raised an MSSQL fault | Timestamp overflow |
| HALLUCINATION | Fabricated value that does not exist in the database | Invented matchcode |
| UNVERIFIED | No transcript anchor *and* no recoverable database-state evidence | — |
| OTHER | Procedural or interaction-control turn (no SQL judgement applies) | Provenance / schema-lookup question |

### 1.3 Verification process
1. Parsed the transcript for verification cues (`stimmt`, `falsch`, `richtig`, `korrekt`, `erfunden`, etc.)
2. Filtered to participant utterances (P1, P2)
3. Mapped each cue to its closest in-time logged turn
4. For turns with no transcript anchor, inspected the logged SQL and the returned rowset against the Sage schema and live database state
5. UNVERIFIED is reserved for turns where neither (3) nor (4) yielded conclusive evidence

Reconciliation went through two passes (16 February and 19 April 2026) — see [`Unverified_Reconciliation_Summary.md`](Unverified_Reconciliation_Summary.md) for the full audit log.

---

## 2. Results

### 2.1 Final label distribution (N = 79)

| Label | n | % of N=79 |
|---|---:|---:|
| CORRECT | 11 | 13.9 |
| PARTIAL | 10 | 12.7 |
| INCORRECT | 31 | 39.2 |
| ERROR | 9 | 11.4 |
| HALLUCINATION | 4 | 5.1 |
| UNVERIFIED | 5 | 6.3 |
| OTHER | 9 | 11.4 |
| **Total** | **79** | **100.0** |

Verified subtotal (CORRECT + PARTIAL + INCORRECT + ERROR + HALLUCINATION) = **65** (82.3 %).

### 2.2 Verified-subset metrics (n = 65)

| Metric | Value |
|---|---|
| Strict accuracy (CORRECT / verified) | **16.92 %** (11 / 65) |
| Acceptable accuracy ((CORRECT + PARTIAL) / verified) | **32.31 %** (21 / 65) |
| Failure rate ((INCORRECT + ERROR + HALLUCINATION) / verified) | 67.69 % (44 / 65) |
| Hallucination rate (HALLUCINATION / verified) | **6.15 %** (4 / 65) |

### 2.3 SQL generation vs. semantic correctness

| Metric | Value |
|---|---|
| SQL generated | **59 / 79 (74.68 %)** |
| SQL execution success (per logs) | 59 / 59 (100 %) |
| Strict semantic correctness on verified | 11 / 65 (16.92 %) |

Execution success ≠ semantic correctness: the agent produced syntactically valid SQL on three of every four turns, all of which executed against the live Sage MSSQL database without error, yet only one in six of the verifiable answers matched what the participant required.

---

## 3. Error pattern analysis

### 3.1 Error subcategories within INCORRECT (n = 31)

| Pattern | Count |
|---|---:|
| Data-interpretation error | 26 |
| Wrong-table selection | 5 |
| Timestamp / date-handling error | 5 |
| Domain-knowledge gap | 4 |
| SQL-producing hallucination (subset of HALLUCINATION) | 4 |

(Counts are non-exclusive: a single turn can be tagged with more than one pattern. See `\HProdErr*` macros in `Thesis_Tex/src/generated/h2b_h3_metrics.tex` for the canonical set.)

### 3.2 Hallucination breakdown (n = 4)

Three were no-SQL fabrications (the agent answered confidently without producing SQL); one was the SQL-generating instance S2T16 in which the agent asserted shift-level aggregation values that P1 rejected as inventions on the production database state. The rate is reported in the thesis as 4 / 65 verified = 6.15 %.

---

## 4. Latency

| Statistic | All turns | SQL turns | No-SQL turns |
|---|---:|---:|---:|
| Mean (ms) | 11 644 | 13 815 | 5 239 |
| Median (ms) | 7 482 | 8 464 | 3 171 |
| 95th percentile (ms) | 41 558 | 43 293 | 13 814 |
| Max (ms) | 74 386 | — | — |

The thesis discusses these descriptively; latency is not a primary H3 outcome.

---

## 5. Implications for H3 (Proof of Value)

### 5.1 Supported
- The system produced executable SQL on **74.68 %** of production turns and every generated statement ran without error.
- Two participants engaged with the natural-language interface and identified four positions of potential value (novice multiplier, expert table-locator, strategic anomaly-surfacer, integrator-knowledge bridge).

### 5.2 Not supported
- An unconditional claim of perceived decision-support value, given **31** INCORRECT turns and a **6.15 %** verified-hallucination rate.

### 5.3 Thesis framing
> "H3 is partially supported. The deployed system produced executable SQL on 74.68 % of 79 production turns at Luisi & Diener and reached 16.92 % strict semantic accuracy on the 65 verified turns […] The system is operationally usable and elicits conditional trust dependent on the user's ability to verify outputs against domain knowledge."
> — Section 7 (Conclusion), `7_conclusion.tex`

---

## 6. Limitations

1. **Coverage of the verified subset:** 5 turns remained UNVERIFIED after two reconciliation passes (transcript silent and database state non-conclusive); these are excluded from the accuracy denominators rather than coded as failures.
2. **Single coder:** All labels were assigned by the author. No second coder was available, so inter-rater reliability is not reported.
3. **Two-participant joint session:** N = 79 turns from a single joint think-aloud session limits generalisation; theme prevalence is not claimed.
4. **Domain specificity:** The Sage / manufacturing context constrains transferability of error subcategories.

---

## 7. References

- Thesis Section 5.4 — `Thesis_Tex/src/chapters/5_results.tex`
- Canonical macros — `Thesis_Tex/src/generated/h2b_h3_metrics.tex`
- Reconciliation log — [`Unverified_Reconciliation_Summary.md`](Unverified_Reconciliation_Summary.md)
- Decision log — [`Unverified_Mapping_Decision_Log.csv`](Unverified_Mapping_Decision_Log.csv)
- Final ground truth — [`h3_Complete_Ground_Truth.reconciled.csv`](h3_Complete_Ground_Truth.reconciled.csv)
- Thematic analysis (v2) — [`../Thematic Analysis/Thematic_Analysis.md`](../Thematic%20Analysis/Thematic_Analysis.md)
