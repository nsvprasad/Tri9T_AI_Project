
import pymupdf

# Open the original manual
pdf = pymupdf.open("data/ct200_manual.pdf")

print("Total pages:", len(pdf))

# Read every page
for page_number, page in enumerate(pdf, start=1):
    print(f"\n--- Page {page_number} ---")
    print(page.get_text())

# Close the PDF
pdf.close()
