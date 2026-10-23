import sys
from pathlib import Path
import unittest

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from pdf_parser import parse_ct200_pdf


class TestCT200StructuralIrregularities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1_data = parse_ct200_pdf(str(PROJECT_DIR / "data" / "ct200_manual.pdf"))
        cls.v2_data = parse_ct200_pdf(str(PROJECT_DIR / "data" / "ct200_manual_v2.pdf"))

        cls.v1_sections = {s["section_number"]: s for s in cls.v1_data["sections"]}
        cls.v2_sections = {s["section_number"]: s for s in cls.v2_data["sections"]}

    def test_duplicate_headings(self):
        """
        Irregularity 1: Duplicate Headings
        'Error Codes' appears in Section 4.2 (under 4. Alarms and Safety Behavior)
        and Section 7.1 (under 7. Troubleshooting).
        Assert that both produce distinct section nodes with distinct parents.
        """
        self.assertIn("4.2", self.v1_sections, "Section 4.2 must exist")
        self.assertIn("7.1", self.v1_sections, "Section 7.1 must exist")

        sec_4_2 = self.v1_sections["4.2"]
        sec_7_1 = self.v1_sections["7.1"]

        # Both share the same heading title
        self.assertEqual(sec_4_2["heading"], "Error Codes")
        self.assertEqual(sec_7_1["heading"], "Error Codes")

        # But have distinct parent numbers
        self.assertEqual(sec_4_2["parent_number"], "4")
        self.assertEqual(sec_7_1["parent_number"], "7")

        # And distinct logical identifiers and distinct content
        self.assertNotEqual(sec_4_2["logical_id"], sec_7_1["logical_id"])
        self.assertNotEqual(sec_4_2["content_hash"], sec_7_1["content_hash"])
        self.assertIn("E1", sec_4_2["content"])
        self.assertIn("retry prompt", sec_7_1["content"])

    def test_missing_parent_hierarchy(self):
        """
        Irregularity 2: Missing Parent Heading
        Section '2.1.1.1 Battery Life Under Typical Use' skips '2.1.1'
        and should attach to the nearest existing ancestor '2.1'.
        """
        self.assertIn("2.1.1.1", self.v1_sections, "Section 2.1.1.1 must be extracted")
        self.assertNotIn("2.1.1", self.v1_sections, "Section 2.1.1 should not exist in PDF")

        sec_2_1_1_1 = self.v1_sections["2.1.1.1"]
        self.assertEqual(sec_2_1_1_1["heading"], "Battery Life Under Typical Use")
        self.assertEqual(
            sec_2_1_1_1["parent_number"], "2.1",
            "Missing parent 2.1.1 should resolve to closest ancestor 2.1"
        )
        self.assertIn("alkaline batteries", sec_2_1_1_1["content"])

    def test_numbered_lists_not_mistaken_for_headings(self):
        """
        Irregularity 3: Numbered Lists in Body Text
        Section 3.3 contains:
          1. Normal: systolic < 120 and diastolic < 80
          2. Elevated: systolic 120-129 and diastolic < 80
        These must NOT be extracted as root sections '1', '2', etc.
        They must remain preserved within the body text of Section 3.3.
        """
        sec_3_3 = self.v1_sections.get("3.3")
        self.assertIsNotNone(sec_3_3, "Section 3.3 must exist")
        self.assertEqual(sec_3_3["heading"], "Result Display and Classification")

        # Root Section 1 must remain 'Device Overview'
        sec_1 = self.v1_sections.get("1")
        self.assertEqual(sec_1["heading"], "Device Overview")

        # Section 3.3 body content must retain the numbered classification items
        self.assertIn("Normal: systolic < 120", sec_3_3["content"])
        self.assertIn("Elevated: systolic 120", sec_3_3["content"])
        self.assertIn("Hypertensive Crisis", sec_3_3["content"])

    def test_out_of_order_sections(self):
        """
        Irregularity 4: Out-of-Order Sections
        In Chapter 3, section 3.4 ('Auto Shutoff') physically appears before
        section 3.3 ('Result Display and Classification').
        Assert that appearance order is preserved via display_order, while both
        correctly link to parent '3'.
        """
        sec_3_3 = self.v1_sections["3.3"]
        sec_3_4 = self.v1_sections["3.4"]

        # Both belong to parent 3
        self.assertEqual(sec_3_3["parent_number"], "3")
        self.assertEqual(sec_3_4["parent_number"], "3")

        # 3.4 appears before 3.3 in document order
        self.assertLess(
            sec_3_4["display_order"], sec_3_3["display_order"],
            "Section 3.4 should have lower display_order than 3.3"
        )

    def test_version_differences_and_hashes(self):
        """
        Test that content hashes accurately reflect modifications between v1 and v2.
        - Section 1.1 is unchanged -> identical hashes.
        - Section 3.2 is modified (40 mmHg vs 30 mmHg) -> distinct hashes.
        - Section 5.3 is added in v2 -> absent in v1.
        """
        # Unchanged section
        self.assertEqual(
            self.v1_sections["1.1"]["content_hash"],
            self.v2_sections["1.1"]["content_hash"],
            "Unchanged section 1.1 should have identical content hash"
        )

        # Modified section
        self.assertNotEqual(
            self.v1_sections["3.2"]["content_hash"],
            self.v2_sections["3.2"]["content_hash"],
            "Modified section 3.2 must produce different content hash"
        )
        self.assertIn("40 mmHg", self.v1_sections["3.2"]["content"])
        self.assertIn("30 mmHg", self.v2_sections["3.2"]["content"])

        # Added section in v2
        self.assertNotIn("5.3", self.v1_sections)
        self.assertIn("5.3", self.v2_sections)
        self.assertEqual(self.v2_sections["5.3"]["heading"], "Data Export")


if __name__ == "__main__":
    unittest.main()
