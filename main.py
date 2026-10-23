
import json
import hashlib
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import ManualVersion, ManualSection


# Project folder and JSON files
BASE_DIR = Path(__file__).resolve().parent
TEST_IDEAS_FILE = BASE_DIR / "test_ideas.json"
CHANGE_RECORDS_FILE = BASE_DIR / "change_records.json"

app = FastAPI(
    title="Tri9T CT-200 Manual API",
    description="Manual versioning, section search, comparison, and stale QA test detection",
    version="1.0.0"
)


def calculate_hash(text):
    """Calculate a SHA-256 fingerprint for text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json_file(file_path):
    """Read a JSON file safely."""
    if not file_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Required file not found: {file_path.name}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON file: {file_path.name}"
        )


@app.get("/")
def home():
    return {
        "message": "Tri9T CT-200 Manual API is running",
        "documentation": "/docs",
        "endpoints": [
            "/manuals",
            "/manuals/{version}/sections",
            "/manuals/{version}/sections/{section_number}",
            "/manuals/{version}/search?q=battery",
            "/compare",
            "/stale-tests"
        ]
    }


@app.get("/manuals")
def get_manuals(db: Session = Depends(get_db)):
    """List all imported manual versions."""
    manuals = (
        db.query(ManualVersion)
        .order_by(ManualVersion.id)
        .all()
    )

    return [
        {
            "id": manual.id,
            "version": manual.version,
            "filename": manual.filename,
            "created_at": (
                manual.created_at.isoformat()
                if manual.created_at else None
            )
        }
        for manual in manuals
    ]


@app.get("/manuals/{version}/sections")
def get_sections(version: str, db: Session = Depends(get_db)):
    """Return all sections for a selected manual version."""
    manual = (
        db.query(ManualVersion)
        .filter(ManualVersion.version == version)
        .first()
    )

    if manual is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manual version '{version}' was not found"
        )

    sections = (
        db.query(ManualSection)
        .filter(ManualSection.manual_version_id == manual.id)
        .order_by(ManualSection.id)
        .all()
    )

    return {
        "version": manual.version,
        "total_sections": len(sections),
        "sections": [
            {
                "id": section.id,
                "section_number": section.section_number,
                "heading": section.heading,
                "content": section.content,
                "parent_id": section.parent_id
            }
            for section in sections
        ]
    }


@app.get("/manuals/{version}/sections/{section_number}")
def get_section(
    version: str,
    section_number: str,
    db: Session = Depends(get_db)
):
    """Retrieve one section from a particular manual version."""
    manual = (
        db.query(ManualVersion)
        .filter(ManualVersion.version == version)
        .first()
    )

    if manual is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manual version '{version}' was not found"
        )

    section = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == manual.id,
            ManualSection.section_number == section_number
        )
        .first()
    )

    if section is None:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{section_number}' was not found in {version}"
        )

    return {
        "version": manual.version,
        "section_number": section.section_number,
        "heading": section.heading,
        "content": section.content,
        "parent_id": section.parent_id
    }


@app.get("/manuals/{version}/search")
def search_sections(
    version: str,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """Search section headings and content in a selected version."""
    manual = (
        db.query(ManualVersion)
        .filter(ManualVersion.version == version)
        .first()
    )

    if manual is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manual version '{version}' was not found"
        )

    search_term = f"%{q}%"

    sections = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == manual.id,
            (
                ManualSection.heading.ilike(search_term)
                | ManualSection.content.ilike(search_term)
            )
        )
        .order_by(ManualSection.id)
        .all()
    )

    return {
        "version": manual.version,
        "query": q,
        "count": len(sections),
        "results": [
            {
                "section_number": section.section_number,
                "heading": section.heading,
                "content": section.content
            }
            for section in sections
        ]
    }


@app.get("/compare")
def compare_manuals(db: Session = Depends(get_db)):
    """Compare the imported v1 and v2 manual sections."""
    old_manual = (
        db.query(ManualVersion)
        .filter(ManualVersion.version == "v1")
        .first()
    )
    new_manual = (
        db.query(ManualVersion)
        .filter(ManualVersion.version == "v2")
        .first()
    )

    if old_manual is None or new_manual is None:
        raise HTTPException(
            status_code=404,
            detail="Both v1 and v2 must be imported before comparison"
        )

    old_sections = (
        db.query(ManualSection)
        .filter(ManualSection.manual_version_id == old_manual.id)
        .all()
    )
    new_sections = (
        db.query(ManualSection)
        .filter(ManualSection.manual_version_id == new_manual.id)
        .all()
    )

    old_map = {s.section_number: s for s in old_sections}
    new_map = {s.section_number: s for s in new_sections}

    changes = []

    for number in sorted(set(old_map) | set(new_map)):
        old = old_map.get(number)
        new = new_map.get(number)

        if old is None:
            change_type = "added"
        elif new is None:
            change_type = "removed"
        elif (
            (old.heading or "") != (new.heading or "")
            or (old.content or "") != (new.content or "")
        ):
            change_type = "modified"
        else:
            continue

        changes.append({
            "section_number": number,
            "change_type": change_type,
            "old_heading": old.heading if old else None,
            "new_heading": new.heading if new else None,
            "old_content": old.content if old else None,
            "new_content": new.content if new else None
        })

    return {
        "version_old": "v1",
        "version_new": "v2",
        "total_changes": len(changes),
        "changes": changes
    }


@app.get("/stale-tests")
def get_stale_tests():
    """
    Compare saved QA fingerprints with the latest content
    recorded in change_records.json.
    """
    test_ideas = load_json_file(TEST_IDEAS_FILE)
    changes = load_json_file(CHANGE_RECORDS_FILE)

    latest_sections = {}

    for change in changes:
        section_number = change.get("section_number")
        latest_content = change.get("new_content")

        if section_number is not None and latest_content is not None:
            latest_sections[section_number] = calculate_hash(
                latest_content
            )

    results = []

    for test in test_ideas:
        section_number = test.get("section_number", "Unknown")
        saved_hash = test.get("source_hash")
        latest_hash = latest_sections.get(section_number)

        if latest_hash is None:
            status = "UNKNOWN"
        elif not saved_hash:
            status = "UNKNOWN"
        elif saved_hash == latest_hash:
            status = "CURRENT"
        else:
            status = "STALE"

        results.append({
            "section_number": section_number,
            "source_heading": test.get("source_heading"),
            "source_version": test.get("source_version"),
            "status": status,
            "test_idea": test.get("test_idea"),
            "expected_result": test.get("expected_result")
        })

    return {
        "total_tests": len(results),
        "current": sum(
            item["status"] == "CURRENT" for item in results
        ),
        "stale": sum(
            item["status"] == "STALE" for item in results
        ),
        "unknown": sum(
            item["status"] == "UNKNOWN" for item in results
        ),
        "results": results
    }
