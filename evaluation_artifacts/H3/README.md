# H3 Evidence — Exploratory Value to Users

H3 hypothesis: *Users derive exploratory value from the system, with trust and adoption signals measurable through behavioural and questionnaire evidence.*

Two-participant think-aloud user study (P1, P2) with the production Sage deployment, conducted **2026-01-19**. Methodology combines a UTAUT-style acceptance questionnaire with NASA-TLX workload self-report; behaviour is captured via system session logs, agent transcripts, and a screen recording.

[![H3 user study screen recording](https://img.youtube.com/vi/2CvVFkrAKMI/hqdefault.jpg)](https://youtu.be/2CvVFkrAKMI)
*Click to play — unlisted YouTube mirror of the H3 user study session.*

## Artefact map

The four kinds of evidence the thesis discusses for H3, with their concrete files in this directory:

| Evidence | Files |
|---|---|
| **System session logs** (raw `/process_conversation` traces, one per participant) | `Results/User Study Artifacts/User Study Logs 1.json`<br/>`Results/User Study Artifacts/User Study Logs 2.json` |
| **Transcripts** (think-aloud + agent trace, raw and cleaned) | `Results/Thematic Analysis/Transcript_User_Study.json` (raw)<br/>`Results/Thematic Analysis/Transcript_User_Study_cleaned.csv`<br/>`Results/Thematic Analysis/Transcript_User_Study_cleaned.json` |
| **Screen recording** (single combined session) | Original 7 GB `.mov` held privately; mirrored as an unlisted YouTube video — <https://youtu.be/2CvVFkrAKMI> (see [`Screen_Recording_README.md`](Screen_Recording_README.md) for access notes). |
| **UTAUT / UEX questionnaire results** | `Results/User Study Artifacts/User Experience Assessment Framework for ERP Chatbot System(1-1).xlsx` |

## Analysis outputs (cited in §5.4)

| File | Role |
|---|---|
| `Results/Thematic Analysis/Thematic_Analysis.md` | Final thematic analysis of session interactions |
| `Results/Thematic Analysis/Supplementary_Thematic_Analysis.md` | Per-turn supplementary findings |
| `Results/Thematic Analysis/User_Study_Analysis_Report.md` | Combined narrative report (qualitative + UTAUT/NASA-TLX) |

## Cross-reference verification (Ref+/Ref−/Ref-NA labels in the thesis figures)

Per-turn correctness labels reconcile the agent trace, the executed SQL, and the value returned against the participant's stated intent.

| File | Role |
|---|---|
| `Results/cross_reference_analysis/h3_Complete_Ground_Truth.csv` | Per-turn ground-truth labels (CSV) |
| `Results/cross_reference_analysis/h3_Complete_Ground_Truth.reconciled.csv` | Final reconciled labels (after audit) |
| `Results/cross_reference_analysis/h3_Complete_Ground_Truth.xlsx` | Excel workbook with the same labels (for review) |
| `Results/cross_reference_analysis/H3_Ground_Truth_Analysis.md` | Narrative explaining the reconciliation |
| `Results/cross_reference_analysis/Unverified_Mapping_Decision_Log.csv` | Decision log for the verification audit |
| `Results/cross_reference_analysis/Unverified_Reconciliation_Summary.md` | Summary of unresolved cases |
| `Results/cross_reference_analysis/Unverified_Remaining_Manual_Review.csv` | Items requiring manual review (post-audit) |
| `Results/cross_reference_analysis/incorrect_evidence_audit.json` | Audit trace for INCORRECT-labelled turns |
| `Results/cross_reference_analysis/incorrect_relabel_proposal.csv` | Proposed re-labels surfaced during the audit |
| `Results/User Study Artifacts/Transcript_Verification_Candidates.csv` | Candidate turns flagged for verification |
| `Results/unverified_turn_mapper.py` | Script used to map unverified turns to the ground-truth file |

## Study design

| File | Role |
|---|---|
| `Study_Outline/User Study Design .pdf` | Protocol: tasks, instrumentation, scoring rubric (canonical reference) |
| `Study_Outline/User Study Design .docx` | Same, editable source |
| `Study_Outline/Fragenkatalog_UserStudy.pdf` | UTAUT + NASA-TLX questionnaire as administered |
| `Study_Outline/Consent_Form_Proactive_Context_Learning.pdf` | Consent form template (no signatures) |
| `Study_Outline/Consent Form_Signed.pdf` | ⚠️ Signed consent form — contains a participant signature. Held privately; **must not be committed to public GitHub.** |
| `Study_Outline/GPT_Zusammenfassung der User Study.docx` | German-language working summary |


