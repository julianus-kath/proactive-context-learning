# Unverified Reconciliation Summary

This file reports the **final** state of the H3 ground-truth reconciliation. The numbers here match the thesis (Section 5.4 of `Thesis_Tex/src/chapters/5_results.tex`) and the canonical macro file (`Thesis_Tex/src/generated/h2b_h3_metrics.tex`).

The authoritative ground-truth file is [`h3_Complete_Ground_Truth.reconciled.csv`](h3_Complete_Ground_Truth.reconciled.csv).

## Scope (final state, N=79 production turns)

- Total turns: 79 (Session 1 / P1: 52, Session 2 / P2: 27)
- Verified turns (one of CORRECT, PARTIAL, INCORRECT, ERROR, HALLUCINATION): 65 (82.3 %)
- UNVERIFIED turns: **5** (6.3 %)
- OTHER (procedural meta / interaction-control) turns: 9 (11.4 %)

## Final label distribution

| Label | n | % of N=79 |
|---|---:|---:|
| CORRECT | 11 | 13.9 |
| PARTIAL | 10 | 12.7 |
| INCORRECT | 31 | 39.2 |
| ERROR | 9 | 11.4 |
| HALLUCINATION | 4 | 5.1 |
| UNVERIFIED | **5** | 6.3 |
| OTHER | 9 | 11.4 |
| **Total** | **79** | **100.0** |

## Reconciliation passes

The reconciliation went through two passes against the [`Transcript_User_Study_cleaned.csv`](../Thematic%20Analysis/Transcript_User_Study_cleaned.csv) think-aloud transcript and against the live database state.

### Pass 1 — UNVERIFIED resolution (16 February 2026)

Starting from the LLM-assisted candidate labels, 46 turns carried no verification anchor in the transcript and were tagged UNVERIFIED. Pass 1 mapped each UNVERIFIED turn to the closest in-time transcript utterance, applied a five-component scoring rule (time / lexical / polarity / speaker-relevance / issue), and proposed a relabel where evidence was conclusive.

- Inputs: 46 UNVERIFIED turns
- Resolved with conclusive transcript evidence: 32
- Held for manual review: 14
- Audit log: [`Unverified_Mapping_Decision_Log.csv`](Unverified_Mapping_Decision_Log.csv)

### Pass 2 — Manual review and INCORRECT-evidence audit (19 April 2026)

Pass 2 manually reviewed (a) the 14 UNVERIFIED rows held from Pass 1, and (b) the per-turn evidence behind every INCORRECT label, to confirm that the failure attribution rested on transcript anchors rather than absence of evidence.

- Of the 14 held UNVERIFIED, 9 were resolved on second look (conflicting evidence reconciled or candidate utterance located) and 5 remained genuinely unverifiable.
- The INCORRECT-evidence audit (logged in [`incorrect_evidence_audit.json`](incorrect_evidence_audit.json)) moved 4 turns whose INCORRECT label rested on absence of evidence back to UNVERIFIED, to comply with the methodology rule that absence of a participant verdict is not coded as failure.
- Net effect on UNVERIFIED count: 14 → 5.

The five remaining UNVERIFIED turns are listed in [`Unverified_Remaining_Manual_Review.csv`](Unverified_Remaining_Manual_Review.csv).

## Quality gates (Pass 1 audit, retained for traceability)

- Gate 1 (quote + timestamp + speaker for relabels): 32/32 rows complete
- Gate 2 (no relabeling without speaker attribution): PASS
- Gate 3 (spot-check HALLUCINATION/ERROR): 3 high-risk relabels reviewed with explicit cue phrases
  - S1 T34 → ERROR at 01:08:38: "Überlauffehler, dann kam zu viel zurück."
  - S1 T35 → ERROR at 01:08:38: "Überlauffehler, dann kam zu viel zurück."
  - S2 T16 → HALLUCINATION at 01:36:52: "Der erfindet Dinge, der Mitarbeiter ID, den gibt es nicht."
- Gate 4 (duplicate evidence reuse flagged): PASS
- Gate 5 (confidence distribution and ambiguity causes reported): PASS

## Cross-reference

The numbers in this file match the thesis macro definitions in [`Thesis_Tex/src/generated/h2b_h3_metrics.tex`](../../../../Thesis_Tex/src/generated/h2b_h3_metrics.tex):

| Macro | Value |
|---|---:|
| `\HProdTotalTurns` | 79 |
| `\HProdVerifiedTurns` | 65 |
| `\HProdUnverifiedTurns` | 5 |
| `\HProdOtherTurns` | 9 |
| `\HProdLabelCorrectN` | 11 |
| `\HProdLabelPartialN` | 10 |
| `\HProdLabelIncorrectN` | 31 |
| `\HProdLabelErrorN` | 9 |
| `\HProdLabelHallucinationN` | 4 |
| `\HProdLabelUnverifiedN` | 5 |
