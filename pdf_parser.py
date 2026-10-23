import re
import unicodedata
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

import pymupdf


def normalize_text(text: str) -> str:
    """Normalize whitespace, newlines, and unicode characters (e.g. ligatures)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Collapse all whitespace sequences (including newlines within paragraphs) into a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def calculate_hash(heading: str, content: str) -> str:
    """Calculate SHA-256 fingerprint for heading and content."""
    payload = f"{normalize_text(heading)}\n{normalize_text(content)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ParsedSection:
    def __init__(
        self,
        section_number: str,
        heading: str,
        level: int,
        display_order: int,
        parent_number: Optional[str] = None
    ):
        self.section_number = section_number
        self.heading = heading
        self.level = level
        self.display_order = display_order
        self.parent_number = parent_number
        self.content_lines: List[str] = []
        self.logical_id = section_number
        self.resolved_parent_number: Optional[str] = None

    @property
    def content(self) -> str:
        text = " ".join(self.content_lines)
        return normalize_text(text)

    @property
    def content_hash(self) -> str:
        return calculate_hash(self.heading, self.content)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "logical_id": self.logical_id,
            "section_number": self.section_number,
            "heading": normalize_text(self.heading),
            "level": self.level,
            "display_order": self.display_order,
            "parent_number": self.resolved_parent_number,
            "content": self.content,
            "content_hash": self.content_hash,
        }


class CT200Parser:
    """
    Specialized, robust parser for CT-200 Technical and User Manuals.
    Handles known PDF structural irregularities:
      1. Duplicate headings (e.g., 'Error Codes' in 4.2 and 7.1)
      2. Missing parent headings (e.g., '2.1.1.1' where '2.1.1' is omitted)
      3. Out-of-order section appearances (e.g., 3.4 appearing before 3.3)
      4. Numbered lists in body text that mimic headings (e.g., classification list in 3.3)
    """

    HEADING_REGEX = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
    CLASSIFICATION_PREFIXES = (
        "Normal:",
        "Elevated:",
        "Hypertension Stage",
        "Hypertensive Crisis:"
    )

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.document_title: str = ""
        self.sections: List[ParsedSection] = []

    def parse(self) -> Dict[str, Any]:
        doc = pymupdf.open(self.pdf_path)

        title_lines = []
        current_section: Optional[ParsedSection] = None
        display_order = 0

        # Scan document
        for page_idx, page in enumerate(doc):
            page_text = page.get_text("text")
            lines = [l.strip() for l in page_text.splitlines() if l.strip()]

            for line in lines:
                # Capture document title on first page before Section 1
                if page_idx == 0 and not current_section:
                    if not self.HEADING_REGEX.match(line):
                        title_lines.append(line)
                        continue
                    else:
                        self.document_title = normalize_text(" ".join(title_lines))

                match = self.HEADING_REGEX.match(line)
                if match:
                    number = match.group(1).rstrip(".")
                    title = match.group(2).strip()

                    # Irregularity 4: Check if this is a numbered list item inside 3.3
                    if any(title.startswith(prefix) for prefix in self.CLASSIFICATION_PREFIXES):
                        if current_section is not None:
                            current_section.content_lines.append(line)
                        continue

                    # If this is a valid section heading
                    level = len(number.split("."))
                    section = ParsedSection(
                        section_number=number,
                        heading=title,
                        level=level,
                        display_order=display_order
                    )
                    display_order += 1
                    self.sections.append(section)
                    current_section = section
                else:
                    # Regular body text, list item, or table row
                    if current_section is not None:
                        current_section.content_lines.append(line)

        doc.close()

        if not self.document_title and title_lines:
            self.document_title = normalize_text(" ".join(title_lines))

        # Reconstruct parent-child hierarchy handling missing parents (Irregularity 2)
        section_lookup = {s.section_number: s for s in self.sections}

        for section in self.sections:
            parts = section.section_number.split(".")
            if len(parts) <= 1:
                section.resolved_parent_number = None
            else:
                # Search up the ancestor tree for nearest existing parent
                found_parent = None
                for i in range(len(parts) - 1, 0, -1):
                    candidate = ".".join(parts[:i])
                    if candidate in section_lookup:
                        found_parent = candidate
                        break
                section.resolved_parent_number = found_parent

        return {
            "document_title": self.document_title,
            "total_sections": len(self.sections),
            "sections": [s.to_dict() for s in self.sections]
        }


def parse_ct200_pdf(pdf_path: str) -> Dict[str, Any]:
    parser = CT200Parser(pdf_path)
    return parser.parse()
