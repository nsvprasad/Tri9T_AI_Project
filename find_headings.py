
# import pymupdf
# import re

# # Open the original manual
# pdf = pymupdf.open("data/ct200_manual.pdf")

# # Look at every page
# for page in pdf:
#     text = page.get_text()

#     # Look at every line on the page
#     for line in text.splitlines():
#         line = line.strip()

#         # Check whether the line starts with a section number
#         if re.match(r"^\d+(\.\d+)*\.?\s+\S", line):
#             print("HEADING:", line)

# pdf.close()






import pymupdf
import re

pdf = pymupdf.open("data/ct200_manual.pdf")

for page in pdf:
    text = page.get_text()

    for line in text.splitlines():
        line = line.strip()

        # Check whether the line starts with a section number
        if re.match(r"^\d+(\.\d+)*\.?\s+\S", line):

            # Ignore the numbered classification list
            if line.startswith((
                "1. Normal:",
                "2. Elevated:",
                "3. Hypertension Stage",
                "4. Hypertension Stage",
                "5. Hypertensive Crisis:"
            )):
                continue

            print("HEADING:", line)

pdf.close()
