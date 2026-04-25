# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for *Proactive Context Learning for LLM-Based ERP Database Querying in SMEs*. They document the architectural evolution of the system over roughly one year of development (April 2025 – April 2026) and are a primary artefact for the thesis.

This README tells the story. For a machine-readable index, see [`adr-index.yaml`](adr-index.yaml). For the ADR template, see [`ADR_TEMPLATE.md`](ADR_TEMPLATE.md).

## How to read the ADRs

- **Chronological order carries the narrative.** The system went through several deliberate pivots — its database target, its transport, its agent architecture, its ablation methodology. Each pivot is captured in an ADR, and every ADR it invalidated is marked with a `Superseded by` note in its Status line.
- **ADRs without a supersede note are live.** They describe the current architecture.
- **Phase 1–6 ADRs** often describe earlier architectures; follow the supersede links to see what replaced them.
- **Some ADR numbers are duplicated** (0003, 0011, 0032). This is historical — parallel branches of work were sometimes assigned the same number. Both files are retained for archival accuracy rather than renumbered, because the code commits they accompany reference the original filenames.
- **Format drift.** Early ADRs (Phases 1–4) predate the current template and fail the linter in [`../scripts/adr_lint.sh`](../scripts/adr_lint.sh). They are preserved as written. New ADRs follow [`ADR_TEMPLATE.md`](ADR_TEMPLATE.md).

---

## The storyline, by phase

### Phase 1 — Synthetic data and prototype agent (April–May 2025)

The project began with a synthetic ERP data generator so the system could be developed and evaluated in isolation, before access to a real production database was arranged.

- [ADR-0001](0001-synthetic-data-service-architecture.md) — Synthetic Data Service Architecture *(superseded)*
- [ADR-0002](0002-synthetic-data-results-and-database-access.md) — Synthetic Data Results and Database Access *(superseded)*
- [ADR-0003](0003-extended-data-models-document-store-and-graph-database.md) — Extended Data Models: Document Store and Graph Database
- [ADR-0003](0003-postgresql-migration-and-enhanced-data-generation.md) — PostgreSQL Migration and Enhanced Data Generation
- [ADR-0004](0004-crawling-agent-architecture.md) — Crawling Agent Architecture
- [ADR-0005](0005-model-context-protocol.md) — Adoption of Model-Context Protocol
- [ADR-0006](0006-agent-architecture-and-data-integration.md) — Agent Architecture and Data Integration

### Phase 2 — MCP integration and UI (September 2025)

With the prototype in place, the system formalised around the Model Context Protocol (MCP) and gained a web-based chatbot UI.

- [ADR-0007](0007-mcp-database-server-implementation.md) — MCP Database Server Implementation
- [ADR-0008](0008-erp-chatbot-ui-complete-system-architecture.md) — ERP Chatbot UI
- [ADR-0009](0009-context-aware-erp-assistant-query-processing-flow.md) — Context-Aware Query Processing Flow
- [ADR-0010](0010-dynamic-erp-assistant-complete-system-architecture.md) — Dynamic ERP Assistant Architecture

### Phase 3 — Pivot: synthetic data → production ERP (October 2025)

**First major pivot.** The thesis moved from synthetic generated data to a real production target: Luisi & Diener's Sage/MSSQL ERP, reachable only via a VPN-connected Windows host. This required a proxy architecture, MCP-only integration, and VPN tunnelling.

- [ADR-0011](0011-erp-proxy-integration-architecture.md) — ERP Proxy Integration Architecture
- [ADR-0011](0011-proxy-for-vpn-tunneling.md) — Windows Proxy for VPN Tunnelling
- [ADR-0012](0012-mcp-only-architecture-migration.md) — **MCP-Only Architecture Migration**
- [ADR-0013](0013-production-database-optimization-vpn-connectivity.md) — Production Database Optimisation for VPN Connectivity

→ This pivot retires the synthetic-data path in **ADR-0001** and **ADR-0002**.

### Phase 4 — Scout Mode and semantic ranking (October 2025)

The thesis's core technical contribution — Scout Mode — enters the code. Scout pre-computes a schema catalog and ranks tables semantically, enabling the agent to operate against opaque production schemas.

- [ADR-0014](0014-scout-mode-semantic-caching.md) — **Scout Mode: Semantic Caching**
- [ADR-0015](0015-semantic-table-ranking.md) — **Semantic Table Ranking**
- [ADR-0016](0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md) — Phase 7+ Complete Architecture
- [ADR-0017](0017-phases-1-5-integration-and-module-organization.md) — Integration and Module Organisation

### Phase 5 — Multi-agent orchestration: explored and retired (October–December 2025)

A period of exploring specialised multi-agent architectures — distinct agents for intent parsing, discovery, SQL generation, and execution, orchestrated by a supervisor. This investigation was later retired in favour of a simpler ReAct agent (Phase 7); the ADRs are preserved as a record of what was tried and why it was set aside.

- [ADR-0018](0018-multi-agent-orchestration-architecture.md) — Multi-Agent Orchestration Architecture *(superseded)*
- [ADR-0019](0019-multi-agent-orchestration-resurrection.md) — Multi-Agent Orchestration Resurrection *(superseded)*
- [ADR-0020](0020-mcp-discovery-tools-semantic-catalog-enrichment.md) — MCP Discovery Tools for Catalog Enrichment
- [ADR-0021](0021-semantic-intent-parsing.md) — Semantic Intent Parsing (Phase 9)
- [ADR-0023](0023-Agent-Orchestration-Architecture.md) — Agent Orchestration Architecture *(superseded)*
- [ADR-0024](0024-Comprehensive-ERP-Assistant-Architecture.md) — Comprehensive ERP Assistant Architecture
- [ADR-0025](0025-langgraph-error-envelope-and-clarify-hardening.md) — LangGraph Error Envelope and Clarify Hardening
- [ADR-0029](0029-react-supervisor-orchestration-mode.md) — ReAct Supervisor Orchestration Mode *(superseded)*

### Phase 6 — Evaluation scaffolding (December 2025)

As the system matured, a first evaluation framework was scaffolded.

- [ADR-0026](0026-evaluation-and-tracking-system.md) — Evaluation and Tracking System
- [ADR-0027](0027-semantic-correctness-contracts-and-benchmark-mode.md) — Semantic Correctness Contracts and Benchmark Mode *(ablation methodology superseded; file format still live)*
- [ADR-0028](0028-Postman-Collection-for-Agent-Endpoints.md) — Postman Collection for Agent Endpoints

### Phase 7 — Pivot: multi-agent → simple ReAct agent (January 2026)

**Second major pivot.** Benchmark runs showed the multi-agent system scoring 0/12 — over-engineered, hard to debug, brittle. The architecture was collapsed into a single ReAct agent using LangGraph's `create_react_agent` with four tools. This is the architecture that ships in the current release (plus `get_column_index` added later, making five tools).

- [ADR-0030](0030-simple-sql-agent-architecture.md) — **Simple SQL Agent Architecture**
- [ADR-0031](0031-simple-sql-agent-complete-architecture.md) — Simple SQL Agent: Complete Architecture
- [ADR-0032](0032-few-shot-sql-patterns.md) — Few-Shot SQL Patterns for Complex Queries
- [ADR-0032](0032-generic-table-search-ranking-fixes.md) — Generic Table Search Ranking Fixes
- [ADR-0033](0033-kpi-library.md) — KPI Library for Domain Calculations
- [ADR-0034](0034-agent-quality-debugging-and-fixes.md) — SQL Agent Quality Debugging and Fixes

→ This pivot retires the multi-agent investigations in **ADR-0018**, **ADR-0019**, **ADR-0023**, and **ADR-0029**.

### Phase 8 — Pivot: Scout ON/OFF → SDG ablation (April 2026)

**Third major pivot.** Running the H2a ablation revealed that Scout ON ≈ Scout OFF once the baseline ranker was aligned: the retrieval layer alone did not move the needle on the transparent Northwind benchmark. The research question refined — it is not the *presence* of Scout that matters but whether semantic *description* enrichment of the catalog changes retrieval. This is the current primary H2a ablation axis.

- [ADR-0035](0035-sdg-semantic-description-generator.md) — **Semantic Description Generator (SDG) for Scout Catalog**
- [ADR-0036](0036-ablation-axis-pivot-sdg.md) — **Ablation Axis Pivot: Scout ON/OFF → SDG Description Enrichment**

→ This pivot retires the ablation framing proposed in **ADR-0027** (the `.contracts.json` file format from that ADR is still used; only the "Scout vs nothing" comparison is set aside).

---

## Summary of pivots

| Pivot | From | To | Retired ADRs | Current ADRs |
|---|---|---|---|---|
| Database target | Synthetic generated data | Real Sage/MSSQL ERP via VPN | 0001, 0002 | 0012, 0013 |
| Agent architecture | Multi-agent orchestration | Single ReAct agent | 0018, 0019, 0023, 0029 | 0030, 0031 |
| Ablation axis | Scout ON vs OFF | SDG description enrichment | 0027 (methodology only) | 0035, 0036 |

## ADR format

New ADRs should follow [`ADR_TEMPLATE.md`](ADR_TEMPLATE.md). The linter at [`../scripts/adr_lint.sh`](../scripts/adr_lint.sh) validates format on new files. Older ADRs (Phases 1–6) use a mix of earlier formats; they fail the current linter but are preserved as written for historical accuracy. Retrofitting them is non-trivial and has no grading upside.

### Required header for new ADRs

Every new ADR must start with:

```md
# ADR-XXXX: Title

**Status**: Accepted
**Date**: YYYY-MM-DD
**Author**: Julianus Kath
```

Optional metadata lines may follow (for example `**Related**`, `**Supersedes**`, `**Context**`, `**Reviewers**`).

### Validation

```bash
scripts/adr_lint.sh
```

The linter checks header structure, required metadata, ISO date format, first-commit date alignment, and obvious secret leaks.
