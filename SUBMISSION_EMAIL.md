# Submission Email Draft — Tri9T AI Engineering Internship

**To:** Tri9T AI Engineering Team <internship@tri9t.ai>  
**Subject:** Submission: AI Engineering Internship Assignment - Tri9T AI  

---

Dear Tri9T AI Engineering Team,

Please find my completed submission for the **AI Engineering Internship Assignment — CT-200 Technical Manual Intelligence System**.

### Deliverable Links
- **GitHub Repository:** `https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPOSITORY_NAME>`
- **Technical Approach Document:** `https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPOSITORY_NAME>/blob/main/APPROACH.md`
- **Decision Log:** `https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPOSITORY_NAME>/blob/main/decision_log.md`

---

### Highlights of Implemented Capabilities

1. **PDF Extraction & Document Hierarchy Reconstruction:**
   - Implemented a layout- and font-aware parser using PyMuPDF (`pdf_parser.py`) for `ct200_manual.pdf` (v1) and `ct200_manual_v2.pdf` (v2).
   - Explicitly resolved all document irregularities with 5 automated unit tests (`test_irregularities.py`):
     - Duplicate headings ("Error Codes" in Section 4.2 vs 7.1) assigned distinct node IDs and parents.
     - Missing parent levels (Section 2.1.1.1 resolving to nearest ancestor 2.1 without dropping content).
     - Out-of-order section appearances (Section 3.4 appearing before 3.3 in document order).
     - Numbered lists in body text (Section 3.3 blood pressure classifications) kept in body content.

2. **Document Versioning & Node Matching:**
   - Concurrently persists versions `v1` and `v2` in SQLite (`tri9t.db`).
   - Categorizes sections as `UNCHANGED`, `MODIFIED`, `ADDED`, or `REMOVED` using normalized text and SHA-256 fingerprints.
   - Idempotent re-ingestion pipeline (`ingest_manuals.py`).

3. **Browse, Search & Version Comparison API:**
   - FastAPI endpoints for top-level section listing, node retrieval with children and hashes (`/nodes/{id}`), heading/content search, version comparison (`/compare`), and node-level diff summaries (`/nodes/{id}/changes`).

4. **Named, Version-Pinned Selections:**
   - Created persistent selection models (`Selection`, `SelectionItem`) and `POST /selections` endpoint.
   - Pinned exact source content and hashes at selection time so re-ingesting future manual versions never corrupts existing selections.
   - Enforced idempotent duplicate submissions and 409 conflict detection.

5. **Gemini QA Generation with Pydantic Validation & Fallback:**
   - Generates 3–5 concrete, executable QA test cases with steps and expected results (`POST /selections/{id}/generate`).
   - Enforces strict Pydantic schema validation.
   - Implemented bounded timeout and a deterministic rule-based fallback generator for API outages or rate limits.

6. **Dynamic Staleness Detection & Retrieval API:**
   - Evaluates test staleness dynamically against live database records (`CURRENT`, `STALE`, `UNKNOWN`), preserving validity for the original pinned revision.
   - Retrieval endpoints by selection ID (`/selections/{id}/tests`), node ID (`/nodes/{id}/tests`), and global audit (`/stale-tests`).
   - Verified that Section 3.2 is flagged `STALE` relative to v2, while Section 1.1 and 4.1 remain `CURRENT`.

7. **Verification & Testing:**
   - 17 automated tests passing: 5 irregularity unit tests in `test_irregularities.py` and 12 end-to-end integration tests in `test_end_to_end.py`.
   - Clean incremental Git commit history without committed secrets or caches.

Please let me know if you have any questions or would like to walk through any architectural decisions during the technical interview.

Best regards,  
**AI Engineering Intern Candidate**
