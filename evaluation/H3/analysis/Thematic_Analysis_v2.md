# Thematic Analysis of the H3 User Study — v2

**Author:** Julianus Kath
**Date:** 19 April 2026
**Corpus:** One co-located, think-aloud session with two participants from Luisi & Diener (the practice partner), duration 2h09m, 931 utterance segments
**Method:** Reflexive thematic analysis following Braun & Clarke (2006), extended by their later reflexive guidance (Braun & Clarke, 2019, 2022)
**Supersedes:** `Supplementary_Thematic_Analysis.md` (24 January 2025). That earlier pass produced six technically-tilted codes (CWB, SC, SIE, TV, PVA, DQC) anchored in benchmark-style concerns (query formulation, table volume, SQL coverage). The present version re-reads the transcript with a non-technical, meta-level framing — trust, acceptability, value proposition — in line with the thesis' H3 critical-path framing that technical quality has already been exhausted by the H2a/H2b ablation study.

---

## 1. Purpose and positioning

The H3 hypothesis (Proof of Value) asks whether users derive exploratory value from the system, with trust and adoption signals measurable through behavioural and questionnaire evidence. The Northwind ablation (H2a) and the production transfer (H2b) have already adjudicated whether the artifact generates correct SQL under controlled and field conditions; the user study is not meant to re-litigate that. Its job is to surface the human-side conditions that govern whether such a system ever reaches a user's daily workflow in a Swiss SME ERP context.

This re-analysis therefore privileges three meta-domains that the participants themselves opened and closed the session with: (i) how they decide whether to trust an AI-generated answer, (ii) what would make the system acceptable enough to adopt, and (iii) where the value proposition actually sits — for whom, in which role, and at which integration depth. The themes that emerge below are not code labels invented analytically; they are the latent structures participants returned to repeatedly, across the opening problem discussion, the hands-on query attempts, and the closing reflection on organisational fit.

A note on positioning: N = 2 is small. The claim level is therefore not "these patterns generalise to Swiss SMEs" but "these are the meta-level concerns that surfaced when the intended-user cohort — a non-technical co-owner and his technical ERP integrator — engaged the system for the first time." The themes are read as hypothesis-generating for a future larger study, not as confirmatory evidence for acceptance.

---

## 2. Methodology

### 2.1 Framework

Braun & Clarke's (2006) six-phase reflexive thematic analysis was followed. The more recent reflexive formulation (Braun & Clarke, 2019; 2022) is adopted insofar as themes are understood as patterns of shared meaning actively constructed by the analyst from the data — not as entities waiting to be "found" — and the analyst's positionality (design author, thesis student, practice-partner relationship) is acknowledged as part of the reading.

### 2.2 Data

One joint session with P1 (co-Managing Director, strategic non-technical role, primary Sage user) and P2 (technical lead, ERP integrator-adjacent role with direct Sage data-model familiarity), moderated by the researcher (I). Recording length 2h09m, transcribed automatically, diarised, and cleaned on 19 April 2026 (Transcript_User_Study_cleaned.csv, 931 segments; cleaning provenance recorded in the JSON header of the paired file). Language: predominantly High German with occasional Swiss-German colouring; one speaker-label reassignment was applied to consolidate a spurious fourth-speaker tag into P1.

### 2.3 Audit trail of the six phases

**Phase 1 — Familiarisation.** The full 931-segment transcript was re-read twice. On first pass I attended to the flow of the session (problem framing → hands-on use → closing reflection); on second pass I marked candidate passages where participants made evaluative statements (positive or negative) rather than task-operational ones.

**Phase 2 — Initial coding.** Approximately 40 latent codes were generated inductively, at the semantic and latent levels. Examples: *verification-by-probing*, *fabrication-as-binary-rupture*, *provenance-as-trust-crutch*, *novice-enablement*, *expert-as-table-locator*, *proactive-dream*, *effort-parity-futility*, *data-model-injection-wish*, *bolt-on-vs-platform*, *customising-is-paid-and-maintained*. Codes were written directly against segment IDs.

**Phase 3 — Searching for themes.** Codes were clustered on the axis the user explicitly requested: trust, acceptability, value proposition. Technical-operational codes from the January 2025 pass (e.g. "SQL coverage", "table volume") were either subsumed under a meta-theme or set aside as already-covered by the H2a/H2b evaluation.

**Phase 4 — Reviewing themes.** Candidate themes were checked against the full corpus for (a) internal homogeneity — do the coded extracts cohere — and (b) external heterogeneity — are the themes distinguishable. One candidate theme ("data model as organigram") was demoted to a subtheme of *Acceptance-via-integration-threshold*, because participants treated the data-model injection wish as a prerequisite for adoption rather than as a standalone concern.

**Phase 5 — Defining and naming themes.** Three overarching themes were settled, each with two to three subthemes. Names were chosen to be declarative, not merely descriptive — they state what participants actually argued, not the topic they discussed.

**Phase 6 — Producing the report.** This document.

### 2.4 Reflexivity and limitations

The researcher designed the system under analysis and has an existing professional relationship with the participants through the thesis practice partnership. Two mitigations were applied: (a) the moderator deliberately avoided defending design decisions in-session, letting deviant cases stand; (b) the re-coding for this v2 was done after the technical ablation results were already written up, which reduces the incentive to over-interpret participant statements as endorsements of the artifact.

Limitations relevant to theme claims: single-coder analysis (no inter-rater reliability); joint-interview format (the two participants could influence one another, though the read-through shows consistent role-stability — P1 stays strategic, P2 stays technical); think-aloud effect (verbalisation may amplify evaluation beyond silent use); translation provenance (German original is the primary evidential layer; English glosses are analyst translations and are marked as such).

---

## 3. Themes

Three overarching themes are developed below. Each is introduced by a one-line definition, followed by subthemes with anchor quotes. Quotes are given in German with an English gloss in square brackets; speaker and timestamp are recorded for traceability back to the cleaned transcript.

### Theme 1 — Trust is a precondition, not an outcome

*Participants do not extend trust to the system and then withdraw it on failure; they withhold trust by default and look for evidence either to grant it or to abandon the interaction entirely. The asymmetry is sharp: one fabricated value destroys the session's trust, while many correct answers do not build it up.*

This theme re-reads what the January 2025 pass labelled "Trust & Verification" as something stronger. The issue is not that users want verification tools; the issue is that verification is their *starting* posture, and a single hallucination collapses the interaction into uselessness regardless of earlier correct outputs.

**T1.1 Default verification stance.** Both participants treat any AI-generated answer the way P1 treats ChatGPT: provisionally, to be probed. When first shown the system, P1's opening move is not to query it but to test it:

> "Da hast du angesprochen eben Vertrauen in sowas, das ist bei mir zumindest bei ChatGPT zum Teil nicht hoch, deswegen würde ich jetzt ein paar Fragen stellen, zu schauen, ob das sein kann, was der mir sagt." — P1, 00:23:49–00:24:02
> [Trust in systems like this is not high for me, at least with ChatGPT, so I would now ask a few questions to check whether what it's telling me can be true.]

The probing is not idle curiosity; it is a deliberate acceptance test that has to be passed before the system is used for anything consequential. P1 immediately formulates a question ("welches Produkt haben wir 2025 — sind alle Jahre drin?" [which product did we have in 2025 — are all years in here?]) whose answer he can independently verify. Trust has to be earned, and the first transaction is a diagnostic probe, not a use case.

**T1.2 Fabrication as binary rupture.** When the system produces plausible-looking but invented values, the reaction is categorical rather than graded. P1's closing evaluation of the system is explicit on this point:

> "Absoluter Abbruch von Vertrauen. Wenn Erfindungen auftauchen, falsche Schlüsselwerte […] den es nicht gibt, dann denke ich, da könnte ein Affe sitzen und schickt irgendwas raus." — P1, 01:50:50–01:51:14
> [Total collapse of trust. When fabrications appear, false key values that don't exist, then I think a monkey could be sitting there sending out anything.]

The phrasing *absoluter Abbruch* and the *Affe* image are not rhetorical flourishes; they encode a binary judgement about system-class rather than system-instance. A single fabrication shifts the user's model of the system from *agent* to *random generator*, at which point no further probing is warranted. This mirrors the known effect in recommender-system trust research where a small number of visible errors outweigh a larger number of successes, but the effect here is more categorical: the rupture is not probabilistic distrust, it is disqualification.

**T1.3 Provenance as an imperfect substitute for trust.** Given that full trust is not extendable to a current LLM-based system, participants gesture toward an intermediate mechanism: showing them *where* the answer came from, so they can spot-check without fully re-doing the work. The wish is simultaneously expressed and qualified:

> "Dort hilft aber, wenn ich sehe, wo er es her hat, also die ganze Erklärung nicht, dass ich sie immer brauche, aber wenn ich mir irgendwo ein bisschen unsicher wäre zu schauen können, schaut der am richtigen Ort." — P1, 01:50:39–01:50:50
> [It helps when I see where he got it from — the whole explanation — not that I always need it, but if I'm a bit unsure somewhere, being able to check whether it's looking in the right place.]

The immediately following turn, however, qualifies this to the point of contradiction:

> "Bei ChatGPT will ich nicht wissen, wo der das her hat, weil für ein gutes System, das ich nutze, müsste das Vertrauen halt schon da sein." — P1, 01:51:31–01:51:40
> [With ChatGPT I don't want to know where it got it from, because for a good system that I use, the trust should just be there.]

This is the most analytically revealing passage in the transcript. Provenance UI (showing tool-call traces, showing which tables were consulted) is a scaffold the user wants *while the system is not yet trustworthy*, but its presence is itself evidence that the system has not reached the standard the user would consider "a good system." The provenance crutch is demanded and resented simultaneously. Any design response to this finding cannot be "add more transparency UI"; it has to recognise that users are asking for transparency as a stopgap while hoping to graduate past it.

**Deviant case for Theme 1.** P2's verification stance is structurally different: he is willing to *latently* verify continuously rather than performing bounded acceptance tests. His summary position is: "für mich geht es in die richtige Richtung, aber Vertrauen könnte aber keines aufbauen auf meiner Seite. Also ich müsste ihn latent überprüfen" (P2, 01:45:27–01:45:37) [for me it's going in the right direction, but I couldn't build up any trust on my side. I'd have to check it latently]. The word *latent* here does work — it implies continuous low-level monitoring rather than categorical disqualification. Role matters: the technical participant treats verification as part of his ordinary job, whereas the strategic participant treats it as a precondition to delegation. Theme 1 holds across both, but its operational meaning differs by role.

---

### Theme 2 — Value is stratified and role-contingent, not uniform

*Participants do not evaluate the system as a single tool with a single value proposition. They stratify it across three distinct user segments — novice employees, technical experts, and strategic decision-makers — and assign it a different role, a different threshold for adoption, and a different payoff at each level. The thesis' framing of "user value" as a monolithic quantity is too coarse for what the data shows.*

When asked where they saw the system's potential, both participants answered by decomposing the target audience rather than by naming a use case. The decomposition is stable across multiple passages and is role-anchored.

**T2.1 The novice multiplier.** The clearest value articulation is for employees who currently *cannot* use Sage well because of its vocabulary and table structure. P1 comes back to this twice, with slightly different framings. After seeing that getting an answer from the system still required him to supply the field and table names himself, the moderator suggests the system might be more valuable for people who don't already know Sage; P1 agrees instantly:

> "Das wäre ein Riesenvorteil. […] Und genauso möchte ich, wenn ich irgendeinen Sachbearbeiter einstelle, ich will dem nicht das System beibringen müssen, das sollte die KI machen oder die sollte ihn befähigen, das von 0 auf 100 zu nutzen." — P1, 01:06:36–01:06:55
> [That would be a huge advantage. And the same applies when I hire any clerical employee — I don't want to have to teach him the system; the AI should do that, or enable him to go from 0 to 100.]

The value proposition here is *substitution of institutional onboarding*, not query-answering speed. The competitive reference point is not Sage-plus-Excel but rather the cost of training a new employee to use Sage at all. This is a radically different framing from the benchmark evaluation's framing (SQL correctness on NL queries).

**T2.2 The expert as table-locator.** For the technical user (P2), the value is not in generating answers but in *pointing* at the right tables:

> "Für mich wäre es natürlich sehr attraktiv, wenn er mir sagen könnte, welche Tabellen beinhalten die Werte zur folgenden Sachfrage?" — P2, 01:53:28–01:53:40
> [For me it would of course be very attractive if it could tell me which tables contain the values for the following business question.]

Crucially, P2 does not want the system to answer; he wants it to *find*. The moderator explicitly reframes this in-session as "human-out-of-the-loop" vs. "assistant-on-the-way," and P2 confirms the latter: the value is an assistant that collapses the Sage-schema lookup overhead without taking over the SQL generation. This inverts the typical text-to-SQL framing. For an expert, Scout Mode's ranked-table output is potentially *more* valuable than the generated SQL it scaffolds.

**T2.3 The strategic proactive partner.** Before any hands-on use, when asked what the ideal system would look like, P1 articulates a third level that is neither novice-enablement nor expert-assistance but pre-emptive insight:

> "Das wäre ein Traum, wenn ich nicht selber wissen müsste, worauf ich eigentlich schauen muss. […] dass mir das System selber sagt, worauf ich eigentlich schauen müsste." — P1, 00:09:48–00:09:54 / 00:09:38–00:09:43
> [It would be a dream if I didn't have to know myself what I should be looking at. That the system itself tells me what I should be looking at.]

This is a qualitatively different ask. The novice wants to *perform* an existing task faster; the expert wants to *locate* the data; the strategist wants the system to *nominate* the question itself by detecting deviations from past patterns ("Korrelationen präsentiert bekomme, weil die abweichen von wie es bis jetzt war," P1, 00:09:22–00:09:38 [to be presented with correlations because they deviate from how it was until now]). The thesis artifact does not currently do this, and participants know it — but the fact that this is the first image of "ideal system" P1 reaches for, unprompted, before touching the tool, reveals where the strategic user's perceived upside actually lies. It is not in query translation; it is in anomaly surfacing.

**Cross-subtheme implication.** The three value levels correspond to three different competitive references (onboarding cost, schema-lookup cost, analyst attention cost), three different interaction modes (answer generation, table ranking, proactive surfacing), and three different trust thresholds (high — you cannot verify what you do not know; medium — you can verify tables you are shown; low — you re-verify during strategic decision-making). The current system is closest to usable for the middle segment (T2.2) and furthest from usable for the top (T2.3) and bottom (T2.1) segments, which is the opposite of what a generic "user value" metric would suggest.

---

### Theme 3 — Acceptance turns on crossing an integration threshold

*Value is recognised but not realised. Both participants see potential — stated explicitly and repeatedly — but each locates a concrete integration barrier that prevents the system from being useful in its current form. The barrier is not SQL quality; it is the depth at which the system meets the enterprise data model, the deployment pathway through which it would be maintained, and the effort-to-answer parity that determines whether using it is worth it at all.*

This is the theme that most directly carries the "usability gap + articulated potential" framing of H3 in the critical path. Participants are neither dismissive nor enthusiastic; they are conditionally positive, and the conditions are concrete.

**T3.1 Effort-to-answer parity.** The most damning usability observation in the session concerns the ratio of input effort to output value. After navigating the system through a multi-step exchange where P1 has to supply the table name, the field name, and the domain vocabulary, he summarises:

> "Ein langer Weg zu einer einfachen Antwort vielleicht. Die Anzahl Klicks entspricht etwa der Anzahl an Tipps, die ich geben musste, was es dann unnütz macht." — P1, 01:05:45–01:06:00
> [A long path to a simple answer. The number of clicks corresponds roughly to the number of tips I had to give, which then makes it useless.]

The metric the user is implicitly applying is not correctness and not latency; it is *input-to-output ratio relative to the alternative*. If acquiring an answer from the system requires as much domain knowledge as acquiring it directly from Sage, the system's contribution is zero at the margin — and that is regardless of whether the final SQL was correct. This is a usability verdict, not a technical one, and it is the decisive negative finding of the session for the expert-in-the-loop mode.

**T3.2 The data-model bridge.** P2's diagnosis of why the system under-performed is not that the LLM is weak but that it was missing a structured representation of Sage's internal semantics. The fix he proposes is explicitly architectural:

> "Wäre es trotz alledem vielleicht besser, man könnte das Datenmodell der KI zeigen, dann wäre sie sehr wahrscheinlich ungemein treffsicher […] Die Bezeichnungen gibt es natürlich Überschneidungen, ich denke jetzt eben an Fremdfertigung, die hat einen Wareneingang, ein Bestellprozess hat auch einen Wareneingang, solche Fehler zu vermeiden." — P2, 01:44:33–01:45:08
> [It would perhaps be better if one could show the data model to the AI — then it would very likely be extremely accurate. The terms of course overlap — I'm thinking of external manufacturing, which has an inbound-goods process, and a purchase-order process also has an inbound-goods process; to avoid such mistakes.]

Two things are being said here simultaneously. First, Scout Mode's autonomous catalog — the thesis' core contribution — is being reframed by the technical participant as insufficient on its own: what he wants is the *tacit* domain structure (which "Wareneingang" is which) injected, not merely a ranked table list. Second, the proposed intervention is specifically to externalise what domain experts carry in their heads, and this overlap-disambiguation problem is precisely the one the Scout catalog cannot resolve without human-in-the-loop disambiguation. This is the single most architecturally consequential piece of feedback in the session.

**T3.3 Bolt-on versus platform pathway.** P1 closes the session by locating the system's deployment barrier outside the technology:

> "Ohne dass hier Softfolio, unser ERP Integrator, dem all sein Wissen rein spült, können wir es einfach so als Klette, die wir da drauf pappen, nicht selber nutzen. […] Wahrscheinlich müsste man mit so einer Idee zum ERP Lieferant gehen, der da sehr viel schneller seine Logik reinpflanzen könnte." — P1, 01:46:34–01:47:13
> [Without our ERP integrator, Softfolio, funneling all his knowledge into it, we can't use it ourselves as a burr we stick on top. Probably one would have to take an idea like this to the ERP vendor, who could plant his logic in much faster.]

The *Klette* (burr) image is precise: it describes a peripheral attachment that never reaches the host's interior. The participant is identifying a structural adoption pathway — the system must be delivered through the integrator channel (Softfolio) or through the ERP vendor (Sage itself), not as a third-party bolt-on. This is a channel-to-market observation about the product, not a feature request about the prototype. For an SME practice partner, the credible deployment pathway runs through existing ERP relationships because those are the only parties with the tacit domain model and the maintenance relationship in place.

**Deviant case for Theme 3.** The theme implies hopelessness in the short term, but both participants close positively on a *future* horizon and offer ongoing cooperation: P1 — "wir sind da jederzeit denke ich offen, dass sowohl als Versuchskaninchen als auch als Mitentwicklung" (02:01:16–02:01:30) [we are open at any time, both as guinea pigs and as co-development]; P2 — "von der Architektur her würde ich mir Gedanken machen […] dass man dem irgendwie besser das Datenmodell beibringen" (02:01:37–02:01:55) [from the architecture side I would think about how to better teach it the data model]. The barrier to adoption is real and specific, but the interest in the technology class is unambiguous. This is not a rejection; it is a conditional invitation.

---

## 4. Cross-theme synthesis

The three themes compose a single story. Theme 1 establishes that trust is not extended to the system; it has to be manufactured through verification scaffolding, and fabrication voids it categorically. Theme 2 establishes that the system's perceived payoff is not uniform: it is highest for novice enablement and strategic anomaly-surfacing, and lowest (because of effort parity, T3.1) for expert query work — which is paradoxically the regime the technical evaluation tested hardest. Theme 3 establishes that crossing from "potential" to "use" requires an integration threshold the current prototype does not meet: data-model injection (T3.2) and vendor-channel delivery (T3.1/T3.3) are the named prerequisites.

Taken together, the user-study evidence converges on a single propositional finding for H3: *the system is not usable today for routine SME ERP work, and users articulated a concrete set of conditions — architectural, organisational, and role-specific — under which they would expect it to become so.* This is the two-sided result Gap 6 of the critical-path document anticipates, and it is both more specific and more honest than the January 2025 supplementary analysis, which framed the same evidence primarily as operational obstacles rather than structural ones.

A second observation worth flagging: the participants' value narrative inverts the thesis' technical evaluation regime. The H2a/H2b work tested the system on SQL-generation accuracy — the middle layer (T2.2, expert-assistant). The highest-value segments the users identified (T2.1 novice multiplier, T2.3 proactive partner) are either untested by the current evaluation or not implemented at all. This is not a negative finding against the artifact; it is a mapping of where future evaluation work and future system development should concentrate if the goal is adoption rather than benchmark performance.

---

## 5. Crosswalk to prior coding

The January 2025 supplementary analysis used six codes (CWB, SC, SIE, TV, PVA, DQC). The mapping below records how the earlier evidence is re-expressed under the present themes; no extract from the earlier pass is dropped, but several are reassigned to a different meta-level.

| v1 code (Jan 2025) | v1 framing | v2 location | Re-interpretation |
|---|---|---|---|
| CWB (Cognitive Workload Burden) | operational friction during use | T3.1 effort-to-answer parity | Friction is not a usability nuisance; it is the decisive adoption-blocker at expert level |
| SC (SQL Coverage / Table Volume) | system-side capability gap | T3.2 data-model bridge | Reframed as missing domain semantics, not missing SQL capability |
| SIE (System Interaction Effort) | learning curve for the system | T2.1 novice multiplier (inverted) | What is a learning curve for experts is the intended *replacement* of a learning curve for novices |
| TV (Trust & Verification) | verification tooling as a feature | T1.1–T1.3 (three subthemes) | Trust is foundational, categorical, and structurally unresolved by more UI |
| PVA (Perceived Value of AI) | generic "it's useful" code | T2.1–T2.3 (stratified) | Perceived value is never generic; it splits cleanly by role |
| DQC (Data Quality Concerns) | data-side obstacles | Embedded in T3.2 and Theme 1 | Data-quality concerns are inseparable from trust concerns; separating them loses meaning |

---

## 6. Limitations of this analysis

The single-session, two-participant corpus supports theme identification but not theme prevalence claims. Joint-interview format permits but does not guarantee role-stability; the transcript shows stable P1-strategic / P2-technical positioning, which is a positive indicator. The researcher-participant relationship (practice-partner setup) biases toward constructive rather than adversarial feedback; participants' willingness to articulate the *Affe* and *Klette* metaphors suggests this bias did not fully suppress criticism, but it may have tempered it. Translations are analyst-produced and are documented inline so that the German original remains the primary evidential layer. Finally, this is a single-coder analysis; the themes should be treated as the analyst's best reading, not as a consensus finding.

---

## 7. References

Braun, V., & Clarke, V. (2006). Using thematic analysis in psychology. *Qualitative Research in Psychology*, 3(2), 77–101.

Braun, V., & Clarke, V. (2019). Reflecting on reflexive thematic analysis. *Qualitative Research in Sport, Exercise and Health*, 11(4), 589–597.

Braun, V., & Clarke, V. (2022). *Thematic Analysis: A Practical Guide*. Sage.

Hart, S. G., & Staveland, L. E. (1988). Development of NASA-TLX (Task Load Index): Results of empirical and theoretical research. *Advances in Psychology*, 52, 139–183.

Venkatesh, V., Thong, J. Y. L., & Xu, X. (2012). Consumer acceptance and use of information technology: Extending the unified theory of acceptance and use of technology. *MIS Quarterly*, 36(1), 157–178.
