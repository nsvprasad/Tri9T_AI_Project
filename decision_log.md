# Decision Log — Tri9T AI Engineering Internship

This decision log addresses the three mandatory engineering questions posed in the assignment specification, detailing the concrete trade-offs, failure modes, and boundaries of the CT-200 manual intelligence system.

---

### Question 1: What is the one part of this system most likely to silently give wrong results without erroring? How would you catch it?

**Decision & Risk Analysis:**
The part most likely to silently produce incorrect results is **section renumbering or structural reorganization across document versions**. 

Our version matching strategy pairs sections across v1 and v2 using their logical section number / hierarchical path (e.g., matching Section `3.2` in v1 to Section `3.2` in v2). If a medical device manufacturer reorganizes the manual such that a requirement is moved or renumbered—for example, if Section `3.2 Cuff Inflation Sequence` were split into two sections or renumbered to `3.3`, and the old `3.3 Result Display` became `3.4`—the path-based matcher would pair old Section `3.2` with new Section `3.2`. 
The system would not raise any exception. Instead, it would compute SHA-256 hashes, observe that the hashes differ, and silently classify the section as `MODIFIED` rather than recognizing it as a section deletion/move. Furthermore, any QA test case pinned to v1 Section `3.2` would compare its hash against the text of the *new* Section `3.2` (which is now completely unrelated content), marking the test as `STALE` for the wrong reason and providing a nonsensical diff summary.

**How to Catch It:**
To detect silent mismatches:
1. **Semantic Similarity Threshold Guardrail:** Before accepting a `MODIFIED` classification, compute the cosine similarity of text embeddings (or token-level Jaccard similarity) between the old section content and new section content. If the similarity falls below a defensible threshold (e.g. < 40%), flag the match with a warning: `AMBIGUOUS_RENUMBERING_SUSPECTED`.
2. **Cross-Document Best-Match Scanning:** When a hash mismatch occurs on identical section numbers, scan all sections in the new version for high semantic similarity (> 85%). If the old section's text is found under a different section number in the new version, flag it as `MOVED / RENAMED` (`section_3.2 -> section_3.3`) instead of `MODIFIED`.
3. **Automated Structural Sanity Invariants:** Run regression checks verifying that heading titles between matched sections share significant token overlap; if Section `3.2 Cuff Inflation Sequence` matches a section titled `Result Display`, reject the automated match and classify as `UNMATCHED / REQUIRES_HUMAN_REVIEW`.

---

### Question 2: Where did you choose simplicity over correctness because of time, and what would break first if this went to production as-is?

**Decision & Risk Analysis:**
We chose simplicity over correctness in **treating all content modifications as binary hash mismatches, without distinguishing cosmetic/formatting changes from safety-critical clinical parameter changes**.

In our implementation, content staleness is determined by `old.content_hash != new.content_hash`. This SHA-256 fingerprint operates on normalized text. While this provides 100% sensitivity (no textual change is ever missed), it has zero semantic discrimination:
- A change from `40 mmHg increments` to `30 mmHg increments` (a safety-critical clinical parameter revision) produces a hash mismatch and is flagged `STALE`.
- A change fixing a typographical spelling error (e.g., `proﬁle` to `profile`) or adding a comma also produces a hash mismatch and is flagged `STALE`.

In a regulated medical device setting (FDA 21 CFR Part 820 / ISO 13485), marking every minor formatting tweak as `STALE` imposes immense QA overhead, forcing test engineers to re-verify hundreds of tests that were not actually invalidated by a cosmetic edit.

**What Would Break First in Production:**
What would break first is **QA alert fatigue and verification backlog collapse**. 
In a production release cycle with a 200-page medical device manual, a technical writer standardizing terminology or correcting punctuation would cause dozens of previously validated test cases across unaffected subsystems to suddenly light up as `STALE`. Test leads would lose trust in the staleness indicator because "everything is always flagged stale," leading engineers to rubber-stamp test case re-approvals without carefully reviewing genuine safety modifications (such as emergency deflation valve timing changing from 2.0s to 1.5s).

**Production Remedy:**
Implement a two-tier staleness classifier:
- Level 1: Strict SHA-256 fingerprint for change detection.
- Level 2: An AST / entity-aware numerical parameter extractor that compares numerical limits, units of measure (mmHg, bpm, seconds, cm), and modal verbs (`shall`, `must`, `not`). Changes affecting clinical parameters are flagged `CRITICAL_STALE`, while pure prose refactorings are flagged `INFORMATIONAL_EDIT`.

---

### Question 3: Name one input (to your parser, your versioning matcher, or your LLM call) that you did not handle, and what your system does when it sees it.

**Decision & Input Analysis:**
**Input Not Handled: Multi-column PDF page layouts with embedded floating tables and non-standard bullet symbols.**

Our PDF parser (`CT200Parser`) uses sequential line-by-line text block extraction from PyMuPDF, assuming a standard single-column reading flow (which matches the CT-200 technical manual). 

**What the System Does When It Sees It:**
If presented with a multi-column document (e.g., a two-column journal-style specification) or a page where text wraps across columns with floating sidebars:
1. PyMuPDF's basic line extraction reads horizontally across physical coordinates or in block sequence. If the blocks are not cleanly ordered by reading order, text from the left column on line 1 is interleaved with text from the right column on line 1.
2. If a section heading appears in Column 1 and body text continues in Column 2, a heading appearing in Column 2 can prematurely terminate Section 1's content.
3. The parser does not crash or throw an exception. Instead, it extracts garbled sentences combining fragments of both columns into `content`.
4. The resulting `content_hash` is computed on the garbled text. When compared across versions or sent to the LLM:
   - The versioning matcher flags it as modified or unchanged based purely on the corrupted text string.
   - The LLM receives scrambled sentences, resulting in QA test ideas derived from nonsensical requirement fragments.
   - The user receives no error indicating that the layout extraction order was compromised.

**System Defense & Boundary:**
We honestly document this boundary: the parser is explicitly built and validated for single-column technical manuals and the CT-200 document structure. If a document with complex multi-column reading orders or scanned raster pages is supplied, our system exposes this limitation and recommends pre-processing via specialized layout-analysis libraries (such as LayoutParser, pdfplumber, or PyMuPDF's block sorting heuristics).
