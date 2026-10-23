# Technical Approach — Tri9T AI CT-200 Manual Intelligence System

## 1. Objective

The system demonstrates how a technical manual can be ingested as a structured hierarchy, compared across revisions, selected as an immutable source snapshot, used to generate QA test ideas, and checked for staleness after a newer revision is available.

The prototype is designed around the supplied CT-200 manuals. It is not a general-purpose PDF parser or a validated medical-device quality system.

## 2. End-to-end architecture

1. `ingest_manuals.py` loads the supplied manual versions.
2. `pdf_parser.py` extracts text and structural clues, then constructs section nodes.
3. `database.py` and `models.py` persist manual versions, sections, hierarchy relationships, and selections in SQLite through SQLAlchemy.
4. Section content is normalized and fingerprinted with SHA-256 hashes.
5. The comparison API uses the implementation's logical section matching and content hashes to classify changes.
6. The selection API stores the exact selected section text, version, and hash.
7. `test_generator.py` attempts structured Gemini output when configured; it validates the result and uses rule-based fallback when the LLM is unavailable or returns unsuitable output.
8. `test_case_store.py` persists generated cases in `test_cases.json`.
9. `staleness_service.py` compares a saved case's source fingerprint with the latest matching section at retrieval time.
10. `main.py` exposes these capabilities through FastAPI.

## 3. Data model and storage

### Relational storage

SQLite stores the structured and relational data:

- **Manual versions:** version label, source filename, document metadata, and creation information.
- **Manual sections:** section number/logical identifier, heading, hierarchy level, body content, content hash, display order, manual-version link, and parent relationship.
- **Selections:** a name and pinned manual version.
- **Selection items:** selected section identity, version, heading, content snapshot, and pinned hash.

The selection item snapshot means that later ingestion does not silently replace the source text from which an earlier generation was produced.

### Generated output storage

Generated QA cases are stored in `test_cases.json`, a JSON-backed document store. Each record carries selection and source metadata, including the source node/section, source version, and pinned hash. This is a lightweight assignment-scale alternative to running a separate MongoDB service; it is not intended for concurrent, multi-instance production workloads.

## 4. PDF parsing and hierarchy construction

The parser is tailored to the supplied CT-200 PDFs. It uses extracted text and document layout/font clues rather than applying OCR indiscriminately to text-based PDFs.

The tree needs to preserve both the logical hierarchy and the physical reading order. The section number and heading alone are not sufficient as a globally unique identity: repeated headings can appear in different parts of the manual.

### Structural irregularities

| Irregularity | Handling strategy | Limitation |
|---|---|---|
| Duplicate headings | Keep separate section records using section/path context and distinct database IDs; do not key nodes only by heading text. | A major renumbering or relocation can still confuse version matching. |
| Missing parent level | Search successively shorter section-number prefixes for the nearest existing ancestor. | Nonstandard numbering that does not follow the expected prefix pattern may need a manual rule. |
| Out-of-order sections | Keep a display-order value for physical appearance separately from the parent/child hierarchy. | Any reading-order extraction error can affect display order even if parent assignment is correct. |
| Numbered lists inside body text | Use heading/layout clues and context to avoid treating every numbered line as a document section. | Unusual formatting that resembles a heading may still be ambiguous. |

`test_irregularities.py` contains explicit tests for parser irregularities. The latest successful run passed all 5 tests.

## 5. Versioning and change detection

The ingestion pipeline retains the supplied v1 and v2 versions rather than treating the latest upload as a replacement for all historical content.

The current matching approach uses the section's logical identifier/number to locate the corresponding section in another version. Normalized heading/body content is fingerprinted with SHA-256. The hash is useful for detecting exact normalized content changes.

Typical classifications:

- **UNCHANGED:** a corresponding logical section exists and its fingerprint matches.
- **MODIFIED:** a corresponding logical section exists but the fingerprint differs.
- **ADDED:** a section exists in the newer version without a match in the older version.
- **REMOVED:** a section exists in the older version without a match in the newer version.

### Known failure modes

1. **Renumbering or moving sections:** matching by logical identifier may compare unrelated sections if a requirement moves or is renumbered.
2. **Meaning versus wording:** a hash difference does not distinguish a punctuation change from a clinically significant threshold change.
3. **Normalization trade-off:** whitespace normalization reduces noise, but overly aggressive normalization could hide a meaningful formatting difference.
4. **Ambiguous repeated structures:** duplicate headings are handled as separate nodes during parsing, but cross-version matching remains dependent on stable logical identifiers.

A production extension should add ambiguity flags, semantic similarity review, and extraction of safety-relevant parameters (for example, numeric thresholds and units) before deciding the impact of a change.

## 6. Version-pinned selections

A client creates a named selection by specifying a version and the desired sections. The API validates the requested sections and saves a snapshot of each selected item, including its text and hash.

The duplicate policy is idempotent for the same selection name, version, and section set: an identical request can return the existing selection. Reusing a name with a different section set is rejected rather than silently mutating the original selection.

This keeps generation traceable to the exact source revision chosen by the user.

## 7. QA test generation

### LLM prompt and response handling

The prompt provides the pinned section number, heading, version, and requirement text. It asks for distinct QA scenarios and a structured JSON array with scenario type, scenario description, test procedure, and expected result.

When Gemini is configured, the client requests JSON output and attempts bounded retries across configured model choices. The response is parsed and basic fields are checked before cases are accepted. Pydantic schemas are used by the test-case storage/validation path.

### Fallback

If the API key is absent, the LLM call fails, or fewer than the minimum required usable cases are generated, the system uses a deterministic rule-based fallback tailored to supported section types. This keeps the demo runnable without depending on a live model call.

Fallback rules are not a substitute for expert review. Any domain-specific thresholds, error codes, timings, or contraindications in generated content must be checked against the pinned manual text. This is a key limitation of a rule-based prototype.

### Duplicate handling

Test procedures are normalized for duplicate detection. Generation is cached for an existing selection by default; an explicit force-regeneration option allows replacement. The stored test record includes the selection and source metadata so it remains traceable after re-ingestion.

## 8. Staleness and retrieval

Staleness is computed at retrieval time, rather than being a static field set only when a new manual is ingested.

- **CURRENT:** the latest matching section has the same source fingerprint.
- **STALE:** the latest matching section exists, but its fingerprint differs.
- **UNKNOWN:** the latest version does not provide a reliable matching section for the stored source.

The retrieval response also explains the reason for the status. The original pinned version remains available as the generation baseline even when a case is marked stale relative to the latest manual.

The check is intentionally conservative: any fingerprint difference can produce `STALE`. It does not assess clinical significance, and a section renumbering can lead to an incorrect match. It should be interpreted as a traceability warning, not an automated medical judgment.

## 9. API surface

The FastAPI application provides routes for:

- listing versions and top-level sections;
- retrieving a node and its children/text/hash;
- searching section headings and body text;
- comparing versions and viewing change summaries;
- creating and retrieving named selections;
- generating QA test cases from a selection;
- retrieving cases by selection or node with live staleness status;
- listing stale/unknown cases for audit.

Interactive endpoint documentation is available at `/docs` while the local API server is running.

## 10. Verification

The latest recorded successful run produced:

- `python test_irregularities.py` — 5 tests passed.
- `python test_end_to_end.py` — 12 tests passed.

The end-to-end tests exercise ingestion, API operations, version comparison, selection behavior, generation, and staleness retrieval. A Starlette/httpx deprecation warning was printed by the current local dependency environment but did not fail the test run.

## 11. What I would improve with more time

1. Add semantic/structural matching for moved and renumbered sections, with an explicit ambiguous-match state.
2. Extract safety-critical numeric parameters and units so the system can distinguish cosmetic edits from changed thresholds.
3. Add table-aware PDF extraction and stronger parser fixtures for unusual layouts.
4. Add a proper dependency lockfile and run tests in a clean CI environment.
5. Replace JSON file storage with a transactional document store if concurrent writers or multiple API instances are required.
6. Add stronger validation that every generated scenario and expected result is supported by its exact pinned source content.
7. Add a traceability-matrix export linking requirement, source version/hash, generated case, and current staleness status.
