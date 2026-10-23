
# Tri9T AI — Versioned CT-200 Manual Intelligence System

## 1. Project Overview

This project processes two versions of the CT-200 device manual and stores their sections in a structured database. It supports version-specific retrieval, section search, manual comparison, QA test idea generation, and fingerprint-based stale-test detection.

The system helps identify documentation changes that may require corresponding QA test updates.

## 2. Technology Stack

- Python 3.11
- FastAPI — REST API
- SQLAlchemy — database ORM
- SQLite — manual versions and sections
- Pydantic — data validation support
- JSON — change records and generated QA test ideas
- SHA-256 — source-content fingerprints
- Uvicorn — API server

## 3. Project Structure

```text
Tri9T_AI_Project/
├── data/
│   ├── ct200_manual.pdf
│   └── ct200_manual_v2.pdf
├── packages/
├── database.py
├── models.py
├── add_manuals.py
├── import_sections.py
├── build_tree.py
├── compare_manuals.py
├── compare_content.py
├── change_records.py
├── change_records.json
├── validate_changes.py
├── generate_test_ideas.py
├── test_ideas.json
├── check_stale_tests.py
├── main.py
├── tri9t.db
└── README.md
```

## 4. Features

### Manual Versioning
Stores v1 and v2 as separate manual versions.

### Structured Section Retrieval
Retrieves manual sections by version and section number.

### Search
Searches section headings and content within a selected manual version.

### Version Comparison
Identifies added, removed, and modified sections between v1 and v2.

### QA Test Idea Generation
Generates five structured QA test ideas from recorded manual changes. The current implementation uses predefined Python rules rather than an integrated LLM.

### Stale-Test Detection
Calculates SHA-256 fingerprints for source text and compares them with fingerprints stored in QA test records. The API reports tests as CURRENT, STALE, or UNKNOWN.

## 5. Setup

Requirements:
- Python 3.11
- The project files and PDFs
- Dependencies installed in the project's `packages` directory

The project was configured to use a local package directory to accommodate limited space on the system drive.

## 6. Run the API

Open Command Prompt and run:

```bat
cd /d D:\Tri9T_AI_Project
python -c "import sys; sys.path.insert(0, r'D:\Tri9T_AI_Project\packages'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=False)"
```

Keep the terminal open while using the API.

Interactive API documentation:

http://127.0.0.1:8000/docs

## 7. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API status |
| GET | `/manuals` | List manual versions |
| GET | `/manuals/{version}/sections` | List sections for a version |
| GET | `/manuals/{version}/sections/{section_number}` | Retrieve a specific section |
| GET | `/manuals/{version}/search?q=battery` | Search a version |
| GET | `/compare` | Compare v1 and v2 |
| GET | `/stale-tests` | Check saved QA fingerprints |

Example requests:

```text
GET /manuals/v1/sections/3.2
GET /manuals/v2/sections/3.2
GET /manuals/v2/search?q=battery
GET /compare
GET /stale-tests
```

## 8. Example Version Change

Section 3.2, Cuff Inflation Sequence:

- v1 documents inflation in 40 mmHg increments.
- v2 documents inflation in 30 mmHg increments.

The section retrieval endpoint returns the content belonging to the requested version.

## 9. Current Limitations

- QA test idea generation is rule-based; LLM integration remains to be implemented.
- Stale-test detection currently compares fingerprints against content in `change_records.json`, rather than checking every current database section.
- The PDF section extraction is a prototype and may require improvements for complex tables, hierarchy, and formatting.
- Automated tests and broader error handling should be expanded before production use.

## 10. Future Improvements

- Integrate an LLM for QA test generation.
- Validate LLM output against a strict Pydantic schema.
- Track source version and content fingerprints persistently.
- Detect stale tests against the latest database sections.
- Add automated tests for APIs, comparison logic, and stale detection.
- Improve PDF hierarchy extraction and document handling.

## 11. Summary

The project demonstrates versioned technical-document storage, section-level retrieval, manual comparison, structured QA test ideas, and an initial fingerprint-based stale-test detection workflow.
