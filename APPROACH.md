# Technical Approach — Tri9T AI Manual Intelligence System

## 1. Objective

The objective is to build a backend system that processes multiple versions of the CT-200 technical manual, stores their content in a structured format, identifies changes between versions, generates QA test ideas, and identifies potentially stale test cases.

## 2. Architecture

The system uses Python for processing, SQLite for persistent storage, SQLAlchemy for database operations, and FastAPI for exposing functionality through REST endpoints.

The workflow is:

1. Extract section headings and content from the PDF manuals.
2. Store manual versions and sections in SQLite.
3. Compare sections between v1 and v2.
4. Record additions and modifications in JSON.
5. Generate structured QA test ideas from recorded changes.
6. Calculate SHA-256 fingerprints for source content.
7. Compare saved fingerprints with recorded source content to identify potentially stale tests.
8. Expose retrieval, search, comparison, and stale-test results through FastAPI.

## 3. Data Storage

Two primary database entities are used:

- **ManualVersion:** Stores the manual version, filename, identifier, and creation timestamp.
- **ManualSection:** Stores the section number, heading, content, manual-version reference, and parent-section relationship.

SQLite provides persistent local storage. JSON files are used for change records and QA test ideas.

## 4. Version Comparison

Sections are compared using their section numbers. A section is classified as:

- **Added:** Present in the newer manual but absent from the older manual.
- **Removed:** Present in the older manual but absent from the newer manual.
- **Modified:** Present in both versions, but the heading or content differs.

The comparison results preserve old and new content where available.

## 5. QA Test Idea Generation

The current implementation generates five structured QA test ideas from the recorded manual changes. Each idea includes the section number, source heading, source version, source-content fingerprint, test idea, and expected result.

The current generator uses predefined Python rules. Integration with an LLM, schema validation of LLM output, and automated retry handling remain future work.

## 6. Stale-Test Detection

The system calculates a SHA-256 fingerprint of the source text and saves it with the associated QA test idea.

The stale-test API compares the saved fingerprint with the fingerprint calculated from the source content available in the change records.

- **CURRENT:** The fingerprints match.
- **STALE:** The fingerprints differ.
- **UNKNOWN:** A reliable comparison cannot be made.

The current implementation is a prototype. For reliable ongoing detection, fingerprints should be checked against the latest stored manual sections, with test records tied to a specific source version and section.

## 7. API Design

FastAPI exposes endpoints for:

- Listing manual versions.
- Listing sections within a version.
- Retrieving a specific section from a selected version.
- Searching section headings and content.
- Comparing manual versions.
- Retrieving QA test ideas and their stale-test status.

Interactive API documentation is available through FastAPI's Swagger UI at `/docs`.

## 8. Validation

The current implementation has been manually checked by:

- Importing 27 sections from v1 and 28 sections from v2.
- Confirming the five recorded manual changes.
- Verifying JSON validity and the presence of five QA test ideas.
- Checking that each test idea contains a source fingerprint.
- Testing the stale-test endpoint with matching fingerprints.
- Deliberately changing one fingerprint and confirming that the related test is marked STALE.
- Restoring the generated QA test data.
- Verifying version-pinned retrieval for section 3.2, where v1 specifies 40 mmHg increments and v2 specifies 30 mmHg increments.

These checks are manual verification steps, not a complete automated test suite.

## 9. Limitations

- PDF extraction may require further work for complex tables, numbering, and parent-child hierarchy.
- QA generation is currently rule-based rather than LLM-powered.
- Stale-test detection currently relies on the content recorded in the change-record JSON file.
- Automated regression tests, persistent test-case management, and production-level error handling require further development.

## 10. Future Work

Future improvements include LLM integration with strict structured-output validation, database-backed QA test records, current-section fingerprint verification, more robust PDF parsing, automated tests, and improved version and change tracking.

## 11. Conclusion

The prototype demonstrates versioned manual storage, section-level retrieval, content search, manual comparison, structured QA test generation, and initial fingerprint-based stale-test detection. The architecture provides a foundation for extending the system into a more reliable document-change and QA management platform.