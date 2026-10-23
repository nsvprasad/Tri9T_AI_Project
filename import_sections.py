
from compare_content import extract_sections
from database import SessionLocal
from models import ManualVersion, ManualSection


MANUAL_FILES = [
    ("v1", "data/ct200_manual.pdf"),
    ("v2", "data/ct200_manual_v2.pdf"),
]


db = SessionLocal()

try:
    for version, pdf_path in MANUAL_FILES:
        manual = (
            db.query(ManualVersion)
            .filter_by(version=version)
            .first()
        )

        if manual is None:
            print(f"Manual version {version} was not found.")
            continue

        # Prevent duplicate imports when the script is rerun.
        existing_count = (
            db.query(ManualSection)
            .filter_by(manual_version_id=manual.id)
            .count()
        )

        if existing_count > 0:
            print(
                f"{version} already has {existing_count} sections. "
                "Skipping import."
            )
            continue

        print(f"\nImporting {version} from {pdf_path}...")

        sections = extract_sections(pdf_path)
        section_objects = {}

        # First, save all sections without parent links.
        for number, details in sections.items():
            section = ManualSection(
                manual_version_id=manual.id,
                section_number=number,
                heading=details["title"],
                content=details["content"],
            )

            db.add(section)
            section_objects[number] = section

        # Assign IDs before creating parent-child links.
        db.flush()

        # Find each section's parent by its section number.
        for number, section in section_objects.items():
            parts = number.split(".")

            if len(parts) > 1:
                parent_number = ".".join(parts[:-1])
                parent = section_objects.get(parent_number)

                if parent is not None:
                    section.parent_id = parent.id

        db.commit()

        print(f"Imported {len(section_objects)} sections for {version}.")

    print("\nSection import process completed.")

except Exception as error:
    db.rollback()
    print("Import failed:", error)

finally:
    db.close()
