
from database import SessionLocal
from models import ManualVersion

# Open a database session
db = SessionLocal()

try:
    # Check whether the manuals have already been added
    existing = db.query(ManualVersion).count()

    if existing == 0:
        manual_v1 = ManualVersion(
            version="v1",
            filename="ct200_manual.pdf"
        )

        manual_v2 = ManualVersion(
            version="v2",
            filename="ct200_manual_v2.pdf"
        )

        db.add_all([manual_v1, manual_v2])
        db.commit()

        print("Both manual versions added successfully!")
    else:
        print("Manual versions already exist. No duplicates added.")

    # Display the saved records
    manuals = db.query(ManualVersion).order_by(
        ManualVersion.id
    ).all()

    print("\nManual versions in the database:")

    for manual in manuals:
        print(
            f"ID: {manual.id} | "
            f"Version: {manual.version} | "
            f"File: {manual.filename}"
        )

except Exception as error:
    db.rollback()
    print("An error occurred:", error)

finally:
    db.close()
