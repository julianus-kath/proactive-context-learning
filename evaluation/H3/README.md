# H3 Evidence — Exploratory Value to Users

H3 hypothesis: *Users derive exploratory value from the system, with trust and adoption signals measurable through behavioural and questionnaire evidence.*

Primary evidence: a two-participant think-aloud user study (P1, P2) with the production Sage deployment, conducted 2026-01-19. Each participant ran a series of natural-language queries against the live ERP through the chatbot UI, with screen recording and post-task questionnaire. The methodology combines UTAUT (Unified Theory of Acceptance and Use of Technology) with NASA-TLX workload self-report.

These artefacts populate Thesis §5.4.

## What ships in this release

This subdirectory ships the **study design** and the **anonymised analytical outputs**. Raw transcripts, screen recordings, and ground-truth files that contain participant identifiers are held privately under the participant consent terms and are not redistributed.

| Path | Role |
|---|---|
| [`study_design/User_Study_Design.pdf`](study_design/User_Study_Design.pdf) | Protocol: tasks, instrumentation, scoring rubric |
| [`study_design/Questionnaire_UserStudy.pdf`](study_design/Questionnaire_UserStudy.pdf) | UTAUT + NASA-TLX questionnaire as administered |
| [`study_design/Consent_Form.pdf`](study_design/Consent_Form.pdf) | Participant consent template (no signed copies are shipped) |
| [`analysis/Thematic_Analysis_v2.md`](analysis/Thematic_Analysis_v2.md) | Final thematic analysis of session interactions |
| [`analysis/User_Study_Metrics_Extension_H2b_H3.md`](analysis/User_Study_Metrics_Extension_H2b_H3.md) | Quantitative metrics derived from the session logs |

## What is *not* in this release

- Raw session transcripts (`Transcript_User_Study.json/csv`) — participant identifiable.
- Screen recording (`Screen Recording 2026-01-19 at 14.32.59.mov`) — participant identifiable.
- Per-turn ground-truth labels (`h3_Complete_Ground_Truth.csv`) — contain participant identifiers and partner-internal context.
- Cross-reference reconciliation logs (`Unverified_*.csv`, `Supplementary_Thematic_Analysis.md`, `User_Study_Analysis_Report.md`) — confirmed to contain participant names.

These remain in the supervisor-private evaluation vault. A summary of the H3 findings without identifying material is in the thesis itself (§5.4) and in the analysis files above.

## Methodology, in one paragraph

Two participants in their day-to-day Sage role were given a fixed task list of natural-language queries to ask the assistant. Sessions were screen-recorded and transcript-logged at the agent layer. After each session the participant completed a UTAUT-style acceptance questionnaire and a NASA-TLX workload report. The thematic analysis was performed as a single-coder pass on the cleaned transcripts; quantitative correctness labels were assigned by reconciling the agent trace, the SQL it executed, and the value it returned against the participant's stated intent.

## Caveats (load-bearing for the defense)

1. **N=2 is qualitative, not statistical.** The thesis text frames H3 as exploratory evidence, not as a hypothesis test in the inferential sense. No effect-size or significance language is used for the user-study results.

2. **Single-coder thematic analysis.** The thematic categories were derived and assigned by the author. Inter-coder reliability was not measured because there was no second coder.

3. **Participant role overlap with the production deployment.** Both participants are users of the production Sage system that hosts the assistant; their familiarity with the schema is therefore already higher than a naïve user's. The H3 evidence speaks to acceptance among informed users, not to onboarding cost for new users.

4. **The Ref+ / Ref− / Ref NA labels in the thesis figures** mean: Ref+ — the reference SQL existed and the agent's answer matched its result; Ref− — reference existed and the answer did not match; Ref NA — the question had no reference SQL available in the partner ground-truth file. The label distribution is reported in `analysis/User_Study_Metrics_Extension_H2b_H3.md`.
