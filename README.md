# Tri9T AI — Versioned CT-200 Manual Intelligence System

A Python backend that ingests two versions of the CardioTrack CT-200 manual, builds a hierarchical section tree, compares document versions, saves version-pinned selections, generates QA test-case ideas, and reports whether saved test cases are current or stale.

Repository: https://github.com/nsvprasad/Tri9T_AI_Project

## 1. What the system does

- **PDF ingestion:** extracts headings and body text from the supplied CT-200 PDFs.
- **Hierarchical structure:** stores section numbers, headings, nesting levels, parent/child relationships, display order, and content hashes.
- **Version comparison:** stores v1 and v2 separately and identifies sections as unchanged, modified, added, or removed using the implemented logical section matching and hashes.
- **Version-pinned selections:** saves the exact section content and hash used when a named selection is created.
- **QA test generation:** attempts structured Gemini output when configured; otherwise, or if generation fails validation, uses the rule-based fallback.
- **Retrieval-time staleness:** checks stored test cases against the latest manual and reports `CURRENT`, `STALE`, or `UNKNOWN`.
- **API:** exposes browsing, searching, comparison, selection, generation, and test retrieval endpoints through FastAPI.

## 2. Workflow

```text
CT-200 manual PDFs (v1 and v2)
            |
            v
       PDF parser
            |
            v
Hierarchical sections + SHA-256 hashes
            |
            v
    SQLite / SQLAlchemy
            |
      +-----+----------------+
      |                      |
      v                      v
Version comparison     Named selection
                             |
                             v
                 Pinned section text + hashes
                             |
                             v
                   QA test-case generation
                    Gemini or rule fallback
                             |
                             v
                   test_cases.json (JSON)
                             |
                             v
                  Retrieval-time staleness
                             |
                             v
                 FastAPI responses / Swagger UI
```

## 3. Project structure

```text
Tri9T_AI_Project/
├── data/
│   ├── ct200_manual.pdf
│   └── ct200_manual_v2.pdf
├── main.py                  # FastAPI routes
├── database.py              # SQLAlchemy engine/session setup
├── models.py                # ORM models for versions, sections, selections
├── pdf_parser.py            # CT-200 PDF parsing and hierarchy construction
├── ingest_manuals.py        # Ingests the supplied manual versions
├── staleness_service.py     # Current/stale/unknown evaluation
├── test_generator.py        # Gemini generation and fallback
├── test_case_store.py       # JSON-backed test-case storage
├── test_irregularities.py   # Parser irregularity unit tests
├── test_end_to_end.py       # API and workflow integration tests
├── check_stale_tests.py     # CLI staleness report
├── tri9t.db                 # Local SQLite database (created/updated by the app)
├── test_cases.json          # Generated QA test cases
├── test_ideas.json          # Supporting generated test ideas
├── APPROACH.md              # Technical approach
├── decision_log.md          # Engineering trade-offs
└── SUBMISSION_EMAIL.md      # Submission email draft
```

The database and JSON files contain local application state. If starting from a clean clone, follow the setup and ingestion steps below before using the API.

## 4. Requirements

- Windows 10/11
- Python 3.11 recommended
- The `data/` directory containing both supplied CT-200 PDF files
- Optional: Gemini API key for LLM-backed generation. The rule-based fallback is available when the key is not configured or the LLM call fails.

## 5. Setup on Windows

Open **Command Prompt** and run:

```bat
cd /d D:\Tri9T_AI_Project
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the repository does not yet contain `requirements.txt`, install the runtime packages explicitly:

```bat
pip install fastapi uvicorn sqlalchemy "pydantic>=2" pymupdf google-genai httpx
```

Check Python:

```bat
python --version
```

### Optional Gemini configuration

For the current Command Prompt window only:

```bat
set GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Replace the placeholder with your key. Never put a real key in source code or commit it to Git. If you do not set this variable, generation can use the rule-based fallback.

The model can be overridden with `GEMINI_MODEL` if the configured model is available to your account:

```bat
set GEMINI_MODEL=your-supported-model-name
```

Close the terminal or run `set GEMINI_MODEL=` to clear the override for the current session.

## 6. Ingest the manuals

From the project root with the virtual environment activated:

```bat
python ingest_manuals.py
```

The pipeline reads the supplied v1 and v2 manuals and persists their sections and version information in SQLite. The expected test run previously reported 27 structured sections for v1 and 28 for v2.

To request a forced refresh using the script's supported option:

```bat
python ingest_manuals.py --force
```

Use `--force` only when you intend to refresh the ingested section data for the relevant version. Do not delete the database unless you intentionally want to reset local state.

## 7. Start the API

In the project root:

```bat
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

If the command cannot find `uvicorn`, verify that the virtual environment is activated and that dependency installation completed.

Open:

- API status: http://127.0.0.1:8000/
- Interactive API documentation: http://127.0.0.1:8000/docs

Keep this terminal open while using the API. Press `Ctrl+C` to stop the server.

## 8. Suggested end-to-end walkthrough

Use Swagger UI at `http://127.0.0.1:8000/docs` so you can see each request and response.

1. **Inspect imported versions:** call `GET /manuals`.
2. **Browse sections:** call `GET /manuals/top-level-sections?version=v1` and repeat with `version=v2`.
3. **Search the manual:** call `GET /manuals/v1/search?q=battery` (try a different query if needed).
4. **Compare versions:** call `GET /compare`; inspect the change classification and diff summary for changed sections.
5. **Create a pinned selection:** use `POST /selections` with a body such as:

   ```json
   {
     "name": "Inflation and Safety Review",
     "version": "v1",
     "section_numbers": ["1.1", "3.2", "4.1"]
   }
   ```

   Use section numbers that exist in the chosen manual version. The API response provides the selection ID.
6. **Inspect the selection:** call `GET /selections/{selection_id}`.
7. **Generate QA cases:** call `POST /selections/{selection_id}/generate`. Existing cases may be returned unless regeneration is explicitly requested.
8. **Retrieve cases and staleness:** call `GET /selections/{selection_id}/tests`. Check the status and staleness reason in each returned test record.
9. **Inspect a node:** call `GET /nodes/{node_id}` and `GET /nodes/{node_id}/changes` using an actual node ID returned by the API.

## 9. Trigger and verify the v1 → v2 flow

The two supplied versions are ingested by the ingestion pipeline:

```bat
python ingest_manuals.py
```

Then use the API to compare them:

```text
GET http://127.0.0.1:8000/compare
```

For a specific node, use the actual node ID from the API response:

```text
GET http://127.0.0.1:8000/nodes/{node_id}/changes
```

Finally, retrieve test cases generated from a v1 selection:

```text
GET http://127.0.0.1:8000/selections/{selection_id}/tests
```

The staleness check is performed at retrieval time against the latest stored manual version. A test can remain valid for its original pinned version while being marked stale relative to the latest version. This is a hash-based signal, not a clinical assessment of the significance of each wording change.

## 10. Run the tests

Run these from the project root:

```bat
python test_irregularities.py
python test_end_to_end.py
```

The latest recorded successful run produced:

- `test_irregularities.py`: 5 tests passed.
- `test_end_to_end.py`: 12 tests passed.

The end-to-end test prints a Starlette/httpx deprecation warning in the current environment. That warning did not prevent the tests from passing.

For a staleness report from the command line:

```bat
python check_stale_tests.py
```

## 11. API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | API status |
| `GET` | `/manuals` | List ingested versions |
| `GET` | `/manuals/top-level-sections?version=v1` | List top-level sections |
| `GET` | `/nodes/{node_id}` | Retrieve a node and its details |
| `GET` | `/nodes/{node_id}/changes` | Compare a node across versions |
| `GET` | `/manuals/{version}/sections` | List sections for a version |
| `GET` | `/manuals/{version}/sections/{section_number}` | Get a section by section number |
| `GET` | `/manuals/{version}/search?q=battery` | Search section headings and content |
| `GET` | `/compare` | Compare manual versions |
| `POST` | `/selections` | Create a named, version-pinned selection |
| `GET` | `/selections` | List selections |
| `GET` | `/selections/{selection_id}` | Retrieve a selection and pinned items |
| `POST` | `/selections/{selection_id}/generate` | Generate QA test cases |
| `GET` | `/selections/{selection_id}/tests` | Retrieve test cases and staleness |
| `GET` | `/nodes/{node_id}/tests` | Retrieve tests linked to a node |
| `GET` | `/stale-tests` | Audit test cases against the latest version |

## 12. Design limitations

- Matching primarily relies on logical section identifiers and content hashes; renumbered or moved sections can be misclassified.
- Hash-based staleness treats all content changes as changes; it does not determine whether a change is clinically significant.
- The parser is designed for the supplied CT-200 manual layout, not arbitrary PDFs.
- LLM output is not treated as authoritative. It is validated, and the rule-based fallback is used when generation is unavailable or unsuitable.
- This is an internship assignment prototype, not a validated medical-device software product.

## 13. Related documentation

- [`APPROACH.md`](APPROACH.md): architecture, parsing, version matching, generation, and limitations.
- [`decision_log.md`](decision_log.md): direct answers to the three required engineering questions.
- [`SUBMISSION_EMAIL.md`](SUBMISSION_EMAIL.md): submission email draft.
