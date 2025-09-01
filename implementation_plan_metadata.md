# EPIC M — Metadata Enhancement (V1 scope + v2-ready)

> Goal: establish a unified doc-level metadata schema, collect it via a simple manual UI during ingestion, persist it, and propagate it into chunk metadata and the UI. Future-proof for auto-extraction & section-awareness.

---

## Phase 1 — Unified Metadata Schema & IO

- **M-001: Define unified metadata schema** - **(DONE - ✅)**
  - *Desc:* Specify document-level schema: `{doc_id(md5), title*, authors[], year, doc_type, tags[], ingested_at, source_path}` with Pydantic validation & JSON storage under `data/metadata/{doc_id}.json`.
  - *Deps:* V1-010 (PDF parsing), V1-050 (UI shell)
  - *DoD:* `schema.py` + docs; `data/metadata/` folder; sample JSON created & validated.

- **M-002: Metadata IO helpers** - **(DONE - ✅)**
  - *Desc:* Implement `load_metadata(doc_id)`, `save_metadata(doc_id, data)`, `list_metadata()`, `exists(doc_id)`. Enforce schema; auto-set `ingested_at`, `source_path`.
  - *Deps:* M-001
  - *DoD:* Round-trip tests: save→load stable; invalid payloads rejected with clear errors.

- **M-003: Backfill placeholders for existing docs**  - **(DONE - ✅)**
  - *Desc:* Scan Chroma (or chunks JSONL) for unique `doc_id`s; generate placeholder metadata JSON with minimal fields (`doc_id`, `title=""`, `year=None`, …) for any missing files.
  - *Deps:* M-002, V1-020 (Chroma initialized)
  - *DoD:* Script produces placeholder files without overwriting existing; summary printed.

- **M-004: Minimal doc registry & integrity checks**  - **(DONE - ✅)**
  - *Desc:* Add `metadata audit` CLI: detects missing/invalid JSONs, conflicting titles per `doc_id`, orphaned Chroma docs (not in `data/pdfs`), and orphaned metadata (no chunks).
  - *Deps:* M-002
  - *DoD:* `scripts/metadata_audit.py` reports counts/issues; exit codes for CI.

---

## Phase 2 — Manual entry UI (ingestion-time)

- **M-010: Streamlit metadata form (ingestion)**  - **(DONE - ✅)**
  - *Desc:* On new `doc_id` (no JSON), show a form: **title (required)**, authors, year, doc_type (book/paper/article/report/other), tags. Persist via `save_metadata`.
  - *Deps:* M-002, V1-051 (upload/ingestion tab)
  - *DoD:* Ingestion pauses for new docs until title entered; saved JSON reused on re-run.

- **M-011: Prefill & edit existing metadata**
  - *Desc:* If JSON exists, prefill form for quick edits (optional). Provide “Skip” to keep existing.
  - *Deps:* M-010
  - *DoD:* Prefill works; edits persisted; skip keeps file unchanged.

- **M-012: UX validation & guardrails**
  - *Desc:* Inline validation (title required, year numeric {1000..2100}, authors split by `;` or `,`). Non-blocking tips for tags/doc_type.
  - *Deps:* M-010
  - *DoD:* Invalid inputs blocked with messages; valid inputs saved.

---

## Phase 3 — Management utilities (UI/CLI)

- **M-020: Metadata list & export**
  - *Desc:* Add “Metadata” admin section (or extend Inspector) to list docs with key fields; export CSV.
  - *Deps:* M-002, V1-052 (Inspector base)
  - *DoD:* Table view with search; Export button writes `metadata_export.csv`.

- **M-021: Edit metadata (admin)**
  - *Desc:* From the list view, open an editor for a `doc_id`; save changes to JSON.
  - *Deps:* M-020
  - *DoD:* Edits persist and are reflected in subsequent ingest/index runs.

- **M-022: Unit tests for metadata**
  - *Desc:* Tests covering schema validation, IO, backfill, export.
  - *Deps:* M-001..M-021
  - *DoD:* Tests pass; coverage for error paths (invalid year, empty title).

---

## Phase 4 — Pipeline integration

- **M-030: Attach doc-level metadata to chunks**
  - *Desc:* When writing chunks JSONL / upserting to Chroma, include standardized fields: `{doc_id, title, authors, year, doc_type, tags, pages_covered, chunk_idx, source_path}`. Ensure Chroma-safe primitives (JSON-stringify lists).
  - *Deps:* M-002, V1-013s (streaming chunker), V1-020
  - *DoD:* Verified in Chroma Inspector: fields present/consistent for new ingests.

- **M-031: Citations use metadata**
  - *Desc:* Update answer rendering to cite `{title} — p. <pages>` (and `year` if present). Keep excerpts as is.
  - *Deps:* M-030, V1-040/053
  - *DoD:* UI shows citations with titles/pages (and year when set).

- **M-032: Inspector shows metadata fields**
  - *Desc:* Extend “Chroma Inspector” to display `title`, `year`, `doc_type`, `tags`; allow filter by title substring and year.
  - *Deps:* M-030, V1-052
  - *DoD:* Filters work; chunk previews unaffected.

- **M-033: Reindex metadata propagation**
  - *Desc:* Ensure reindex uses latest JSON metadata for each `doc_id`. If missing, block with a gentle prompt (or create placeholder).
  - *Deps:* M-002, V1-054
  - *DoD:* After reindex, chunks in Chroma reflect updated metadata.

---

## Phase 5 — Future (v2/backlog)

- **M-040: Auto-prefill metadata (LLM/OCR)**
  - *Desc:* Optional local/LLM pass to guess title/authors/year from first N pages; prefill the form, never auto-commit.
  - *Deps:* M-010
  - *DoD:* Prefill appears; user can accept/edit/ignore.

- **M-041: Section/heading capture**
  - *Desc:* Extract heading path per chunk (`part > chapter > section`) as `section_id` for better retrieval/reranking & neighbor expansion.
  - *Deps:* V2-021 (header/footer cleanup) or improved parser
  - *DoD:* `section_id` in metadata; Inspector shows it for debug.

- **M-042: Keywords auto-suggest**
  - *Desc:* Generate keywords/tags per document (and optionally per section) using TF-IDF or LLM; store in metadata.
  - *Deps:* M-002
  - *DoD:* Tags saved; UI filter by tag.

- **M-043: Metadata versioning & history**
  - *Desc:* Track `metadata_version`, `updated_at`, and optional `updated_by` to audit changes.
  - *Deps:* M-002
  - *DoD:* JSONs carry version & timestamps; audit CLI shows diffs.
