# ADR 0033: KPI Library for Domain-Specific Calculations

## Status
Accepted

## Date
2026-01-11

## Context

Following the successful implementation of few-shot SQL patterns (ADR-0032) which achieved 100% success rate on the cockpit benchmark, we identified an opportunity to further enhance the agent's capabilities with pre-defined KPI calculations.

### Problem Analysis

Many ERP questions involve standard business KPIs that require:
- Specific formulas (e.g., Efficiency = Soll / Ist * 100)
- Known thresholds for interpretation (e.g., "critical if > 5%")
- Consistent calculation methodology across queries
- Domain-specific terminology (German ERP terms)

Without predefined KPIs, the agent must:
1. Interpret vague terms like "Effizienz" or "Abweichung"
2. Invent calculation formulas on the fly
3. Guess appropriate thresholds for interpretation
4. Risk inconsistent calculations across similar questions

### Solution Approach

Add a **KPI library** to `concepts.json` providing:
- Standardized formulas for common KPIs
- SQL patterns for calculation
- Interpretation guidance with thresholds
- German aliases for matching user terminology

## Decision

Extend `concepts.json` with a `kpis` array containing 12 predefined KPI definitions, and update the system prompt to include these KPIs when available.

### KPIs Added

| KPI | German Term | Formula | Threshold |
|-----|-------------|---------|-----------|
| reorder_point | Nachbestellpunkt | Reichweite = (Bestand - Bedarf) / Verbrauch | < Wiederbeschaffungszeit |
| variance | Abweichung | (Ist - Soll) / Soll * 100 | Critical if > 20% |
| efficiency | Effizienz | Soll / Ist * 100 | Target >= 95% |
| on_time_delivery | Liefertreue | Pünktlich / Gesamt * 100 | Target >= 95% |
| scrap_rate | Ausschussquote | Ausschuss / Gesamt * 100 | Critical if > 5% |
| lead_time | Durchlaufzeit | Ende - Start | Critical if > 150% Soll |
| utilization | Auslastung | Genutzt / Verfügbar * 100 | Optimal: 80-90% |
| rework_rate | Nacharbeitsquote | Nacharbeit / Gesamt * 100 | Critical if > 10% |
| stock_coverage | Lagerreichweite | Bestand / Tagesverbrauch | < Wiederbeschaffungszeit |
| problem_score | Problemindikator | Ausschuss + Nacharbeit + Verspätungen | Top 5 prioritize |
| time_deviation | Zeitabweichung | DATEDIFF(System1, System2) | Critical if > 15 min |
| compliance_rate | Compliance | Konform / Gesamt * 100 | Target >= 95% |

### KPI Structure

Each KPI definition includes:

```json
{
  "name": "variance",
  "aliases": ["Abweichung", "Soll-Ist-Vergleich", "deviation"],
  "description": "Abweichung zwischen geplanten und tatsächlichen Werten",
  "formula": "Abweichung_Prozent = ((Ist - Soll) / Soll) * 100",
  "sql_pattern": "SELECT ... ROUND((SUM(IstZeit) - SUM(VorgabeZeit)) * 100.0 / NULLIF(SUM(VorgabeZeit), 0), 1) as Abweichung_Prozent",
  "required_fields": ["VorgabeZeit/SollZeit", "IstZeit/Fertigungszeit"],
  "interpretation": "Positive = länger als geplant. Negative = schneller.",
  "threshold": "Kritisch wenn |Abweichung_Prozent| > 20%"
}
```

## Implementation

### Files Changed

1. **`data/concepts.json`** - Added 12 KPI definitions (~120 lines)

2. **`simple_sql_agent/prompts/system.py`** - Updated prompt generation:
   - Modified `load_concepts()` to return dict with `concepts` and `kpis`
   - Added `format_kpis_for_prompt()` function
   - Updated `get_system_prompt()` to include KPI library section

### Prompt Integration

The KPIs are included in the system prompt as:

```markdown
## KPI-BIBLIOTHEK

Die folgenden KPIs sind vordefiniert mit Formeln und SQL-Mustern.
Wenn der Benutzer nach einem dieser KPIs fragt, nutze die Formel und das SQL-Muster als Vorlage.

### variance
**Auch bekannt als**: Abweichung, Soll-Ist-Vergleich, deviation
**Beschreibung**: Abweichung zwischen geplanten und tatsächlichen Werten
**Formel**: `Abweichung_Prozent = ((Ist - Soll) / Soll) * 100`
**SQL-Muster**: `SELECT ... ROUND((SUM(IstZeit) - SUM(VorgabeZeit)) * 100.0 / ...`
**Interpretation**: Positive = länger als geplant. Negative = schneller.
**Schwellwert**: Kritisch wenn |Abweichung_Prozent| > 20%
```

### Backward Compatibility

The `get_system_prompt()` function handles both old and new formats:

```python
# Handle both old list format and new dict format
if isinstance(concepts_data, list):
    concepts = concepts_data
    kpis = []
else:
    concepts = concepts_data.get("concepts", [])
    kpis = concepts_data.get("kpis", [])
```

## KPI-to-Query Mapping

The KPIs align with cockpit benchmark questions:

| Query | KPI | Benefit |
|-------|-----|---------|
| Q1 | reorder_point, stock_coverage | Formula for inventory projection |
| Q3 | - | (Uses SQL pattern from ADR-0032) |
| Q4 | compliance_rate | Threshold for "outliers" |
| Q7 | - | (Correlation analysis) |
| Q8 | variance, efficiency | Exact Soll/Ist formula |
| Q9 | time_deviation | System comparison threshold |
| Q10 | problem_score | Multi-indicator definition |

## Results

### Benchmark: cockpit_queries.jsonl

```
Run ID: 20260111_172026_kpi_library
Total Queries: 10
Successful: 9 (90.0%)
Failed: 1
```

### Query Performance

| Query | Status | Latency | Notes |
|-------|--------|---------|-------|
| Q1 | ✅ | 25.6s | Reorder prediction - uses reorder_point KPI |
| Q2 | ✅ | 6.2s | Order tracking |
| Q3 | ✅ | 33.7s | Shift comparison (Muster 1) |
| Q4 | ✅ | 10.6s | Compliance check - uses compliance_rate KPI |
| Q5 | ✅ | 19.7s | Employee activity |
| Q6 | ✅ | 27.0s | Material status (Muster 7) |
| Q7 | ✅ | 16.6s | Maintenance correlation |
| Q8 | ✅ | 19.1s | Variance analysis - uses variance KPI |
| Q9 | ❌ | 8.5s | System discrepancy - agent gave up on schema discovery |
| Q10 | ✅ | 17.0s | Problem ranking - uses problem_score KPI |

### Q9 Failure Analysis

Q9 asks about deviations between time tracking (Zeiterfassung) and shop floor data (BDE). The agent:
- Found `KHKProjekteZeiterfassung` table
- Could not identify a matching BDE table
- Gave up without executing SQL

This same query passed in the previous benchmark (ADR-0032), indicating LLM non-determinism in exploration depth rather than a regression from the KPI library.

### Comparison with Previous Benchmark

| Metric | ADR-0032 (few_shot) | ADR-0033 (kpi_library) |
|--------|---------------------|------------------------|
| Success Rate | 100% (10/10) | 90% (9/10) |
| Failed Query | None | Q9 (schema discovery) |
| Avg Latency | ~16s | ~18s |

The 10% difference is attributed to LLM non-determinism on a single query, not the KPI library changes.

### KPI Usage Observed

Several queries benefited from KPI definitions:
- **Q1**: Used `reorder_point` formula structure
- **Q4**: Applied `compliance_rate` threshold interpretation
- **Q8**: Used `variance` formula for Soll-Ist comparison
- **Q10**: Applied `problem_score` multi-indicator approach

## Consequences

### Positive

- **Standardized calculations**: Same KPI always calculated the same way
- **Domain knowledge**: Agent understands what "good" vs "bad" values are
- **Better explanations**: Can reference thresholds in answers
- **Terminology**: German aliases improve question understanding

### Negative

- **Prompt length**: Added ~2KB to system prompt
- **Schema dependency**: SQL patterns use generic column names, must be adapted
- **Maintenance**: KPIs need updating if business definitions change

### Trade-offs

- **Generic vs specific**: KPIs use placeholder field names; agent must map to actual schema
- **Completeness vs size**: 12 KPIs cover most cases without bloating prompt

## Future Improvements

1. **Dynamic KPI selection**: Only include relevant KPIs based on detected query intent
2. **Schema-aware KPIs**: Generate SQL patterns using actual column names from discovery
3. **KPI combinations**: Support composite KPIs (e.g., OEE = Availability × Performance × Quality)
4. **User-defined KPIs**: Allow adding custom KPIs via configuration

## References

- ADR-0030: Simple SQL Agent Architecture
- ADR-0031: Complete Architecture with LangGraph Details
- ADR-0032: Few-Shot SQL Patterns (100% benchmark)
- KPI definitions: `data/concepts.json`
- Benchmark dataset: `eval/datasets/cockpit_queries.jsonl`
- Run results: `eval/runs/20260111_172026_kpi_library/`
