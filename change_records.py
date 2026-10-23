
import json
from compare_content import extract_sections


# Load both manual versions
v1 = extract_sections("data/ct200_manual.pdf")
v2 = extract_sections("data/ct200_manual_v2.pdf")

change_records = []

# Find added sections
for number, section in v2.items():
    if number not in v1:
        change_records.append({
            "section_number": number,
            "section_title": section["title"],
            "version_old": "v1",
            "version_new": "v2",
            "change_type": "added",
            "old_content": None,
            "new_content": section["content"]
        })


# Find removed sections
for number, section in v1.items():
    if number not in v2:
        change_records.append({
            "section_number": number,
            "section_title": section["title"],
            "version_old": "v1",
            "version_new": "v2",
            "change_type": "removed",
            "old_content": section["content"],
            "new_content": None
        })


# Find modified sections
for number, old_section in v1.items():
    if number not in v2:
        continue

    new_section = v2[number]

    old_content = (
        old_section["title"] + " " + old_section["content"]
    )
    new_content = (
        new_section["title"] + " " + new_section["content"]
    )

    if old_content != new_content:
        change_records.append({
            "section_number": number,
            "section_title": old_section["title"],
            "version_old": "v1",
            "version_new": "v2",
            "change_type": "modified",
            "old_content": old_content,
            "new_content": new_content
        })


# Save the records as JSON
with open("change_records.json", "w", encoding="utf-8") as file:
    json.dump(change_records, file, indent=4, ensure_ascii=False)

print("Change records created:", len(change_records))
print("Saved to change_records.json")

for record in change_records:
    print(
        record["section_number"],
        "-",
        record["change_type"],
        "-",
        record["section_title"]
    )
