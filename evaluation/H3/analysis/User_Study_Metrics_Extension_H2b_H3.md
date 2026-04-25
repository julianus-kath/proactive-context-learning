# User Study Metrics Extension (H2b/H3 Carryover)

## Data Completeness Audit
- Ground-truth table rows: 79
- System log turns (Session 1 + 2): 79
- Transcript utterances: 931
- Verified turns with explicit user evidence: 26 (32.9%)
- Unverified turns: 46 (58.2%)
- Questionnaire completed response rows detected: 1

## H2a Production Accuracy (with uncertainty)
- Strict accuracy: 23.08% (6/26)
- Strict 95% Wilson CI: 11.03% to 42.05%
- Acceptable accuracy (CORRECT+PARTIAL): 38.46% (10/26)
- Acceptable 95% Wilson CI: 22.43% to 57.47%

Conservative bounds over all evaluable turns (excluding N/A):
- Strict worst/best-case: 8.33% to 72.22%
- Acceptable worst/best-case: 13.89% to 77.78%

## Session Effects (H2b transfer stability)
| Session | Turns | Verified Turns | Strict % | Acceptable % | SQL Generated % |
|---|---:|---:|---:|---:|---:|
| 1 | 52 | 24 | 20.83 | 37.50 | 75.00 |
| 2 | 27 | 2 | 50.00 | 50.00 | 74.07 |

## Latency vs Correctness
| Ground Truth | n | Mean Latency (ms) | Median (ms) | Min | Max |
|---|---:|---:|---:|---:|---:|
| CORRECT | 6 | 5860.3 | 5487.0 | 1064 | 9664 |
| PARTIAL | 4 | 17807.0 | 10665.0 | 4528 | 45370 |
| INCORRECT | 10 | 19178.1 | 10268.5 | 2453 | 59500 |
| ERROR | 5 | 11082.0 | 11274.0 | 2257 | 23314 |
| HALLUCINATION | 1 | 2246.0 | 2246.0 | 2246 | 2246 |
| UNVERIFIED | 46 | 10693.0 | 6870.5 | 1070 | 74386 |

## H1-to-H2b Carryover Proxies (from production SQL traces)
- SQL-generated turns: 59 / 79 (74.68%)
- Unique production tables referenced in generated SQL: 30
- Average joins per SQL: 0.03 (median 0, max 1)
- Average tables referenced per SQL: 1.15
- No-SQL turns that still provide concrete table attribution in response text: 7 / 20 (35.0%)

Top referenced tables (frequency):
- `dbo.khkvkbelegepositionen`: 8
- `dbo.khkvkbelege`: 7
- `dbo.khkppsressourcenpositionen`: 7
- `dbo.khkppsrueckmeldungen`: 7
- `dbo.khkppsffbestellmengen`: 4
- `dbo.khkartikel`: 3
- `dbo.tkhkppsmitarbeiterbuchungen`: 3
- `dbo.khkartikelbewertungmekhistorie`: 3
- `dbo.khkbuchungserfassungsdiv`: 3
- `dbo.khkekbelege`: 3

## H3 Trust/Interaction Signals
- Verification-style user turns: 13/79 (16.5%)
- Follow-up/reformulation turns: 33/79 (41.8%)
- Interpretation: high follow-up and verification behavior indicates users actively checked outputs instead of passive acceptance.

## Additional Derived Signals
- Correlation between conversation context length and latency: -0.006 (no meaningful relationship in this dataset).
- Session 1 drift (verified subset): acceptable accuracy declined from 52.9% in the first half to 0.0% in the second half.
- Date-heavy verified SQL (contains date/timestamp filtering) had lower acceptable rate (30.8%) than non-date verified SQL (62.5%).

## Gaps Not Fully Exploited Yet
- No inter-rater agreement for semantic labels (single coder).
- Verified subset is sparse and imbalanced across sessions (Session 2 has very low verification coverage).
- Questionnaire evidence appears to include only one completed response row; this weakens inferential claims for H3 constructs.
- No table-linking ground truth in production, so H1 transfer relies on proxies rather than recall@k.
- `success_flag` in raw logs is always true (79/79), so execution quality must be inferred from `has_sql` + semantic labels, not `success_flag` alone.

## Immediate Thesis Strengthening Actions
1. Report confidence intervals (not only point estimates) for strict and acceptable accuracy.
2. Report worst/best-case bounds due unverified turns to make uncertainty explicit.
3. Add session-level and turn-level heterogeneity analysis (Session 1 vs 2).
4. Add latency-by-outcome analysis to show that slower responses are not more accurate.
5. Position H1 carryover using production SQL trace proxies (table diversity, joins, source-attribution behavior).
6. Reframe H3 quantitative claims as exploratory due questionnaire sample size; rely more on transcript-grounded thematic evidence.
