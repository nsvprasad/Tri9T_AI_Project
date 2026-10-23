# Tri9T AI — Versioned CT-200 Manual Intelligence System

A production-grade backend API and automated pipeline for hierarchical PDF ingestion, version comparison, version-pinned test selections, Gemini LLM test-case generation, and dynamic requirement staleness detection for the **CardioTrack CT-200 Home Blood Pressure Monitor**.

---

## 1. System Overview & Key Capabilities

- **Hierarchical PDF Parsing:** Extracts document titles, multi-level headings, body paragraphs, and specifications from technical manuals using PyMuPDF. Correctly resolves real-world document irregularities (duplicate headings, missing parent levels, out-of-order sections, and numbered lists).
- **Multi-Version Document Storage:** Concurrently stores manual versions `v1` and `v2` in SQLite without destroying historical records.
- **Node Matching & Change Detection:** Tracks logical requirements across versions, classifying sections as `UNCHANGED`, `MODIFIED`, `ADDED`, or `REMOVED` with unified text diffs.
- **Named, Version-Pinned Selections:** Allows QA engineers to snapshot specific requirements against an exact manual version, guaranteeing that future manual updates do not silently alter the selection's baseline text.
- **Gemini-Powered QA Test Generation:** Generates 3–5 concrete, executable QA verification procedures from pinned requirements, complete with strict Pydantic validation and a deterministic, domain-specific rule fallback.
- **Dynamic Staleness Detection:** Real-time retrieval calculation comparing test-case fingerprints against the latest database version (`CURRENT`, `STALE`, `UNKNOWN`), while preserving validity for the original pinned revision.

---

## 2. Technology Stack

- **Operating System:** Windows 10/11
- **Language:** Python 3.11
- **Web Framework:** FastAPI + Uvicorn
- **ORM & Database:** SQLAlchemy + SQLite (`tri9t.db`)
- **Schema Validation:** Pydantic v2
- **PDF Extraction:** PyMuPDF (`fitz`)
- **LLM Provider:** Google GenAI (`gemini-3.8-flash`) with bounded retry and rule-based fallback
- **Dependencies Location:** Local `D:\Tri9T_AI_Project\packages` directory

---

## 3. Project Directory Structure

```text
Tri9T_AI_Project/
├── data/
│   ├── ct200_manual.pdf            # Authoritative CT-200 v1 manual
│   └── ct200_manual_v2.pdf         # Revised CT-200 v2 manual
├── packages/                       # Local Python 3.11 wheel packages
├── database.py                     # SQLAlchemy database configuration
├── models.py                       # SQLAlchemy models: ManualVersion, ManualSection, Selection
├── pdf_parser.py                   # Layout-aware parser handling PDF irregularities
├── ingest_manuals.py               # Repeatable manual ingestion pipeline
├── test_case_store.py              # Atomic JSON store for generated QA test records
├── test_generator.py               # Gemini generation with validation & fallback
├── staleness_service.py            # Live database staleness calculation engine
├── main.py                         # FastAPI application and REST endpoints
├── test_irregularities.py          # Automated unit tests for 4 PDF irregularities
├── test_end_to_end.py              # Full 12-step end-to-end integration test suite
├── check_stale_tests.py            # CLI tool for database-backed staleness reporting
├── decision_log.md                 # Mandatory engineering decision and trade-off log
├── APPROACH.md                     # In-depth technical architecture and design document
└── README.md                       # Setup, usage, and API guide
```

---

## 4. Setup & Environment Configuration

### Prerequisites
- Python 3.11 installed on Windows.
- Project folder located at `D:\Tri9T_AI_Project`.

### Dependencies & PYTHONPATH
Because dependencies are installed locally in the `packages` directory, every script dynamically resolves `PROJECT_DIR / "packages"`. To run external commands or the server, ensure `packages` is accessible:

```powershell
# Set PYTHONPATH in PowerShell (if needed)
$env:PYTHONPATH = "D:\Tri9T_AI_Project\packages"
```

### Secure Gemini API Key Configuration
Configure your Gemini API key as an environment variable in PowerShell or Windows Command Prompt. **Never hardcode or commit your API key.**

```powershell
# In PowerShell:
$env:GEMINI_API_KEY = "your-actual-gemini-api-key"
```

---

## 5. Ingestion & Re-Ingestion Workflow

To ingest both manuals into SQLite while preserving full version isolation and populating hierarchy levels, display orders, and content hashes:

```powershell
python ingest_manuals.py
```

To perform a clean, repeatable re-ingestion:
```powershell
python ingest_manuals.py --force
```

---

## 6. Running the API Server

Start the FastAPI application using Uvicorn:

```powershell
python -c "import sys; sys.path.insert(0, r'D:\Tri9T_AI_Project\packages'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=False)"
```

- **API Base URL:** `http://127.0.0.1:8000`
- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`

---

## 7. Automated Test Suites

### Unit Tests: Structural Irregularities
Validates handling of duplicate headings, missing parent levels, out-of-order sections, and numbered lists in body text:

```powershell
python test_irregularities.py
```
*Expected result:* 5 tests pass (`OK`).

### Integration Tests: Complete End-to-End Workflow
Validates browse endpoints, version comparison, version-pinned selection creation, idempotent duplicate submissions, QA test generation, and retrieval-time staleness detection:

```powershell
python test_end_to_end.py
```
*Expected result:* 12 tests pass (`OK`).

### CLI Staleness Report
Evaluates all stored test cases directly against the live database:

```powershell
python check_stale_tests.py
```

---

## 8. Complete API Endpoint Reference

### A. Browse & Search Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API status and sitemap |
| `GET` | `/manuals` | List all imported manual versions |
| `GET` | `/manuals/top-level-sections?version=v1` | List top-level root sections for a version (defaults to latest) |
| `GET` | `/nodes/{node_id}` | Retrieve node by database ID, including children, text, and hash |
| `GET` | `/nodes/{node_id}/changes` | Determine whether a node changed across versions with diff summary |
| `GET` | `/manuals/{version}/sections` | List all sections for a manual version |
| `GET` | `/manuals/{version}/sections/{section_number}` | Retrieve section by section number (e.g. `3.2`) |
| `GET` | `/manuals/{version}/search?q=battery` | Full-text search across headings and body content |
| `GET` | `/compare` | Comprehensive version comparison between v1 and v2 |

#### Example: Get Node Changes Across Versions
`GET http://127.0.0.1:8000/nodes/10/changes`
```json
{
  "node_id": 10,
  "section_number": "3.2",
  "heading": "Cuff Inflation Sequence",
  "source_version": "v1",
  "target_version": "v2",
  "has_changed": true,
  "change_type": "modified",
  "similarity_ratio": 0.8148,
  "diff_summary": [
    "--- v1/3.2",
    "+++ v2/3.2",
    "-40 mmHg increments",
    "+30 mmHg increments"
  ]
}
```

---

### B. Selection API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/selections` | Create a named, version-pinned selection |
| `GET` | `/selections` | List all saved named selections |
| `GET` | `/selections/{selection_id}` | Retrieve selection details with pinned text and hashes |

#### Example: Create Version-Pinned Selection
`POST http://127.0.0.1:8000/selections`
```json
{
  "name": "Inflation & Overpressure Review",
  "version": "v1",
  "section_numbers": ["1.1", "3.2", "4.1"]
}
```

*Duplicate Submission Policy:*
- If identical section numbers are posted with the same name and version, the API returns the existing selection with `"status": "existing"` (idempotent).
- If different section numbers are posted under an existing selection name, the API returns `409 Conflict`.

---

### C. LLM QA Generation Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/selections/{selection_id}/generate` | Generate 3–5 QA test cases from the selection's pinned requirements |

Optional query parameter: `?force_regenerate=true` (defaults to false to prevent accidental overwrite of existing generations).

---

### D. Retrieval & Staleness Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/selections/{selection_id}/tests` | Fetch generated test cases by selection ID with live staleness |
| `GET` | `/nodes/{node_id}/tests` | Fetch test cases tracing back to a specific node ID |
| `GET` | `/stale-tests` | Global audit view of all test cases against the latest manual |

#### Example: Retrieval with Staleness
`GET http://127.0.0.1:8000/selections/1/tests`
```json
{
  "selection_id": 1,
  "selection_name": "Inflation & Overpressure Review",
  "pinned_version": "v1",
  "total_tests": 3,
  "current_tests": 2,
  "stale_tests": 1,
  "unknown_tests": 0,
  "tests": [
    {
      "test_id": "d5f17d85",
      "section_number": "3.2",
      "source_heading": "Cuff Inflation Sequence",
      "source_version": "v1",
      "source_hash": "d96ca6eb...",
      "test_case": "Verify cuff inflation sequence for Section 3.2...",
      "expected_result": "Device inflates in 40 mmHg increments above 180 mmHg...",
      "status": "STALE",
      "valid_for_pinned_version": true,
      "staleness_reason": "Content fingerprint changed in latest version 'v2' (pinned hash: d96ca6eb..., current hash: 438c5892...)."
    },
    {
      "test_id": "993b8714",
      "section_number": "1.1",
      "source_heading": "Intended Use",
      "source_version": "v1",
      "status": "CURRENT",
      "valid_for_pinned_version": true,
      "staleness_reason": "Content fingerprint is identical to latest version 'v2'."
    }
  ]
}
```

---

## 9. Design Decisions & Limitations

For complete technical justifications, refer to:
- [`APPROACH.md`](APPROACH.md): Full data model, PDF irregularity handling, matching algorithm, LLM prompt design, and future roadmap.
- [`decision_log.md`](decision_log.md): Explicit answers to the three core engineering questions:
  1. What part is most likely to silently give wrong results (Section renumbering / moves across versions) and how to catch it.
  2. Where simplicity was chosen over correctness (Binary SHA-256 hash staleness vs clinical parameter AST extraction).
  3. Unhandled inputs (Multi-column magazine-style PDF page layouts).
