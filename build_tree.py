
import pymupdf
import re


# STEP 1: Read the original CT-200 manual
pdf = pymupdf.open("data/ct200_manual.pdf")

headings = []

for page in pdf:
    text = page.get_text()

    for line in text.splitlines():
        line = line.strip()

        # Find numbered section headings
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


# STEP 2: Find the expected parent section
def get_parent_number(number):
    parts = number.split(".")

    if len(parts) <= 1:
        return None

    return ".".join(parts[:-1])


# STEP 3: Create a node for every heading
nodes = {}

for heading in headings:
    number = heading["number"]

    nodes[number] = {
        "number": number,
        "title": heading["title"],
        "children": []
    }


# STEP 4: Build the parent-child tree
roots = []
missing_parent_sections = []

for heading in headings:
    number = heading["number"]
    parent = get_parent_number(number)

    if parent is None:
        roots.append(nodes[number])

    elif parent in nodes:
        nodes[parent]["children"].append(nodes[number])

    else:
        # Preserve sections with missing parents separately
        roots.append(nodes[number])

        missing_parent_sections.append({
            "number": number,
            "expected_parent": parent
        })


# STEP 5: Print the tree
def print_tree(node, level=0):
    indent = "    " * level

    print(
        f"{indent}{node['number']} - {node['title']}"
    )

    for child in node["children"]:
        print_tree(child, level + 1)


print("\nCT-200 MANUAL TREE")
print("=" * 40)

for root in roots:
    print_tree(root)


# STEP 6: Report missing parent sections
if missing_parent_sections:
    print("\nMISSING PARENT WARNINGS")
    print("=" * 40)

    for item in missing_parent_sections:
        print(
            f"Section {item['number']} expects parent "
            f"{item['expected_parent']}, which was not found."
        )

print("\nTotal headings extracted:", len(headings))
print("Total root sections:", len(roots))
