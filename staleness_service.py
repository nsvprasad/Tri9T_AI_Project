from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from models import ManualVersion, ManualSection


def evaluate_test_staleness(test_case: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Evaluates whether a test case generated from a pinned version remains CURRENT,
    has become STALE relative to the latest document version, or is UNKNOWN.
    """
    # 1. Identify latest manual version in the system
    latest_version_obj = (
        db.query(ManualVersion)
        .order_by(ManualVersion.id.desc())
        .first()
    )

    if latest_version_obj is None:
        return {
            **test_case,
            "status": "UNKNOWN",
            "valid_for_pinned_version": True,
            "staleness_reason": "No manual versions found in database",
            "latest_version": None,
            "current_hash": None
        }

    latest_ver_str = latest_version_obj.version
    source_ver_str = test_case.get("source_version", "v1")
    section_number = test_case.get("section_number")
    logical_id = test_case.get("logical_id") or section_number
    source_hash = test_case.get("source_hash")

    # 2. Look up the corresponding logical node in the latest version
    latest_section = (
        db.query(ManualSection)
        .filter(
            ManualSection.manual_version_id == latest_version_obj.id,
            (ManualSection.logical_id == logical_id) | (ManualSection.section_number == section_number)
        )
        .first()
    )

    if latest_section is None:
        status = "UNKNOWN"
        reason = f"Logical section '{section_number}' was not found in latest version '{latest_ver_str}'."
        current_hash = None
        current_node_id = None
    elif not source_hash:
        status = "UNKNOWN"
        reason = "Test case record is missing original source hash."
        current_hash = latest_section.content_hash
        current_node_id = latest_section.id
    elif latest_section.content_hash == source_hash:
        status = "CURRENT"
        reason = f"Content fingerprint is identical to latest version '{latest_ver_str}'."
        current_hash = latest_section.content_hash
        current_node_id = latest_section.id
    else:
        status = "STALE"
        reason = (
            f"Content fingerprint changed in latest version '{latest_ver_str}' "
            f"(pinned hash: {source_hash[:8]}..., current hash: {latest_section.content_hash[:8]}...)."
        )
        current_hash = latest_section.content_hash
        current_node_id = latest_section.id

    return {
        "test_id": test_case.get("test_id"),
        "selection_id": test_case.get("selection_id"),
        "source_node_id": test_case.get("source_node_id"),
        "section_number": section_number,
        "source_heading": test_case.get("source_heading"),
        "source_version": source_ver_str,
        "source_hash": source_hash,
        "test_case": test_case.get("test_case"),
        "expected_result": test_case.get("expected_result"),
        "generation_method": test_case.get("generation_method"),
        "status": status,
        "valid_for_pinned_version": True,
        "staleness_reason": reason,
        "latest_version": latest_ver_str,
        "current_node_id": current_node_id,
        "current_hash": current_hash,
        "created_at": test_case.get("created_at")
    }


def evaluate_all_tests(test_cases: List[Dict[str, Any]], db: Session) -> List[Dict[str, Any]]:
    return [evaluate_test_staleness(tc, db) for tc in test_cases]
