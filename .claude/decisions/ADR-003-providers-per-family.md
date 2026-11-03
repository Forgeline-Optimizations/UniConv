# ADR-003: Several providers per family, in priority order

**Date:** 2026-11-03
**Sprint:** 0.2 (plan `docs/extension-plan-0.2.md`, steps 2-5, 15, 17, 19)
**Status:** Accepted (refines the "one converter per family" rule of the v1 plan)

## Context
In 0.1 the `Registry` allowed one converter per family and required format keys to be
unique across all families. 0.2 needs `pdf` as a target in Image, Data and Document, and
DOCX in two engines (LibreOffice and Pandoc). The old registry refused to start with that
(review #6). Some engines are also optional at runtime: LibreOffice and Chrome/Edge are
detected, not bundled (ADR-002), so a pair can have a better and a fallback route.

## Decision
- A family holds an **ordered list of providers** (one `Converter` class per engine).
  `find(family, source, target)` returns the first *available* provider that offers the
  pair. Registration order in `core/registry.py::default_providers()` IS the priority.
- **Format definitions are shared**: a key has exactly one `Format` (in
  `converters/formats.py` when more than one provider uses it); a second, different
  definition is a `ValueError` at start-up.
- A **source** key still belongs to exactly one family, so detection knows where a file
  belongs. A target (PDF) may appear in many families.
- **Options per config section**: `Converter.options_key` (default: the family) names the
  section under `defaults`; providers may share a section only with the same Options model
  (`VectorConverter` reuses `image`). `options_for(conv, cfg)` validates per provider.
- **Unavailable providers stay registered**: their formats are still detected, they offer
  no targets, and `hints(family, source)` returns their `install_hint` for the UI/CLI.
  `available()` is evaluated once at start-up.
- Container MIME types that say little (`application/zip`, OLE `msword`/`ms-excel`/
  `ms-powerpoint`) are **weak**: the extension wins (review #13).

## Rationale
- Keeps the v1 promise "a new engine is one file plus one line": an Office route or a
  vector engine is a new provider, not edits inside an existing converter.
- Fallbacks are explicit and testable (`registry_without(...)` fixture), and the loss hint
  always comes from the provider that will actually run.

## Alternatives considered
- **One converter per family with internal dispatch:** every new engine edits a shared
  file; availability, options and hints would be re-implemented per family.
- **A separate "PDF" family:** breaks the UI model (pick family, drop file): a DOCX would
  belong to two families and detection would become ambiguous.

## Consequences
- The order in `default_providers()` is behaviour: Document = LibreOffice, browser, Pandoc;
  Data = pandas, LibreOffice; Image = Pillow/img2pdf, vector. Tests pin this order.
- `registry.converter(family)` no longer exists; use `sources()`, `providers()`, `find()`.
- The family order in the UI follows the first provider registered per family.
