import sys
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))

DB_PATH = PROJECT_DIR / "tri9t.db"

def migrate():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Check columns in manual_versions
    cur.execute("PRAGMA table_info(manual_versions)")
    version_cols = {col[1] for col in cur.fetchall()}
    if "document_title" not in version_cols:
        print("Adding document_title to manual_versions...")
        cur.execute("ALTER TABLE manual_versions ADD COLUMN document_title VARCHAR")

    # Check columns in manual_sections
    cur.execute("PRAGMA table_info(manual_sections)")
    section_cols = {col[1] for col in cur.fetchall()}

    columns_to_add = [
        ("logical_id", "VARCHAR"),
        ("level", "INTEGER DEFAULT 1"),
        ("content_hash", "VARCHAR"),
        ("display_order", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in section_cols:
            print(f"Adding {col_name} to manual_sections...")
            cur.execute(f"ALTER TABLE manual_sections ADD COLUMN {col_name} {col_type}")

    con.commit()
    con.close()
    print("Database migration completed successfully.")

if __name__ == "__main__":
    migrate()
