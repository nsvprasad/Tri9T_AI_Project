import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, ValidationError

PROJECT_DIR = Path(__file__).resolve().parent
TEST_CASES_FILE = PROJECT_DIR / "test_cases.json"
TEST_IDEAS_FILE = PROJECT_DIR / "test_ideas.json"


class QATestCaseSchema(BaseModel):
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    selection_id: int
    source_node_id: int
    logical_id: str
    section_number: str
    source_heading: str
    source_version: str
    source_hash: str
    test_case: str = Field(min_length=10)
    expected_result: str = Field(min_length=5)
    generation_method: str = "gemini-3.8-flash"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class TestCaseStore:
    def __init__(self, file_path: Path = TEST_CASES_FILE):
        self.file_path = file_path
        self._ensure_store()

    def _ensure_store(self):
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_all(self) -> List[Dict[str, Any]]:
        self._ensure_store()
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save_all(self, test_cases: List[Dict[str, Any]]):
        temp_file = self.file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.file_path)

        # Synchronize backward-compatible test_ideas.json
        legacy_ideas = []
        for tc in test_cases:
            legacy_ideas.append({
                "section_number": tc["section_number"],
                "source_heading": tc["source_heading"],
                "source_version": tc["source_version"],
                "source_hash": tc["source_hash"],
                "test_idea": tc["test_case"],
                "expected_result": tc["expected_result"]
            })
        temp_legacy = TEST_IDEAS_FILE.with_suffix(".tmp")
        with open(temp_legacy, "w", encoding="utf-8") as f:
            json.dump(legacy_ideas, f, indent=2, ensure_ascii=False)
        temp_legacy.replace(TEST_IDEAS_FILE)

    def add_cases(self, new_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing = self.load_all()
        validated_cases = []
        for case in new_cases:
            validated = QATestCaseSchema(**case).model_dump()
            validated_cases.append(validated)
        existing.extend(validated_cases)
        self.save_all(existing)
        return validated_cases

    def get_by_selection_id(self, selection_id: int) -> List[Dict[str, Any]]:
        return [tc for tc in self.load_all() if tc.get("selection_id") == selection_id]

    def get_by_node_id(self, node_id: int) -> List[Dict[str, Any]]:
        return [tc for tc in self.load_all() if tc.get("source_node_id") == node_id]

    def get_by_section_number(self, section_number: str) -> List[Dict[str, Any]]:
        return [tc for tc in self.load_all() if tc.get("section_number") == section_number]
