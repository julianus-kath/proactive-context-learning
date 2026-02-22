#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

if [[ ! -d adrs ]]; then
  echo "ERROR: adrs/ directory not found"
  exit 1
fi

shopt -s nullglob
files=(adrs/[0-9][0-9][0-9][0-9]-*.md)
if (( ${#files[@]} == 0 )); then
  echo "ERROR: no ADR markdown files found in adrs/"
  exit 1
fi

errors=0
warnings=0
id_tmp="$(mktemp)"
trap 'rm -f "$id_tmp"' EXIT

for f in "${files[@]}"; do
  base="$(basename "$f")"
  id_from_file=""
  if [[ "$base" =~ ^([0-9]{4}) ]]; then
    id_from_file="${BASH_REMATCH[1]}"
    printf '%s\n' "$id_from_file" >> "$id_tmp"
  fi

  first_line="$(awk 'NF{print; exit}' "$f")"
  if [[ ! "$first_line" =~ ^#\ ADR-[0-9]{4}:\ .+ ]]; then
    echo "ERROR [$f]: first non-empty line must be '# ADR-XXXX: Title'"
    ((errors++))
  fi

  status_line="$(awk 'NR<=20 && /^\*\*Status\*\*:/ {print; exit}' "$f")"
  date_line="$(awk 'NR<=20 && /^\*\*Date\*\*:/ {print; exit}' "$f")"
  author_line="$(awk 'NR<=20 && /^\*\*Author\*\*:/ {print; exit}' "$f")"

  if [[ -z "$status_line" ]]; then
    echo "ERROR [$f]: missing '**Status**:' in top metadata block"
    ((errors++))
  fi

  if [[ -z "$date_line" ]]; then
    echo "ERROR [$f]: missing '**Date**:' in top metadata block"
    ((errors++))
  fi

  if [[ -z "$author_line" ]]; then
    echo "ERROR [$f]: missing '**Author**:' in top metadata block"
    ((errors++))
  fi

  date_val="${date_line#**Date**: }"
  if [[ -n "$date_line" && ! "$date_val" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR [$f]: date must be ISO format YYYY-MM-DD (found '$date_val')"
    ((errors++))
  fi

  first_commit="$(git log --follow --format='%ad' --date=short -- "$f" | tail -1)"
  if [[ -n "$date_line" && -n "$first_commit" && "$date_val" != "$first_commit" ]]; then
    echo "ERROR [$f]: Date '$date_val' does not match first commit date '$first_commit'"
    ((errors++))
  fi

  if rg -n "SQLSERVER_PASSWORD\s*=\s*'[^<]|password\s*=\s*\"[^<]|API_KEY\s*=\s*supersecret|PWD=.*[^>]" "$f" >/dev/null 2>&1; then
    echo "WARN [$f]: potential secret-like value detected, review manually"
    ((warnings++))
  fi
done

while read -r count id; do
  if (( count > 1 )); then
    echo "WARN: duplicate ADR id prefix '$id' appears ${count} times"
    ((warnings++))
  fi
done < <(sort "$id_tmp" | uniq -c)

if (( warnings > 0 )); then
  echo
  echo "Lint warnings: $warnings"
fi

if (( errors > 0 )); then
  echo
  echo "ADR lint failed with $errors error(s)."
  exit 1
fi

echo "ADR lint passed for ${#files[@]} file(s)."
