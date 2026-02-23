# ADR Guidelines

This directory is the single source of truth for Architecture Decision Records.

## Required Header

Every ADR must start with:

```md
# ADR-XXXX: Title

**Status**: Accepted
**Date**: YYYY-MM-DD
**Author**: Julianus Kath
```

Optional metadata lines may follow (for example `**Related**`, `**Supersedes**`, `**Context**`, `**Reviewers**`).

## Validation

Run:

```bash
scripts/adr_lint.sh
```

The linter checks header structure, required metadata, ISO date format, first-commit date alignment, and obvious secret leaks.
