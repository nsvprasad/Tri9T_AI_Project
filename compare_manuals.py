
import pymupdf
import re


def extract_headings(pdf_path):
    """Extract numbered headings from a PDF manual."""

    pdf = pymupdf.open(pdf_path)
    headings = []

    for page in pdf:
        text = page.get_text()

        for line in text.splitlines():
            line = line.strip()

            match = re.match(
                r"^(\d+(?:\.\d+)*\.?)\s+(.+)$",
                line
            )

            if not match:
                continue

            number = match.group(1).rstrip(".")
            title = match.group(2)

            # Skip numbered blood pressure classification items
            if title.startswith((
                "Normal:",
                "Elevated:",
                "Hypertension Stage",
                "Hypertensive Crisis:"
            )):
                continue

            headings.append({
                "number": number,
                "title": title
            })

    pdf.close()
    return headings


# Extract headings from both versions
v1 = extract_headings("data/ct200_manual.pdf")
v2 = extract_headings("data/ct200_manual_v2.pdf")


# Create dictionaries using section numbers as keys
v1_sections = {item["number"]: item["title"] for item in v1}
v2_sections = {item["number"]: item["title"] for item in v2}


print("\nMANUAL HEADING COMPARISON")
print("=" * 50)

# Find sections added in version 2
for number in v2_sections:
    if number not in v1_sections:
        print(f"ADDED: {number} - {v2_sections[number]}")

# Find sections removed from version 1
for number in v1_sections:
    if number not in v2_sections:
        print(f"REMOVED: {number} - {v1_sections[number]}")

# Find headings whose titles changed
for number in v1_sections:
    if number in v2_sections:
        if v1_sections[number] != v2_sections[number]:
            print(f"TITLE CHANGED: {number}")
            print(f"  V1: {v1_sections[number]}")
            print(f"  V2: {v2_sections[number]}")

print("\nComparison complete.")
print("V1 headings:", len(v1))
print("V2 headings:", len(v2))
