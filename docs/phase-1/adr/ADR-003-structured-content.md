# ADR-003: Preserve structured content with plain-text fallbacks

## Decision

Question stems and options use typed blocks while retaining `plain_text` for search, audit and accessibility fallback. Shared passages/tables and assets are separate referenced entities.

## Consequences

Match lists, tables, formulas, images and labelled statements survive import/export without being flattened into ambiguous strings.
