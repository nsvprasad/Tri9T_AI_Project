
import json
import hashlib

def calculate_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# Load the QA test ideas
with open("test_ideas.json", "r", encoding="utf-8") as file:
    test_ideas = json.load(file)

# Load the recorded manual changes
with open("change_records.json", "r", encoding="utf-8") as file:
    changes = json.load(file)

# Build a lookup of the latest section content
latest_sections = {}

for change in changes:
    section_number = change["section_number"]
    latest_content = change.get("new_content") or ""
    latest_sections[section_number] = calculate_hash(latest_content)

# Compare each test's saved fingerprint with the latest fingerprint
for test in test_ideas:
    section_number = test["section_number"]
    saved_hash = test.get("source_hash")
    latest_hash = latest_sections.get(section_number)

    if latest_hash is None:
        status = "UNKNOWN - source section not found"
    elif saved_hash == latest_hash:
        status = "CURRENT"
    else:
        status = "STALE - review this test"

    print(f"Section {section_number}: {status}")

