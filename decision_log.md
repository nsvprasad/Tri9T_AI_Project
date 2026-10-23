# Decision Log — Tri9T AI Engineering Internship

This log records the main risks and trade-offs in the CT-200 manual intelligence prototype.

## 1. What is most likely to silently give wrong results, and how would I catch it?

**Risk:** cross-version matching can silently pair the wrong sections when a requirement is renumbered, moved, split, or when the same heading appears in different places. Because the matcher relies primarily on logical section identifiers and hashes, it can report a section as modified even when the original requirement was moved elsewhere.

**Detection:** add a match-confidence/ambiguity check using section path, heading similarity, and body similarity. Flag low-confidence matches for review and test the matcher with fixtures that include renumbered, moved, split, and duplicate-heading sections. A hash comparison alone detects changed text; it does not prove that the two sections represent the same requirement.

## 2. Where did I choose simplicity over correctness, and what would break first in production?

**Trade-off:** I used normalized content hashes as a straightforward staleness signal instead of building a semantic or clinical-impact analysis of each change. This is easy to explain and deterministic, but it treats a punctuation change and a changed pressure threshold as different hashes without judging the severity of the change.

**Production risk:** reviewers could receive too many stale warnings, or a wrong cross-version match could cause a misleading status. Before production use, I would add safety-parameter extraction, ambiguity handling, audit logging, and human review of changes that affect device limits.

## 3. Name an input I did not handle and explain what the system does with it.

**Input:** a heavily multi-column or magazine-style PDF page whose text extraction order does not follow the intended reading order.

**Current behavior/limitation:** the parser is tailored to the supplied CT-200 manual layout. If a page's extracted text order is ambiguous, the parser may place content under the wrong heading or in the wrong order without being able to infer the intended layout reliably. I would detect suspicious layout patterns, flag the page/section for review, and add parser fixtures for that layout rather than claiming support for arbitrary PDFs.

## Additional trade-offs

- **Storage:** SQLite is used for relational manual/version/selection data, while generated QA records are stored in JSON. This keeps local setup small, but JSON storage is not appropriate for concurrent multi-process writes at scale.
- **LLM dependency:** the generation path can use Gemini when configured and has a rule-based fallback. The fallback improves availability but cannot replace verification by a QA engineer against the pinned source.
- **Scope:** the implementation prioritizes versioning, traceability, and staleness behavior over a frontend, authentication, or automatic regeneration of stale tests, which are outside the assignment's stated scope.
