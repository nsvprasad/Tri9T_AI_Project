import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from fastapi.testclient import TestClient
from database import SessionLocal
from models import ManualVersion, ManualSection, Selection
from ingest_manuals import ingest_all
from main import app


class TestEndToEndManualIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use deterministic rule fallback for fast, hermetic test execution
        os.environ["FORCE_FALLBACK_TESTS"] = "1"
        # Ingest both manuals to ensure clean, consistent DB state
        ingest_all(force=True)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # -------------------------------------------------------------
    # 1. BROWSE API TESTS
    # -------------------------------------------------------------

    def test_01_get_manuals(self):
        res = self.client.get("/manuals")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data), 2)
        versions = [m["version"] for m in data]
        self.assertIn("v1", versions)
        self.assertIn("v2", versions)

    def test_02_get_top_level_sections(self):
        res = self.client.get("/manuals/top-level-sections?version=v1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["version"], "v1")
        # 8 root chapters in manual: 1 to 8
        self.assertEqual(data["total_top_level_sections"], 8)
        section_nums = [s["section_number"] for s in data["sections"]]
        self.assertEqual(section_nums, ["1", "2", "3", "4", "5", "6", "7", "8"])

    def test_03_get_node_by_id_with_children_and_hash(self):
        # Fetch section 2 (Physical & Electrical Specifications)
        sec_2 = self.db.query(ManualSection).filter(ManualSection.section_number == "2", ManualSection.manual_version_id == 1).first()
        self.assertIsNotNone(sec_2)

        res = self.client.get(f"/nodes/{sec_2.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["section_number"], "2")
        self.assertIn("children", data)
        self.assertGreaterEqual(len(data["children"]), 2)  # 2.1, 2.2
        self.assertIsNotNone(data["content_hash"])

    def test_04_search_sections(self):
        res = self.client.get("/manuals/v1/search?q=battery")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["count"], 0)
        matched_sections = [r["section_number"] for r in data["results"]]
        self.assertIn("2.1.1.1", matched_sections)

    def test_05_compare_versions(self):
        res = self.client.get("/compare")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["version_old"], "v1")
        self.assertEqual(data["version_new"], "v2")
        self.assertGreaterEqual(data["total_changes"], 5)

        changes = {c["section_number"]: c for c in data["changes"]}
        # 3.2 was modified (40 mmHg to 30 mmHg)
        self.assertEqual(changes["3.2"]["change_type"], "modified")
        # 5.3 was added in v2
        self.assertEqual(changes["5.3"]["change_type"], "added")
        # 1.1 was unchanged
        self.assertIn("1.1", data["unchanged_sections"])

    def test_06_node_diff_summary(self):
        sec_3_2 = self.db.query(ManualSection).filter(ManualSection.section_number == "3.2", ManualSection.manual_version_id == 1).first()
        res = self.client.get(f"/nodes/{sec_3_2.id}/changes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_changed"])
        self.assertEqual(data["change_type"], "modified")
        self.assertIn("40 mmHg", data["source_content"])
        self.assertIn("30 mmHg", data["target_content"])
        self.assertGreater(len(data["diff_summary"]), 0)

    # -------------------------------------------------------------
    # 2. SELECTION API & VERSION-PINNING TESTS
    # -------------------------------------------------------------

    def test_07_create_version_pinned_selection(self):
        payload = {
            "name": "End-to-End Safety Test Selection",
            "version": "v1",
            "section_numbers": ["1.1", "3.2", "4.1"]
        }
        res = self.client.post("/selections", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ["created", "existing"])
        selection = data["selection"]
        self.assertEqual(selection["name"], "End-to-End Safety Test Selection")
        self.assertEqual(selection["manual_version"], "v1")
        self.assertEqual(selection["total_items"], 3)

        # Verify items are pinned with exact content and hashes
        items = {item["section_number"]: item for item in selection["items"]}
        self.assertIn("40 mmHg", items["3.2"]["pinned_content"])
        self.assertIsNotNone(items["3.2"]["pinned_hash"])
        self.assertEqual(items["3.2"]["version"], "v1")

    def test_08_selection_duplicate_idempotency_and_conflict(self):
        # 1. Identical submission should return existing (idempotent)
        payload = {
            "name": "End-to-End Safety Test Selection",
            "version": "v1",
            "section_numbers": ["1.1", "3.2", "4.1"]
        }
        res = self.client.post("/selections", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "existing")

        # 2. Conflicting submission with same name but different sections should return 409
        conflicting_payload = {
            "name": "End-to-End Safety Test Selection",
            "version": "v1",
            "section_numbers": ["1.1", "2.1"]
        }
        res_conflict = self.client.post("/selections", json=conflicting_payload)
        self.assertEqual(res_conflict.status_code, 409)

    # -------------------------------------------------------------
    # 3. LLM QA GENERATION FROM SELECTION TESTS
    # -------------------------------------------------------------

    def test_09_generate_qa_tests_from_selection(self):
        # Find the selection created above
        sel = self.db.query(Selection).filter(Selection.name == "End-to-End Safety Test Selection").first()
        self.assertIsNotNone(sel)

        res = self.client.post(f"/selections/{sel.id}/generate?force_regenerate=true")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ["generated", "cached"])
        self.assertGreaterEqual(data["total_tests"], 3)

        # Validate structured fields and traceability
        for test in data["tests"]:
            self.assertEqual(test["selection_id"], sel.id)
            self.assertIsNotNone(test["source_node_id"])
            self.assertIsNotNone(test["section_number"])
            self.assertIsNotNone(test["source_hash"])
            self.assertEqual(test["source_version"], "v1")
            self.assertGreater(len(test["test_case"]), 10)
            self.assertGreater(len(test["expected_result"]), 5)

    # -------------------------------------------------------------
    # 4. STALENESS DETECTION & RETRIEVAL WORKFLOW
    # -------------------------------------------------------------

    def test_10_staleness_detection_v1_to_v2(self):
        sel = self.db.query(Selection).filter(Selection.name == "End-to-End Safety Test Selection").first()
        res = self.client.get(f"/selections/{sel.id}/tests")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["pinned_version"], "v1")
        self.assertGreaterEqual(data["total_tests"], 3)

        tests_by_section = {t["section_number"]: t for t in data["tests"]}

        # Section 3.2 changed from 40 mmHg (v1) to 30 mmHg (v2) -> Must be STALE!
        self.assertIn("3.2", tests_by_section)
        test_3_2 = tests_by_section["3.2"]
        self.assertEqual(test_3_2["status"], "STALE")
        self.assertTrue(test_3_2["valid_for_pinned_version"])
        self.assertEqual(test_3_2["latest_version"], "v2")
        self.assertIn("Content fingerprint changed", test_3_2["staleness_reason"])

        # Section 1.1 unchanged -> Must be CURRENT!
        self.assertIn("1.1", tests_by_section)
        test_1_1 = tests_by_section["1.1"]
        self.assertEqual(test_1_1["status"], "CURRENT")
        self.assertTrue(test_1_1["valid_for_pinned_version"])
        self.assertEqual(test_1_1["latest_version"], "v2")

        # Section 4.1 unchanged -> Must be CURRENT!
        self.assertIn("4.1", tests_by_section)
        test_4_1 = tests_by_section["4.1"]
        self.assertEqual(test_4_1["status"], "CURRENT")

    def test_11_get_tests_by_node_id(self):
        sec_3_2 = self.db.query(ManualSection).filter(ManualSection.section_number == "3.2", ManualSection.manual_version_id == 1).first()
        res = self.client.get(f"/nodes/{sec_3_2.id}/tests")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["section_number"], "3.2")
        self.assertGreater(data["total_tests"], 0)
        self.assertEqual(data["tests"][0]["status"], "STALE")

    def test_12_global_stale_tests_endpoint(self):
        res = self.client.get("/stale-tests")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_tests"], 0)
        self.assertGreater(data["stale"], 0)
        self.assertGreater(data["current"], 0)


if __name__ == "__main__":
    unittest.main()
