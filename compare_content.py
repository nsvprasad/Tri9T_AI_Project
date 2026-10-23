
import pymupdf
import re
import unicodedata
import difflib


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_sections(pdf_path):
    pdf = pymupdf.open(pdf_path)
    sections = {}
    current_section = None

    heading_pattern = re.compile(
        r"^(\d+(?:\.\d+)*\.?)\s+(.+)$"
    )

    for page in pdf:
        for line in page.get_text().splitlines():
            line = line.strip()
            match = heading_pattern.match(line)

            if match:
                number = match.group(1).rstrip(".")
                title = match.group(2)

                if title.startswith((
                    "Normal:",
                    "Elevated:",
                    "Hypertension Stage",
                    "Hypertensive Crisis:"
                )):
                    if current_section is not None:
                        sections[current_section]["content"] += " " + line
                    continue

                current_section = number

                if number not in sections:
                    sections[number] = {
                        "title": title,
                        "content": ""
                    }
                else:
                    sections[number]["content"] += " " + title

            elif current_section is not None:
                sections[current_section]["content"] += " " + line

    pdf.close()

    for section in sections.values():
        section["title"] = normalize_text(section["title"])
        section["content"] = normalize_text(section["content"])

    return sections


v1 = extract_sections("data/ct200_manual.pdf")
v2 = extract_sections("data/ct200_manual_v2.pdf")

print("\nCT-200 CONTENT COMPARISON")
print("=" * 50)

for number in v2:
    if number not in v1:
        print(f"\nADDED SECTION: {number} - {v2[number]['title']}")

for number in v1:
    if number not in v2:
        print(f"\nREMOVED SECTION: {number} - {v1[number]['title']}")

for number in v1:
    if number not in v2:
        continue

    old_text = v1[number]["title"] + " " + v1[number]["content"]
    new_text = v2[number]["title"] + " " + v2[number]["content"]

    if old_text != new_text:
        print(f"\nCONTENT CHANGED: Section {number}")
        print("V1:", old_text[:500])
        print("V2:", new_text[:500])

        similarity = difflib.SequenceMatcher(
            None, old_text, new_text
        ).ratio()

        print(f"Text similarity: {similarity:.2%}")
        print("Exact text differences:")

        differences = difflib.unified_diff(
            old_text.split(),
            new_text.split(),
            fromfile="V1",
            tofile="V2",
            lineterm=""
        )

        for line in differences:
            print(line)

print("\nComparison complete.")
print("V1 sections:", len(v1))
print("V2 sections:", len(v2))
