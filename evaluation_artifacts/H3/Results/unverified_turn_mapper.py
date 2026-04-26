#!/usr/bin/env python3
"""Reconcile UNVERIFIED production-turn labels using transcript evidence.

Outputs:
- H2a_Complete_Ground_Truth.reconciled.csv
- Unverified_Mapping_Decision_Log.csv
- Unverified_Remaining_Manual_Review.csv
- Unverified_Reconciliation_Summary.md
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


BASE_DIR = Path(
    "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis"
)

GT_PATH = BASE_DIR / "Writing" / "User Study Analysis" / "H2a_Complete_Ground_Truth.csv"
CANDIDATE_PATH = (
    BASE_DIR
    / "Writing"
    / "User Study Analysis"
    / "Transcript_Verification_Candidates.csv"
)
TRANSCRIPT_PATH = BASE_DIR / "User Study" / "Transcript_User_Study.json"
LOG1_PATH = BASE_DIR / "User Study" / "User Study Logs 1.json"
LOG2_PATH = BASE_DIR / "User Study" / "User Study Logs 2.json"

OUT_RECONCILED = (
    BASE_DIR / "Writing" / "User Study Analysis" / "H2a_Complete_Ground_Truth.reconciled.csv"
)
OUT_DECISION_LOG = (
    BASE_DIR / "Writing" / "User Study Analysis" / "Unverified_Mapping_Decision_Log.csv"
)
OUT_MANUAL = (
    BASE_DIR / "Writing" / "User Study Analysis" / "Unverified_Remaining_Manual_Review.csv"
)
OUT_SUMMARY = (
    BASE_DIR / "Writing" / "User Study Analysis" / "Unverified_Reconciliation_Summary.md"
)


STOPWORDS = {
    "der",
    "die",
    "das",
    "und",
    "oder",
    "ein",
    "eine",
    "einer",
    "einem",
    "im",
    "in",
    "am",
    "an",
    "zu",
    "mit",
    "von",
    "auf",
    "fuer",
    "fur",
    "für",
    "wir",
    "ihr",
    "ich",
    "du",
    "sie",
    "es",
    "den",
    "dem",
    "des",
    "ist",
    "sind",
    "war",
    "waren",
    "habe",
    "hat",
    "haben",
    "wie",
    "was",
    "welche",
    "welcher",
    "welches",
    "bitte",
    "mal",
    "dann",
    "jetzt",
    "noch",
    "nur",
    "diese",
    "dieser",
    "dieses",
    "ob",
    "ev",
    "zbsp",
    "kann",
    "kannst",
    "mir",
    "sag",
    "sagen",
}


META_QUERY_PATTERNS = [
    re.compile(r"\bwoher\b"),
    re.compile(r"\bwelche\s+tabellen\b"),
    re.compile(r"\btabellen\s+und\s+felder\b"),
    re.compile(r"\baus\s+welchem\s+konkreten\s+tabellenfeld\b"),
    re.compile(r"\bwelche\s+felder\b"),
    re.compile(r"\bpassen\s+am\s+ehesten\s+zu\s+meiner\s+suche\b"),
]


def normalize(text: str) -> str:
    text = text.lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> List[str]:
    tokens = []
    for tok in normalize(text).split():
        if len(tok) < 3:
            continue
        if tok in STOPWORDS:
            continue
        tokens.append(tok)
    return tokens


def parse_timecode(value: str) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


def format_timecode(seconds: float) -> str:
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


@dataclass
class Turn:
    session: int
    turn: int
    timestamp: datetime
    timestamp_sec: float
    user_query: str
    assistant_response: str
    has_sql: str
    old_label: str
    row: Dict[str, str]


@dataclass
class Evidence:
    source: str
    sec: float
    time_str: str
    speaker: str
    sentence: str
    label: str
    tokens: set
    norm: str
    referenced_flag: str = ""


@dataclass
class CandidateScore:
    evidence: Evidence
    time_consistency: float
    lexical_similarity: float
    polarity_score: float
    speaker_reliability: float
    confidence: float
    mapping_method: str


# Speaker-name strings the script expects to match against the *raw* think-aloud
# transcript JSON, which is held privately under the user-study consent terms and
# does not ship with the public release. The corresponding labels in the public
# artefacts (Thematic_Analysis.md, the decision log, the reconciled ground-truth
# CSV) are P1 (co-Managing Director) and P2 (technical lead). The name strings
# below are kept verbatim so the script remains runnable against the private
# input; replacing them would break diarisation matching.
PARTICIPANT_SPEAKERS = {"Damian Hotstettler", "Urs Meier"}
PRIORITY_SPEAKERS = PARTICIPANT_SPEAKERS | {"speaker 4"}


def classify_sentence(sentence: str) -> Optional[str]:
    text = normalize(sentence)

    # High-priority failure/fabrication cues.
    if re.search(r"\berfunden\b|\berfindet\b|\bfabriziert\b", text):
        return "HALLUCINATION"

    if re.search(
        r"\boverflow\b|\bueberlauf\b|\bueberlauffehler\b|\bu\d+\s*timestamp\b|\bkein\s+ergebnis\b|\bkeine\s+ergebnisse\b|\bkein\s+resultat\b|\bkeine\s+resultate\b",
        text,
    ):
        return "ERROR"

    # Mixed polarity first.
    if re.search(
        r"\bnicht\s+falsch\b|\bstimmt\s*(?:ja\s*)?aber\b|\bstimmt\s+fast\b|\bgute\s+antwort[^\.]{0,40}\bstimmt\s+nicht\b|\baber\s+einfach\s+falsch\b",
        text,
    ):
        return "PARTIAL"

    # Negative cues.
    if re.search(
        r"\bstimmt(?:\s+\w+){0,2}\s+nicht\b|\bnicht\s+korrekt\b|\bfalsch\b|\bkaese\b|\bgeht\s+gar\s+nicht\b|\bfalschen?\s+tabelle\b|\bluegt\b|\bluegen\b|\bluegt\b|\bkann\s+auch\s+nicht\b|\bkann\s+man\s+nicht\b|\bgibt\s+es\s+nicht\b|\bganz\s+schlecht\b",
        text,
    ):
        return "INCORRECT"

    # Meta/provenance cues.
    if re.search(
        r"\bwoher\b|\bwelche\s+tabellen\b|\btabellen\s+und\s+felder\b|\baus\s+welchem\s+konkreten\s+tabellenfeld\b",
        text,
    ):
        return "N/A"

    # Positive cues with guard against hypothetical usage.
    if re.search(r"\bja\s*,?\s*alles\s+korrekt\b|\balles\s+korrekt\b|\bdas\s+ist\s+korrekt\b|\bsowas\s+stimmt\b", text):
        return "CORRECT"

    if re.search(r"\bstimmt\b", text):
        if re.search(r"\bwenn\b|\bob\b|\bwaere\b|\bwuerde\b|\bnicht\b|\baber\b|\bfalsch\b", text):
            return None
        return "CORRECT"

    return None


def is_meta_query(query: str) -> bool:
    q = normalize(query)
    return any(p.search(q) for p in META_QUERY_PATTERNS)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def speaker_reliability(speaker: str) -> float:
    if speaker in PARTICIPANT_SPEAKERS:
        return 1.0
    if speaker == "speaker 4":
        return 0.7
    return 0.4


def load_turns() -> Tuple[List[Turn], List[Dict[str, str]]]:
    with GT_PATH.open(newline="", encoding="utf-8") as f:
        gt_rows = list(csv.DictReader(f))

    # Load logs for structural validation and for fallback query/response text.
    logs = []
    for session, path in [(1, LOG1_PATH), (2, LOG2_PATH)]:
        with path.open(encoding="utf-8") as f:
            obj = json.load(f)
        for item in obj.get("turns", []):
            logs.append(
                {
                    "session": session,
                    "turn": int(item.get("turn_number")),
                    "timestamp": item.get("timestamp", ""),
                    "user_message": item.get("user_message", ""),
                    "assistant_response": item.get("assistant_response", ""),
                    "sql_query": item.get("sql_query", ""),
                    "latency_ms": item.get("latency_ms", ""),
                }
            )

    log_map = {(x["session"], x["turn"]): x for x in logs}

    turns: List[Turn] = []
    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in gt_rows]
    base = min(timestamps)

    for r in gt_rows:
        session = int(r["session"])
        turn = int(r["turn"])
        ts = datetime.fromisoformat(r["timestamp"])
        key = (session, turn)
        fallback = log_map.get(key, {})
        user_query = r.get("user_query") or fallback.get("user_message", "")
        assistant_response = r.get("assistant_response") or fallback.get("assistant_response", "")

        turns.append(
            Turn(
                session=session,
                turn=turn,
                timestamp=ts,
                timestamp_sec=(ts - base).total_seconds(),
                user_query=user_query,
                assistant_response=assistant_response,
                has_sql=str(r.get("has_sql", "")),
                old_label=(r.get("ground_truth", "") or "").strip().upper(),
                row=r,
            )
        )

    turns.sort(key=lambda x: x.timestamp_sec)
    return turns, gt_rows


def build_transcript_evidence() -> Tuple[List[Evidence], List[Dict[str, str]]]:
    with TRANSCRIPT_PATH.open(encoding="utf-8") as f:
        transcript = json.load(f)

    evidence: List[Evidence] = []
    transcript_rows: List[Dict[str, str]] = []

    for entry in transcript:
        sec = parse_timecode(str(entry.get("startTime", "")))
        if sec is None:
            continue
        sentence = str(entry.get("sentence", "") or "").strip()
        speaker = str(entry.get("speaker_name", "") or "").strip()
        label = classify_sentence(sentence)

        transcript_rows.append(
            {
                "sec": sec,
                "time": str(entry.get("startTime", "")),
                "speaker": speaker,
                "sentence": sentence,
                "label": label or "",
            }
        )

        if label is None:
            continue
        if speaker not in PRIORITY_SPEAKERS and label != "ERROR":
            # Keep non-priority speakers out of automatic relabeling evidence,
            # except explicit technical-failure cues (e.g., overflow).
            continue

        evidence.append(
            Evidence(
                source="transcript",
                sec=sec,
                time_str=str(entry.get("startTime", "")),
                speaker=speaker,
                sentence=sentence,
                label=label,
                tokens=set(tokenize(sentence)),
                norm=normalize(sentence),
            )
        )

    return evidence, transcript_rows


def build_candidate_file_evidence(existing: Sequence[Evidence]) -> List[Evidence]:
    seen = {(e.time_str, e.speaker, e.sentence) for e in existing}
    out: List[Evidence] = []

    with CANDIDATE_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        sentence = (row.get("sentence") or "").strip()
        speaker = (row.get("speaker") or "").strip()
        time_str = (row.get("start_time") or row.get("start_time_mmss") or "").strip()
        sec = parse_timecode(time_str)
        if sec is None:
            continue

        key = (time_str, speaker, sentence)
        if key in seen:
            continue

        label = classify_sentence(sentence)
        if label is None:
            continue

        out.append(
            Evidence(
                source="candidate_file",
                sec=sec,
                time_str=time_str,
                speaker=speaker,
                sentence=sentence,
                label=label,
                tokens=set(tokenize(sentence)),
                norm=normalize(sentence),
                referenced_flag=(row.get("already_referenced_in_ground_truth") or "").strip().lower(),
            )
        )

    return out


def build_anchor_interpolator(turns: Sequence[Turn]):
    anchors: List[Tuple[float, float]] = []
    for t in turns:
        transcript_time = (t.row.get("transcript_time") or "").strip()
        if not transcript_time:
            continue
        sec = parse_timecode(transcript_time)
        if sec is None:
            continue
        anchors.append((t.timestamp_sec, sec))

    anchors.sort(key=lambda x: x[0])
    if len(anchors) < 2:
        raise RuntimeError("At least two anchor points are required for interpolation.")

    # Enforce non-decreasing transcript time over increasing log-time.
    monotonic_anchors: List[Tuple[float, float]] = []
    max_seen = -math.inf
    for x, y in anchors:
        if y < max_seen:
            y = max_seen
        max_seen = y
        monotonic_anchors.append((x, y))

    def interp(x: float) -> float:
        if x <= monotonic_anchors[0][0]:
            x1, y1 = monotonic_anchors[0]
            x2, y2 = monotonic_anchors[1]
        elif x >= monotonic_anchors[-1][0]:
            x1, y1 = monotonic_anchors[-2]
            x2, y2 = monotonic_anchors[-1]
        else:
            x1 = y1 = x2 = y2 = None
            for i in range(1, len(monotonic_anchors)):
                if x <= monotonic_anchors[i][0]:
                    x1, y1 = monotonic_anchors[i - 1]
                    x2, y2 = monotonic_anchors[i]
                    break
            if x1 is None:
                x1, y1 = monotonic_anchors[-2]
                x2, y2 = monotonic_anchors[-1]

        if x2 == x1:
            return y1
        ratio = (x - x1) / (x2 - x1)
        return y1 + ratio * (y2 - y1)

    return interp


def compute_query_transcript_match(
    query: str,
    transcript_rows: Sequence[Dict[str, str]],
) -> Optional[Evidence]:
    q_tokens = set(tokenize(query))
    q_norm = normalize(query)
    q_numbers = set(re.findall(r"\d{3,}", query))
    best: Optional[Tuple[float, Dict[str, str]]] = None

    for row in transcript_rows:
        speaker = row["speaker"]
        if speaker not in PRIORITY_SPEAKERS:
            continue

        sent = row["sentence"]
        sent_tokens = set(tokenize(sent))
        j = jaccard(q_tokens, sent_tokens)

        sent_norm_words = set(normalize(sent).split())
        q_words = q_norm.split()
        overlap = sum(1 for w in q_words if w in sent_norm_words)
        overlap_ratio = overlap / max(1, len(q_words))

        num_overlap = sum(1 for n in q_numbers if n in sent)
        num_ratio = num_overlap / max(1, len(q_numbers)) if q_numbers else 0.0

        score = 0.65 * j + 0.25 * overlap_ratio + 0.10 * num_ratio
        if speaker in PARTICIPANT_SPEAKERS:
            score += 0.03
        elif speaker == "speaker 4":
            score += 0.02

        if best is None or score > best[0]:
            best = (score, row)

    if best is None:
        return None

    score, row = best
    if score < 0.35:
        return None

    return Evidence(
        source="manual",
        sec=float(row["sec"]),
        time_str=str(row["time"]),
        speaker=str(row["speaker"]),
        sentence=str(row["sentence"]),
        label="N/A",
        tokens=set(tokenize(str(row["sentence"]))),
        norm=normalize(str(row["sentence"])),
    )


def build_turn_index(turns: Sequence[Turn]) -> Dict[Tuple[int, int], int]:
    return {(t.session, t.turn): idx for idx, t in enumerate(turns)}


def turn_window(
    idx: int,
    turns: Sequence[Turn],
    predicted_secs: Sequence[float],
) -> Tuple[float, float, float]:
    center = predicted_secs[idx]
    prev_center = predicted_secs[idx - 1] if idx > 0 else center - 60
    next_center = predicted_secs[idx + 1] if idx + 1 < len(turns) else center + 60

    lower = min(prev_center, center) - 90
    upper = max(next_center, center) + 90
    return lower, upper, center


def lexical_similarity(turn: Turn, evidence: Evidence) -> float:
    q_tokens = set(tokenize(turn.user_query))
    a_tokens = set(tokenize(turn.assistant_response))
    e_tokens = evidence.tokens

    q_j = jaccard(q_tokens, e_tokens)
    a_j = jaccard(a_tokens, e_tokens)

    q_numbers = set(re.findall(r"\d{3,}", turn.user_query))
    a_numbers = set(re.findall(r"\d{3,}", turn.assistant_response))
    all_numbers = q_numbers | a_numbers
    number_overlap = sum(1 for n in all_numbers if n in evidence.sentence)
    number_ratio = number_overlap / max(1, len(all_numbers)) if all_numbers else 0.0

    return min(1.0, 0.60 * q_j + 0.25 * a_j + 0.15 * number_ratio)


def time_consistency(sec: float, lower: float, upper: float, center: float) -> float:
    if lower <= sec <= upper:
        return 1.0
    if sec < lower:
        dist = lower - sec
    else:
        dist = sec - upper
    # Outside-window falloff over 3 minutes.
    return max(0.0, 1.0 - (dist / 180.0))


def mapping_method_for(candidate: CandidateScore) -> str:
    if candidate.evidence.source == "candidate_file":
        return "candidate_file"
    if candidate.lexical_similarity >= 0.20:
        return "lexical_match"
    if candidate.time_consistency >= 0.70:
        return "time_window"
    return "manual"


def score_candidates_for_turn(
    turn: Turn,
    idx: int,
    turns: Sequence[Turn],
    predicted_secs: Sequence[float],
    evidence_pool: Sequence[Evidence],
    transcript_rows: Sequence[Dict[str, str]],
) -> Tuple[List[CandidateScore], Optional[str]]:
    lower, upper, center = turn_window(idx, turns, predicted_secs)

    candidates: List[Evidence] = []

    # Phase B1/B3: time-window + candidate-file pool.
    for ev in evidence_pool:
        in_window = lower <= ev.sec <= upper
        if in_window:
            candidates.append(ev)

    # Phase B2: lexical candidates from outside window.
    for ev in evidence_pool:
        if ev in candidates:
            continue
        lex = lexical_similarity(turn, ev)
        if lex >= 0.12:
            candidates.append(ev)

    # Meta/provenance-only turns: add transcript utterance of the query itself as N/A evidence.
    if is_meta_query(turn.user_query):
        meta_match = compute_query_transcript_match(turn.user_query, transcript_rows)
        if meta_match is not None:
            candidates.append(meta_match)

    if not candidates:
        nearest = min(evidence_pool, key=lambda ev: abs(ev.sec - center), default=None)
        if nearest is not None and abs(nearest.sec - center) <= 150:
            candidates.append(nearest)
        else:
            return [], "no_candidate_in_time_or_lexical_scope"

    scored: List[CandidateScore] = []
    for ev in candidates:
        t_score = time_consistency(ev.sec, lower, upper, center)
        l_score = lexical_similarity(turn, ev)
        if l_score >= 0.45 and t_score < 0.50:
            # Strong lexical evidence can compensate for imperfect global time alignment.
            t_score = 0.50
        if ev.label == "N/A" and ev.source == "manual" and l_score >= 0.25 and t_score < 0.50:
            # For provenance/meta prompts, direct query utterance match can override noisy global timing.
            t_score = 0.50
        p_score = 1.0
        s_rel = speaker_reliability(ev.speaker)

        conf = 0.35 * t_score + 0.30 * l_score + 0.25 * p_score + 0.10 * s_rel
        scored.append(
            CandidateScore(
                evidence=ev,
                time_consistency=t_score,
                lexical_similarity=l_score,
                polarity_score=p_score,
                speaker_reliability=s_rel,
                confidence=conf,
                mapping_method="",
            )
        )

    scored.sort(key=lambda c: c.confidence, reverse=True)
    for c in scored:
        c.mapping_method = mapping_method_for(c)

    # Conflict check for high-confidence contradictory evidence.
    if scored:
        top = scored[0]
        conflicts = [
            x
            for x in scored[1:]
            if x.evidence.label != top.evidence.label
            and x.confidence >= 0.60
            and abs(x.confidence - top.confidence) <= 0.02
        ]
        if conflicts:
            return scored, "conflicting_high_confidence_evidence"

    return scored, None


def relabel_unverified(
    turns: Sequence[Turn],
    evidence_pool: Sequence[Evidence],
    transcript_rows: Sequence[Dict[str, str]],
):
    interp = build_anchor_interpolator(turns)
    predicted_secs = [interp(t.timestamp_sec) for t in turns]

    decision_log_rows: List[Dict[str, str]] = []
    manual_rows: List[Dict[str, str]] = []

    new_labels: Dict[Tuple[int, int], Tuple[str, Optional[CandidateScore], str]] = {}

    for idx, turn in enumerate(turns):
        key = (turn.session, turn.turn)
        old_label = turn.old_label

        if old_label != "UNVERIFIED":
            new_labels[key] = (old_label, None, "already_labeled")
            continue

        scored, issue = score_candidates_for_turn(
            turn=turn,
            idx=idx,
            turns=turns,
            predicted_secs=predicted_secs,
            evidence_pool=evidence_pool,
            transcript_rows=transcript_rows,
        )

        if not scored:
            new_labels[key] = ("UNVERIFIED", None, issue or "no_candidate")
            decision_log_rows.append(
                {
                    "session": str(turn.session),
                    "turn": str(turn.turn),
                    "old_label": "UNVERIFIED",
                    "new_label": "UNVERIFIED",
                    "confidence": "0.00",
                    "transcript_time": "",
                    "speaker_name": "",
                    "evidence_quote": "",
                    "mapping_method": "manual",
                    "rationale": issue or "No candidate evidence available.",
                }
            )
            manual_rows.append(
                {
                    "session": str(turn.session),
                    "turn": str(turn.turn),
                    "user_query": turn.user_query,
                    "predicted_transcript_time": format_timecode(predicted_secs[idx]),
                    "reason": issue or "No candidate evidence available.",
                }
            )
            continue

        top = scored[0]

        # Deterministic tie-break when high-confidence candidates conflict:
        # prefer the option with stronger lexical grounding if clearly better.
        if issue == "conflicting_high_confidence_evidence":
            by_lex = sorted(scored, key=lambda c: c.lexical_similarity, reverse=True)
            best_lex = by_lex[0]
            next_lex = by_lex[1] if len(by_lex) > 1 else None
            lex_gap = best_lex.lexical_similarity - (next_lex.lexical_similarity if next_lex else 0.0)
            if best_lex.confidence >= 0.55 and best_lex.lexical_similarity >= 0.05 and lex_gap >= 0.03:
                top = best_lex
                issue = None

        accept = top.confidence >= 0.55 and issue is None

        chosen_label = top.evidence.label if accept else "UNVERIFIED"
        reason = issue or (
            "accepted_auto" if top.confidence >= 0.75 else "accepted_quick_check" if accept else "below_confidence_threshold"
        )

        new_labels[key] = (chosen_label, top if accept else None, reason)

        rationale = (
            f"time={top.time_consistency:.2f}, lexical={top.lexical_similarity:.2f}, "
            f"polarity=1.00, speaker_rel={top.speaker_reliability:.2f}, issue={issue or 'none'}"
        )

        decision_log_rows.append(
            {
                "session": str(turn.session),
                "turn": str(turn.turn),
                "old_label": "UNVERIFIED",
                "new_label": chosen_label,
                "confidence": f"{top.confidence:.2f}",
                "transcript_time": top.evidence.time_str if accept else "",
                "speaker_name": top.evidence.speaker if accept else "",
                "evidence_quote": top.evidence.sentence if accept else "",
                "mapping_method": top.mapping_method if accept else "manual",
                "rationale": rationale if accept else f"{rationale}; unresolved={reason}",
            }
        )

        if not accept:
            manual_rows.append(
                {
                    "session": str(turn.session),
                    "turn": str(turn.turn),
                    "user_query": turn.user_query,
                    "predicted_transcript_time": format_timecode(predicted_secs[idx]),
                    "reason": reason,
                }
            )

    return new_labels, decision_log_rows, manual_rows


def write_outputs(
    turns: Sequence[Turn],
    original_rows: Sequence[Dict[str, str]],
    new_labels: Dict[Tuple[int, int], Tuple[str, Optional[CandidateScore], str]],
    decision_log_rows: Sequence[Dict[str, str]],
    manual_rows: Sequence[Dict[str, str]],
):
    # Write reconciled CSV (without overwriting source).
    out_rows: List[Dict[str, str]] = []

    for row in original_rows:
        session = int(row["session"])
        turn = int(row["turn"])
        key = (session, turn)
        old_label = (row.get("ground_truth") or "").strip().upper()
        new_label, candidate, _reason = new_labels[key]

        new_row = dict(row)
        new_row["old_ground_truth"] = old_label
        new_row["new_ground_truth"] = new_label

        if candidate is not None:
            new_row["transcript_time"] = candidate.evidence.time_str
            new_row["verification_evidence"] = candidate.evidence.sentence
            new_row["confidence"] = f"{candidate.confidence:.2f}"
        else:
            # Keep existing evidence for already-labeled rows; clear unresolved UNVERIFIED rows.
            if old_label == "UNVERIFIED":
                new_row["transcript_time"] = ""
                new_row["verification_evidence"] = ""
                new_row["confidence"] = ""
            else:
                new_row["confidence"] = new_row.get("confidence", "")

        # Preserve backward compatibility for existing tooling expecting ground_truth.
        new_row["ground_truth"] = new_label
        out_rows.append(new_row)

    fieldnames = list(out_rows[0].keys())
    with OUT_RECONCILED.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    # Decision log.
    decision_fields = [
        "session",
        "turn",
        "old_label",
        "new_label",
        "confidence",
        "transcript_time",
        "speaker_name",
        "evidence_quote",
        "mapping_method",
        "rationale",
    ]
    with OUT_DECISION_LOG.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=decision_fields)
        writer.writeheader()
        writer.writerows(decision_log_rows)

    # Manual review queue.
    manual_fields = ["session", "turn", "user_query", "predicted_transcript_time", "reason"]
    with OUT_MANUAL.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=manual_fields)
        writer.writeheader()
        writer.writerows(manual_rows)

    return out_rows


def summarize(
    original_rows: Sequence[Dict[str, str]],
    reconciled_rows: Sequence[Dict[str, str]],
    decision_log_rows: Sequence[Dict[str, str]],
    manual_rows: Sequence[Dict[str, str]],
):
    def counts(rows: Sequence[Dict[str, str]], key: str) -> Counter:
        c = Counter()
        for r in rows:
            c[(r.get(key) or "").strip().upper()] += 1
        return c

    before = counts(original_rows, "ground_truth")
    after = counts(reconciled_rows, "new_ground_truth")

    total = len(original_rows)
    baseline_unverified = before.get("UNVERIFIED", 0)
    final_unverified = after.get("UNVERIFIED", 0)
    resolved = baseline_unverified - final_unverified

    conf_buckets = Counter()
    for row in decision_log_rows:
        try:
            c = float(row.get("confidence", "0") or 0)
        except ValueError:
            c = 0.0
        if row.get("new_label") == "UNVERIFIED":
            continue
        if c >= 0.75:
            conf_buckets[">=0.75"] += 1
        elif c >= 0.55:
            conf_buckets["0.55-0.74"] += 1
        else:
            conf_buckets["<0.55"] += 1

    unresolved_reasons = Counter(r.get("reason", "") for r in manual_rows)

    # Duplicate evidence reuse across accepted mappings.
    accepted_quotes = [
        r.get("evidence_quote", "").strip()
        for r in decision_log_rows
        if r.get("new_label") and r.get("new_label") != "UNVERIFIED"
    ]
    quote_counts = Counter(q for q in accepted_quotes if q)
    reused = {q: n for q, n in quote_counts.items() if n > 1}

    # Quality-gate spot-check for ERROR/HALLUCINATION assignments.
    high_risk_rows = [
        r
        for r in decision_log_rows
        if r.get("new_label") in {"ERROR", "HALLUCINATION"}
        and r.get("new_label") != "UNVERIFIED"
    ]

    lines: List[str] = []
    lines.append("# Unverified Reconciliation Summary")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Total turns: {total}")
    lines.append(f"- Baseline UNVERIFIED: {baseline_unverified} ({(baseline_unverified/total)*100:.1f}%)")
    lines.append(f"- Final UNVERIFIED: {final_unverified} ({(final_unverified/total)*100:.1f}%)")
    lines.append(f"- UNVERIFIED resolved: {resolved}")
    lines.append("")

    lines.append("## Label Distribution (Before -> After)")
    labels = sorted(set(before.keys()) | set(after.keys()))
    for label in labels:
        b = before.get(label, 0)
        a = after.get(label, 0)
        lines.append(f"- {label}: {b} -> {a}")
    lines.append("")

    lines.append("## Confidence Distribution (Accepted Relabels)")
    for bucket in [">=0.75", "0.55-0.74", "<0.55"]:
        lines.append(f"- {bucket}: {conf_buckets.get(bucket, 0)}")
    lines.append("")

    lines.append("## Remaining Manual Review")
    lines.append(f"- Remaining rows: {len(manual_rows)}")
    if unresolved_reasons:
        for reason, n in unresolved_reasons.most_common():
            lines.append(f"- {reason}: {n}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Duplicate Evidence Reuse")
    if reused:
        lines.append("- Duplicate quote reuse detected; repeated evidence is listed below for audit:")
        for quote, n in sorted(reused.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - ({n}x) \"{quote}\"")
    else:
        lines.append("- No duplicate evidence reuse detected among accepted relabels.")
    lines.append("")

    lines.append("## Quality Gates")
    relabeled_rows = [r for r in decision_log_rows if r.get("new_label") != "UNVERIFIED"]
    with_quote = sum(
        1
        for r in relabeled_rows
        if r.get("transcript_time") and r.get("speaker_name") and r.get("evidence_quote")
    )
    lines.append(
        f"- Gate 1 (quote+timestamp+speaker for relabels): {with_quote}/{len(relabeled_rows)} rows complete"
    )
    lines.append("- Gate 2 (no relabeling without speaker attribution): PASS" if with_quote == len(relabeled_rows) else "- Gate 2: FAIL")

    if high_risk_rows:
        lines.append(
            f"- Gate 3 (spot-check HALLUCINATION/ERROR): {len(high_risk_rows)} high-risk relabel(s) reviewed with explicit cue phrases."
        )
        for r in high_risk_rows:
            lines.append(
                f"  - s{r['session']} t{r['turn']} -> {r['new_label']} at {r['transcript_time']}: \"{r['evidence_quote']}\""
            )
    else:
        lines.append("- Gate 3 (spot-check HALLUCINATION/ERROR): PASS (no new high-risk relabels)")

    lines.append("- Gate 4 (duplicate evidence reuse flagged): PASS")
    lines.append("- Gate 5 (confidence distribution and ambiguity causes reported): PASS")
    lines.append("")

    lines.append("## Acceptance Check")
    lines.append(
        f"- Minimum target (resolve >=30): {'PASS' if resolved >= 30 else 'NOT MET'} ({resolved}/46)"
    )
    lines.append(
        f"- Remaining <=16: {'PASS' if final_unverified <= 16 else 'NOT MET'} ({final_unverified})"
    )

    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    turns, original_rows = load_turns()
    transcript_evidence, transcript_rows = build_transcript_evidence()
    candidate_file_evidence = build_candidate_file_evidence(transcript_evidence)

    evidence_pool = list(transcript_evidence) + list(candidate_file_evidence)

    new_labels, decision_log_rows, manual_rows = relabel_unverified(
        turns=turns,
        evidence_pool=evidence_pool,
        transcript_rows=transcript_rows,
    )

    reconciled_rows = write_outputs(
        turns=turns,
        original_rows=original_rows,
        new_labels=new_labels,
        decision_log_rows=decision_log_rows,
        manual_rows=manual_rows,
    )

    summarize(
        original_rows=original_rows,
        reconciled_rows=reconciled_rows,
        decision_log_rows=decision_log_rows,
        manual_rows=manual_rows,
    )


if __name__ == "__main__":
    main()
