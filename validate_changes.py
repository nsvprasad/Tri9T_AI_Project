
import json
from pathlib import Path


file_path = Path("change_records.json")

# Check whether the JSON file exists
if not file_path.exists():
    print("ERROR: change_records.json was not found.")
    raise SystemExit(1)

# Load the JSON data
with file_path.open("r", encoding="utf-8") as file:
    records = json.load(file)

# Check the structure of each record
required_fields = {
    "section_number",
    "section_title",
    "version_old",
    "version_new",
    "change_type",
    "old_content",
    "new_content"
}

errors = []

for index, record in enumerate(records, start=1):
    missing_fields = required_fields - set(record.keys())

    if missing_fields:
        errors.append(
            f"Record {index} is missing: {sorted(missing_fields)}"
        )

    if record.get("change_type") not in {
        "added", "removed", "modified"
    }:
        errors.append(
            f"Record {index} has an invalid change_type."
        )

    if record.get("version_old") != "v1":
        errors.append(
            f"Record {index} has an unexpected old version."
        )

    if record.get("version_new") != "v2":
        errors.append(
            f"Record {index} has an unexpected new version."
        )

# Display the validation result
if errors:
    print("VALIDATION FAILED")

    for error in errors:
        print("-", error)
else:
    print("VALIDATION PASSED")
    print("Total records:", len(records))

    for record in records:
        print(
            record["section_number"],
            "-",
            record["change_type"]
        )
