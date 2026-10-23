
from database import SessionLocal
from models import ManualVersion, ManualSection

db = SessionLocal()

try:
    manuals = db.query(ManualVersion).order_by(
        ManualVersion.id
    ).all()

    for manual in manuals:
        sections = (
            db.query(ManualSection)
            .filter_by(manual_version_id=manual.id)
            .order_by(ManualSection.id)
            .all()
        )

        print(f"\nManual version: {manual.version}")
        print(f"Total sections: {len(sections)}")

        for section in sections[:5]:
            print(
                f"{section.section_number} - "
                f"{section.heading}"
            )

finally:
    db.close()
