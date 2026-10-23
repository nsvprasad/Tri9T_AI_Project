import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from database import SessionLocal, engine, Base
from models import ManualVersion, ManualSection
from pdf_parser import parse_ct200_pdf


MANUAL_DEFINITIONS = [
    ("v1", "data/ct200_manual.pdf"),
    ("v2", "data/ct200_manual_v2.pdf"),
]


def ingest_manual(version_str: str, pdf_path: str, force_reingest: bool = False) -> Tuple[int, int]:
    """
    Ingest or re-ingest a manual version into SQLite.
    Preserves version isolation and populates levels, parent IDs, hashes, and display orders.
    Returns (version_id, count_of_sections).
    """
    db = SessionLocal()
    try:
        parsed = parse_ct200_pdf(pdf_path)

        manual = db.query(ManualVersion).filter_by(version=version_str).first()
        if manual is None:
            manual = ManualVersion(
                version=version_str,
                filename=Path(pdf_path).name,
                document_title=parsed["document_title"]
            )
            db.add(manual)
            db.flush()
        else:
            manual.document_title = parsed["document_title"]
            manual.filename = Path(pdf_path).name
            if force_reingest:
                # Remove old sections for this version
                db.query(ManualSection).filter_by(manual_version_id=manual.id).delete()
                db.flush()
            else:
                existing_count = db.query(ManualSection).filter_by(manual_version_id=manual.id).count()
                if existing_count > 0:
                    # Update columns on existing sections (hashes, levels, etc.) if they were blank
                    existing_sections = {s.section_number: s for s in db.query(ManualSection).filter_by(manual_version_id=manual.id).all()}
                    for item in parsed["sections"]:
                        sec = existing_sections.get(item["section_number"])
                        if sec:
                            sec.level = item["level"]
                            sec.content_hash = item["content_hash"]
                            sec.logical_id = item["logical_id"]
                            sec.display_order = item["display_order"]
                    db.commit()
                    return manual.id, existing_count

        section_objects: Dict[str, ManualSection] = {}

        # First pass: create all section objects
        for item in parsed["sections"]:
            sec = ManualSection(
                manual_version_id=manual.id,
                logical_id=item["logical_id"],
                section_number=item["section_number"],
                heading=item["heading"],
                level=item["level"],
                content=item["content"],
                content_hash=item["content_hash"],
                display_order=item["display_order"],
            )
            db.add(sec)
            section_objects[item["section_number"]] = sec

        db.flush()

        # Second pass: wire up parent-child relationships
        for item in parsed["sections"]:
            parent_num = item["parent_number"]
            if parent_num and parent_num in section_objects:
                section_objects[item["section_number"]].parent_id = section_objects[parent_num].id

        db.commit()
        return manual.id, len(section_objects)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ingest_all(force: bool = False):
    Base.metadata.create_all(bind=engine)
    print("=" * 60)
    print("INGESTING CT-200 MANUALS")
    print("=" * 60)
    for v_str, pdf_rel in MANUAL_DEFINITIONS:
        full_path = str(PROJECT_DIR / pdf_rel)
        vid, count = ingest_manual(v_str, full_path, force_reingest=force)
        print(f"Manual {v_str} (ID={vid}): Ingested {count} structured sections.")


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    ingest_all(force=force_flag)
