import sys
import difflib
from pathlib import Path
from typing import List, Optional, Dict, Any

# Ensure local packages are loaded
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from fastapi import FastAPI, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, engine, Base
from models import ManualVersion, ManualSection, Selection, SelectionItem
from test_case_store import TestCaseStore
from test_generator import generate_tests_for_selection
from staleness_service import evaluate_test_staleness, evaluate_all_tests


app = FastAPI(
    title="Tri9T CT-200 Manual Intelligence API",
    description=(
        "Versioned technical manual intelligence system: document hierarchy, "
        "version-pinned selections, LLM QA test generation, and dynamic staleness detection."
    ),
    version="2.0.0"
)


# ---------------------------------------------------------
# Pydantic Schemas for API Requests and Responses
# ---------------------------------------------------------

class SelectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Unique human-readable selection name")
    version: str = Field(default="v1", description="Manual version to pin this selection against (e.g. v1, v2)")
    node_ids: Optional[List[int]] = Field(default=None, description="List of ManualSection database IDs")
    section_numbers: Optional[List[str]] = Field(default=None, description="List of section numbers, e.g. ['3.2', '4.2']")


# ---------------------------------------------------------
# Root and Status Endpoints
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "system": "Tri9T CT-200 Manual Intelligence System",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "browse": [
                "/manuals",
                "/manuals/top-level-sections?version=latest",
                "/manuals/{version}/sections",
                "/manuals/{version}/sections/{section_number}",
                "/nodes/{node_id}",
                "/nodes/{node_id}/changes",
                "/manuals/{version}/search?q=...",
                "/compare"
            ],
            "selections": [
                "POST /selections",
                "GET /selections",
                "GET /selections/{selection_id}"
            ],
            "qa_generation": [
                "POST /selections/{selection_id}/generate"
            ],
            "retrieval_and_staleness": [
                "GET /selections/{selection_id}/tests",
                "GET /nodes/{node_id}/tests",
                "GET /stale-tests"
            ]
        }
    }


# ---------------------------------------------------------
# Browse API Endpoints
# ---------------------------------------------------------

@app.get("/manuals")
def get_manuals(db: Session = Depends(get_db)):
    """List all imported manual versions."""
    manuals = db.query(ManualVersion).order_by(ManualVersion.id).all()
    return [
        {
            "id": manual.id,
            "version": manual.version,
            "filename": manual.filename,
            "document_title": manual.document_title,
            "created_at": manual.created_at.isoformat() if manual.created_at else None
        }
        for manual in manuals
    ]


@app.get("/manuals/top-level-sections")
def get_top_level_sections(
    version: str = Query(default="latest", description="Manual version ('v1', 'v2', or 'latest')"),
    db: Session = Depends(get_db)
):
    """
    List top-level root sections (level 1) for a specified manual version.
    Defaults to the latest version.
    """
    if version.lower() == "latest":
        manual = db.query(ManualVersion).order_by(ManualVersion.id.desc()).first()
    else:
        manual = db.query(ManualVersion).filter(ManualVersion.version == version).first()

    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual version '{version}' was not found")

    top_sections = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == manual.id,
            ManualSection.parent_id == None
        )
        .order_by(ManualSection.display_order, ManualSection.section_number)
        .all()
    )

    return {
        "version": manual.version,
        "document_title": manual.document_title,
        "total_top_level_sections": len(top_sections),
        "sections": [s.to_dict(include_children=False) for s in top_sections]
    }


@app.get("/nodes/{node_id}")
def get_node_by_id(node_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific node by its unique database ID,
    including its children, full text, level, and content hash.
    """
    node = db.query(ManualSection).filter(ManualSection.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node ID {node_id} was not found")

    return node.to_dict(include_children=True)


@app.get("/nodes/{node_id}/changes")
def get_node_changes(node_id: int, db: Session = Depends(get_db)):
    """
    Given a node ID, determine whether that logical requirement changed
    across manual versions and return a lightweight diff summary.
    """
    node = db.query(ManualSection).filter(ManualSection.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node ID {node_id} was not found")

    source_ver = node.manual_version.version
    target_ver = "v2" if source_ver == "v1" else "v1"

    target_manual = db.query(ManualVersion).filter(ManualVersion.version == target_ver).first()
    if target_manual is None:
        raise HTTPException(status_code=404, detail=f"Target manual version '{target_ver}' not imported")

    # Match logical node in target manual
    target_node = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == target_manual.id,
            (ManualSection.logical_id == node.logical_id) | (ManualSection.section_number == node.section_number)
        )
        .first()
    )

    if target_node is None:
        change_type = "removed" if source_ver == "v1" else "added"
        return {
            "node_id": node.id,
            "section_number": node.section_number,
            "heading": node.heading,
            "source_version": source_ver,
            "target_version": target_ver,
            "has_changed": True,
            "change_type": change_type,
            "diff_summary": f"Section exists in {source_ver} but is absent in {target_ver}."
        }

    # Compare hashes and content
    has_changed = (node.content_hash != target_node.content_hash)
    if not has_changed:
        return {
            "node_id": node.id,
            "section_number": node.section_number,
            "heading": node.heading,
            "source_version": source_ver,
            "target_version": target_ver,
            "has_changed": False,
            "change_type": "unchanged",
            "content_hash": node.content_hash,
            "diff_summary": "Content and heading are identical across versions."
        }

    # Generate unified diff
    old_text = f"{node.heading}\n{node.content or ''}"
    new_text = f"{target_node.heading}\n{target_node.content or ''}"
    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=f"{source_ver}/{node.section_number}",
        tofile=f"{target_ver}/{target_node.section_number}",
        lineterm=""
    ))

    similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()

    return {
        "node_id": node.id,
        "section_number": node.section_number,
        "heading": node.heading,
        "source_version": source_ver,
        "target_version": target_ver,
        "has_changed": True,
        "change_type": "modified",
        "similarity_ratio": round(similarity, 4),
        "source_hash": node.content_hash,
        "target_hash": target_node.content_hash,
        "diff_summary": diff_lines,
        "source_content": node.content,
        "target_content": target_node.content
    }


@app.get("/manuals/{version}/sections")
def get_sections(version: str, db: Session = Depends(get_db)):
    """Return all sections for a selected manual version."""
    manual = db.query(ManualVersion).filter(ManualVersion.version == version).first()
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual version '{version}' was not found")

    sections = (
        db.query(ManualSection)
        .filter(ManualSection.manual_version_id == manual.id)
        .order_by(ManualSection.display_order, ManualSection.id)
        .all()
    )

    return {
        "version": manual.version,
        "document_title": manual.document_title,
        "total_sections": len(sections),
        "sections": [s.to_dict(include_children=False) for s in sections]
    }


@app.get("/manuals/{version}/sections/{section_number}")
def get_section(version: str, section_number: str, db: Session = Depends(get_db)):
    """Retrieve one section from a particular manual version."""
    manual = db.query(ManualVersion).filter(ManualVersion.version == version).first()
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual version '{version}' was not found")

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

    return section.to_dict(include_children=True)


@app.get("/manuals/{version}/search")
def search_sections(
    version: str,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """Search section headings and content in a selected version."""
    manual = db.query(ManualVersion).filter(ManualVersion.version == version).first()
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual version '{version}' was not found")

    search_term = f"%{q}%"
    sections = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == manual.id,
            (ManualSection.heading.ilike(search_term) | ManualSection.content.ilike(search_term))
        )
        .order_by(ManualSection.display_order, ManualSection.id)
        .all()
    )

    return {
        "version": manual.version,
        "query": q,
        "count": len(sections),
        "results": [
            {
                "id": s.id,
                "section_number": s.section_number,
                "heading": s.heading,
                "level": s.level,
                "content_hash": s.content_hash,
                "content": s.content
            }
            for s in sections
        ]
    }


@app.get("/compare")
def compare_manuals(db: Session = Depends(get_db)):
    """Compare imported v1 and v2 manual sections and return categorized diffs."""
    old_manual = db.query(ManualVersion).filter(ManualVersion.version == "v1").first()
    new_manual = db.query(ManualVersion).filter(ManualVersion.version == "v2").first()

    if old_manual is None or new_manual is None:
        raise HTTPException(status_code=404, detail="Both v1 and v2 must be imported before comparison")

    old_sections = db.query(ManualSection).filter(ManualSection.manual_version_id == old_manual.id).all()
    new_sections = db.query(ManualSection).filter(ManualSection.manual_version_id == new_manual.id).all()

    old_map = {s.section_number: s for s in old_sections}
    new_map = {s.section_number: s for s in new_sections}

    changes = []
    unchanged = []

    for number in sorted(set(old_map) | set(new_map)):
        old = old_map.get(number)
        new = new_map.get(number)

        if old is None:
            change_type = "added"
        elif new is None:
            change_type = "removed"
        elif (old.content_hash or "") != (new.content_hash or "") or (old.heading != new.heading):
            change_type = "modified"
        else:
            unchanged.append(number)
            continue

        changes.append({
            "section_number": number,
            "change_type": change_type,
            "old_heading": old.heading if old else None,
            "new_heading": new.heading if new else None,
            "old_hash": old.content_hash if old else None,
            "new_hash": new.content_hash if new else None,
            "old_content": old.content if old else None,
            "new_content": new.content if new else None
        })

    return {
        "version_old": "v1",
        "version_new": "v2",
        "total_changes": len(changes),
        "total_unchanged": len(unchanged),
        "unchanged_sections": unchanged,
        "changes": changes
    }


# ---------------------------------------------------------
# Selection API Endpoints
# ---------------------------------------------------------

@app.post("/selections")
def create_selection(req: SelectionCreateRequest, db: Session = Depends(get_db)):
    """
    Create a persistent, version-pinned selection.
    Pins the exact node content and SHA-256 fingerprints at creation time.
    Duplicate submission policy: Idempotent if matching identical nodes.
    """
    manual = db.query(ManualVersion).filter(ManualVersion.version == req.version).first()
    if manual is None:
        raise HTTPException(status_code=404, detail=f"Manual version '{req.version}' was not found")

    # Find matching sections
    sections: List[ManualSection] = []
    if req.node_ids:
        sections = (
            db.query(ManualSection)
            .filter(
                ManualSection.manual_version_id == manual.id,
                ManualSection.id.in_(req.node_ids)
            )
            .all()
        )
        found_ids = {s.id for s in sections}
        missing_ids = set(req.node_ids) - found_ids
        if missing_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Node IDs not found in version '{req.version}': {sorted(missing_ids)}"
            )

    elif req.section_numbers:
        sections = (
            db.query(ManualSection)
            .filter(
                ManualSection.manual_version_id == manual.id,
                ManualSection.section_number.in_(req.section_numbers)
            )
            .all()
        )
        found_nums = {s.section_number for s in sections}
        missing_nums = set(req.section_numbers) - found_nums
        if missing_nums:
            raise HTTPException(
                status_code=400,
                detail=f"Section numbers not found in version '{req.version}': {sorted(missing_nums)}"
            )
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'node_ids' or 'section_numbers'")

    if not sections:
        raise HTTPException(status_code=400, detail="No matching sections found for selection")

    # Check duplicate submission policy
    existing = (
        db.query(Selection)
        .filter(Selection.name == req.name, Selection.manual_version == req.version)
        .first()
    )
    if existing is not None:
        existing_section_nums = {item.section_number for item in existing.items}
        requested_section_nums = {s.section_number for s in sections}
        if existing_section_nums == requested_section_nums:
            return {
                "message": "Selection already exists with identical sections (idempotent response).",
                "status": "existing",
                "selection": existing.to_dict()
            }
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Selection '{req.name}' already exists for version '{req.version}' with different sections."
            )

    # Create new selection
    selection = Selection(
        name=req.name,
        manual_version=req.version
    )
    db.add(selection)
    db.flush()

    # Pin items
    for s in sections:
        item = SelectionItem(
            selection_id=selection.id,
            section_id=s.id,
            logical_id=s.logical_id or s.section_number,
            section_number=s.section_number,
            heading=s.heading,
            version=req.version,
            pinned_hash=s.content_hash or s.compute_hash(),
            pinned_content=s.content
        )
        db.add(item)

    db.commit()
    db.refresh(selection)

    return {
        "message": "Version-pinned selection created successfully.",
        "status": "created",
        "selection": selection.to_dict()
    }


@app.get("/selections")
def list_selections(db: Session = Depends(get_db)):
    """List all saved named selections."""
    selections = db.query(Selection).order_by(Selection.id).all()
    return [s.to_dict() for s in selections]


@app.get("/selections/{selection_id}")
def get_selection(selection_id: int, db: Session = Depends(get_db)):
    """Get a specific named selection with its pinned sections and exact source text."""
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if selection is None:
        raise HTTPException(status_code=404, detail=f"Selection ID {selection_id} was not found")
    return selection.to_dict()


# ---------------------------------------------------------
# LLM QA Test Generation API
# ---------------------------------------------------------

@app.post("/selections/{selection_id}/generate")
def generate_tests(
    selection_id: int,
    force_regenerate: bool = Query(default=False, description="Set True to regenerate if already exists"),
    db: Session = Depends(get_db)
):
    """
    Generate 3-5 QA test cases from a saved version-pinned selection.
    Uses Gemini when available; falls back automatically to validated rule-based QA cases.
    """
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if selection is None:
        raise HTTPException(status_code=404, detail=f"Selection ID {selection_id} was not found")

    result = generate_tests_for_selection(selection, force_regenerate=force_regenerate)
    return result


# ---------------------------------------------------------
# Retrieval and Staleness API Endpoints
# ---------------------------------------------------------

@app.get("/selections/{selection_id}/tests")
def get_tests_for_selection(selection_id: int, db: Session = Depends(get_db)):
    """
    Fetch previously generated test cases for a selection ID.
    Staleness status (CURRENT, STALE, UNKNOWN) is calculated dynamically
    against the latest manual version in the database.
    """
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if selection is None:
        raise HTTPException(status_code=404, detail=f"Selection ID {selection_id} was not found")

    store = TestCaseStore()
    cases = store.get_by_selection_id(selection_id)
    evaluated = evaluate_all_tests(cases, db)

    return {
        "selection_id": selection_id,
        "selection_name": selection.name,
        "pinned_version": selection.manual_version,
        "total_tests": len(evaluated),
        "current_tests": sum(1 for t in evaluated if t["status"] == "CURRENT"),
        "stale_tests": sum(1 for t in evaluated if t["status"] == "STALE"),
        "unknown_tests": sum(1 for t in evaluated if t["status"] == "UNKNOWN"),
        "tests": evaluated
    }


@app.get("/nodes/{node_id}/tests")
def get_tests_for_node(node_id: int, db: Session = Depends(get_db)):
    """
    Fetch previously generated test cases that trace back to a specific node ID.
    Includes dynamically calculated staleness.
    """
    node = db.query(ManualSection).filter(ManualSection.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node ID {node_id} was not found")

    store = TestCaseStore()
    cases = store.get_by_node_id(node_id)
    if not cases:
        # Fall back to section number matching if node was pinned in a different session
        cases = store.get_by_section_number(node.section_number)

    evaluated = evaluate_all_tests(cases, db)

    return {
        "node_id": node.id,
        "section_number": node.section_number,
        "heading": node.heading,
        "total_tests": len(evaluated),
        "tests": evaluated
    }


@app.get("/stale-tests")
def get_stale_tests(db: Session = Depends(get_db)):
    """
    Check all stored QA test cases against the latest manual version.
    Staleness is determined using the real database records and content hashes.
    """
    store = TestCaseStore()
    all_cases = store.load_all()

    # If no cases in store yet, seed from legacy test_ideas.json if present
    if not all_cases:
        legacy_file = PROJECT_DIR / "test_ideas.json"
        if legacy_file.exists():
            try:
                import json
                with open(legacy_file, "r", encoding="utf-8") as f:
                    legacy_ideas = json.load(f)
                    seeded = []
                    for idx, idea in enumerate(legacy_ideas):
                        seeded.append({
                            "test_id": f"legacy-{idx+1}",
                            "selection_id": 1,
                            "source_node_id": idx + 1,
                            "logical_id": idea.get("section_number"),
                            "section_number": idea.get("section_number"),
                            "source_heading": idea.get("source_heading"),
                            "source_version": idea.get("source_version", "v1"),
                            "source_hash": idea.get("source_hash"),
                            "test_case": idea.get("test_idea"),
                            "expected_result": idea.get("expected_result"),
                            "generation_method": "legacy-import",
                            "created_at": "2026-10-23T00:00:00"
                        })
                    store.save_all(seeded)
                    all_cases = seeded
            except Exception:
                pass

    evaluated = evaluate_all_tests(all_cases, db)

    return {
        "total_tests": len(evaluated),
        "current": sum(1 for t in evaluated if t["status"] == "CURRENT"),
        "stale": sum(1 for t in evaluated if t["status"] == "STALE"),
        "unknown": sum(1 for t in evaluated if t["status"] == "UNKNOWN"),
        "results": evaluated
    }
