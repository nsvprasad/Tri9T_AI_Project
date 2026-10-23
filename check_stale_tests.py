import sys
import json
import hashlib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from database import SessionLocal
from staleness_service import evaluate_all_tests
from test_case_store import TestCaseStore

def main():
    store = TestCaseStore()
    cases = store.load_all()

    if not cases:
        # Fallback to test_ideas.json if test_cases.json is empty
        legacy_file = PROJECT_DIR / "test_ideas.json"
        if legacy_file.exists():
            with open(legacy_file, "r", encoding="utf-8") as f:
                cases = json.load(f)

    if not cases:
        print("No test cases found to evaluate.")
        return

    db = SessionLocal()
    try:
        evaluated = evaluate_all_tests(cases, db)
        print("=" * 70)
        print("REAL DATABASE-BACKED QA TEST STALENESS REPORT")
        print("=" * 70)
        for item in evaluated:
            sec = item.get("section_number")
            heading = item.get("source_heading") or "Unknown"
            status = item.get("status")
            reason = item.get("staleness_reason")
            print(f"[{status:7}] Section {sec:<7} ({heading}): {reason}")

        current_count = sum(1 for t in evaluated if t["status"] == "CURRENT")
        stale_count = sum(1 for t in evaluated if t["status"] == "STALE")
        unknown_count = sum(1 for t in evaluated if t["status"] == "UNKNOWN")
        print("=" * 70)
        print(f"Summary: Total: {len(evaluated)} | CURRENT: {current_count} | STALE: {stale_count} | UNKNOWN: {unknown_count}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
