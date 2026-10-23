import os
import sys
import json
import time
import uuid
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))
sys.path.insert(0, str(PROJECT_DIR))

from test_case_store import TestCaseStore, QATestCaseSchema, normalize_for_dedup
from models import Selection, SelectionItem

logger = logging.getLogger("test_generator")

# Supported Gemini models in order of priority
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash"]


def get_distinct_fallback_cases_for_item(item: SelectionItem) -> List[Dict[str, str]]:
    """
    Generate three genuinely distinct, clinically accurate rule-based test cases
    for a pinned manual requirement. Covers:
      1. Normal operation / nominal workflow
      2. Boundary condition / threshold / step increment
      3. Maximum limit / error abort / safety intervention
    """
    sec = str(item.section_number).strip()
    heading = item.heading.strip()
    content = item.pinned_content or ""
    version = item.version

    if sec == "3.2":
        step_increment = "30 mmHg" if "30 mmHg" in content else "40 mmHg"
        deflation_timing = "approximately 3 mmHg"

        return [
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Nominal Cuff Inflation and Pulse Acquisition",
                "test_case": (
                    f"Connect the CT-200 to a patient simulator with normal pulse signal detectable below 180 mmHg. "
                    "Power on the device, select User Profile 1, and press Start. Observe the initial inflation phase "
                    "and pressure gauge reading."
                ),
                "expected_result": (
                    f"The cuff inflates smoothly to the initial target of 180 mmHg, acquires oscillometric pulse data, "
                    f"and initiates controlled deflation in steps of {deflation_timing} to complete the reading."
                )
            },
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Incremental Inflation Above Initial Target",
                "test_case": (
                    "Configure simulator so that no pulse is detectable at or below 180 mmHg. Initiate measurement "
                    "and record cuff pressure increases above the initial 180 mmHg target."
                ),
                "expected_result": (
                    f"Upon reaching 180 mmHg without pulse detection, the device automatically increases pressure in "
                    f"{step_increment} increments toward 299 mmHg to acquire pulse data before timing out."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Maximum Pressure Ceiling Safety Abort",
                "test_case": (
                    "Configure simulator to suppress pulse detection across all inflation stages. Initiate measurement "
                    "and monitor device behavior as cuff pressure approaches the 299 mmHg maximum rating."
                ),
                "expected_result": (
                    "The device inflates in documented increments up to the maximum limit of 299 mmHg, halts inflation, "
                    "aborts the measurement cycle with an error indication, and rapidly deflates the cuff."
                )
            }
        ]

    elif sec == "4.1":
        vent_time = "2 seconds"
        return [
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Normal Operating Envelope Inflation",
                "test_case": (
                    "Execute standard inflation cycle on a test subject with systolic pressure below 250 mmHg. "
                    "Monitor emergency valve status during inflation."
                ),
                "expected_result": (
                    "Emergency deflation valve remains securely closed throughout nominal inflation below 299 mmHg."
                )
            },
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Immediate Emergency Venting at 299 mmHg Threshold",
                "test_case": (
                    "Apply artificial pressure exceeding 299 mmHg directly to the cuff air port during active inflation. "
                    "Measure the elapsed time until emergency deflation valve triggers."
                ),
                "expected_result": (
                    f"The device immediately triggers the emergency deflation valve and completely vents the cuff "
                    f"within {vent_time}, independent of the main firmware control loop."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Sustained Overpressure Sensor Fault Venting",
                "test_case": (
                    "Simulate an internal sensor fault maintaining cuff pressure above 300 mmHg for 3 consecutive seconds. "
                    "Verify failsafe hardware venting response."
                ),
                "expected_result": (
                    f"Exceeding 300 mmHg for longer than 3 seconds triggers the secondary emergency deflation mechanism, "
                    f"venting the cuff within {vent_time}."
                )
            }
        ]

    elif sec == "4.2":
        deflate_time = "1.5 seconds" if "1.5 seconds" in content else "2 seconds"
        has_e6 = "E6" in content

        cases = [
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Cuff Disconnection Error Code E1",
                "test_case": (
                    "Disconnect the cuff air connector from the unit and press Start to begin a measurement cycle. "
                    "Record screen output and motor activity."
                ),
                "expected_result": (
                    "The device detects cuff leak or absence, halts inflation immediately, and displays error code E1."
                )
            },
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Motion Artifact Detection Error Code E2",
                "test_case": (
                    "Introduce mechanical vibration and arm movement during the oscillometric deflation phase. "
                    "Observe display and firmware response."
                ),
                "expected_result": (
                    "Device detects motion artifact, aborts measurement, displays error code E2, and prompts the user to retry."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Overpressure Condition Error Code E3",
                "test_case": (
                    "Simulate an overpressure condition during inflation. Measure time to auto-deflation and observe display."
                ),
                "expected_result": (
                    f"The device auto-deflates within {deflate_time} and displays error code E3."
                )
            }
        ]
        if has_e6:
            cases.append({
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Bluetooth Sync Failure Error Code E6",
                "test_case": (
                    "Simulate Bluetooth communication failure during sync with companion application. "
                    "Observe subsequent sync status and measurement readiness."
                ),
                "expected_result": (
                    "Device displays error code E6 on sync attempt; device measurement functions remain fully operational."
                )
            })
        return cases

    elif sec == "2.1.1.1":
        low_threshold = "10%" if "10%" in content else "15%"
        cycles = "250" if "250" in content else "300"
        return [
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Typical Battery Endurance Verification",
                "test_case": (
                    f"Perform simulated measurement cycles (3 per day) using standard AA alkaline batteries. "
                    f"Monitor total cycle count before battery depletion."
                ),
                "expected_result": (
                    f"Batteries provide approximately {cycles} measurement cycles under typical use before requiring replacement."
                )
            },
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Low Battery Warning Threshold Activation",
                "test_case": (
                    f"Connect device to an adjustable laboratory DC power supply. Gradually decrease supply voltage "
                    f"to simulate remaining battery capacity reaching {low_threshold}."
                ),
                "expected_result": (
                    f"The device displays the low-battery indicator icon once remaining capacity falls below {low_threshold}."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Mid-Measurement Battery Depletion Error E4",
                "test_case": (
                    "Drop supply voltage below critical operating threshold during active motor inflation. "
                    "Observe device shutdown behavior and display."
                ),
                "expected_result": (
                    "Device safely aborts measurement, vents cuff pressure, and displays error code E4."
                )
            }
        ]

    elif sec == "1.1":
        return [
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Nominal Adult Arm Circumference Verification",
                "test_case": (
                    "Fit the CT-200 cuff to an adult patient simulator with an arm circumference of 28 cm. "
                    "Initiate measurement and verify reading acquisition."
                ),
                "expected_result": (
                    "The device successfully acquires systolic, diastolic, and pulse rate readings without sizing errors."
                )
            },
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Boundary Arm Circumference Limits (22 cm and 42 cm)",
                "test_case": (
                    "Fit the device using appropriate cuff sizes to test cylinders measuring exactly 22 cm (minimum) "
                    "and 42 cm (maximum). Perform measurement cycles."
                ),
                "expected_result": (
                    "Device inflates and measures non-invasively across the full 22-42 cm rated arm circumference range."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Contraindicated Population Safety Guidance",
                "test_case": (
                    "Inspect device documentation and on-screen warnings regarding use on neonates, infants, or pregnant users."
                ),
                "expected_result": (
                    "Manual and packaging clearly designate device as not intended for neonates, infants, or pregnant users."
                )
            }
        ]

    else:
        # Generic 3-scenario generator for any unspecialized section
        return [
            {
                "scenario_type": "NORMAL_OPERATION",
                "scenario": f"Section {sec} - Nominal Operational Verification",
                "test_case": (
                    f"Execute standard verification procedure for Section {sec} ({heading}). "
                    f"Verify device operation conforming to: {content[:140]}..."
                ),
                "expected_result": (
                    f"Observed device behavior satisfies the documented requirements of Section {sec}."
                )
            },
            {
                "scenario_type": "BOUNDARY_CONDITION",
                "scenario": f"Section {sec} - Boundary Specification Compliance",
                "test_case": (
                    f"Apply boundary test limits according to Section {sec} ({heading}). "
                    f"Validate operational tolerances and threshold transitions."
                ),
                "expected_result": (
                    f"Device maintains specified accuracy and performance at boundary limits defined in Section {sec}."
                )
            },
            {
                "scenario_type": "ERROR_HANDLING_OR_LIMIT",
                "scenario": f"Section {sec} - Fault Recovery and Exception Handling",
                "test_case": (
                    f"Simulate out-of-spec condition or invalid input corresponding to Section {sec} ({heading}). "
                    "Verify device safety response."
                ),
                "expected_result": (
                    f"Device safely manages fault condition without patient hazard or lockup as required by Section {sec}."
                )
            }
        ]


def build_llm_prompt(items: List[SelectionItem], target_count: int) -> str:
    sections_text = ""
    for idx, item in enumerate(items, 1):
        sections_text += f"""
--- Pinned Item {idx} ---
Section Number: {item.section_number}
Heading: {item.heading}
Version: {item.version}
Requirement Text:
{item.pinned_content}
"""

    return f"""
You are a senior medical device Quality Assurance (QA) engineer.
Given the following pinned requirements from the CardioTrack CT-200 Technical Manual:
{sections_text}

Generate exactly {target_count} GENUINELY DISTINCT QA test cases.
Requirements for test cases:
1. Cover different scenario types:
   - NORMAL_OPERATION (nominal baseline performance)
   - BOUNDARY_CONDITION (numerical thresholds, step sizes, minimum/maximum values)
   - ERROR_HANDLING_OR_LIMIT (maximum limits, safety valves, error codes, aborts)
2. DO NOT create duplicate or near-identical test cases. Every case must have distinct test steps and an expected result.
3. Every test case must be grounded strictly in the supplied requirement text. Do NOT invent unsupported features.
4. If multiple sections are provided, distribute the test cases across them. If only one section is provided, generate distinct scenarios (normal, boundary, error) for that single section.

Return a JSON array where each object has:
- section_number: string matching the relevant pinned section
- scenario_type: string ("NORMAL_OPERATION", "BOUNDARY_CONDITION", or "ERROR_HANDLING_OR_LIMIT")
- scenario: concise title describing the test condition (e.g. "Section 3.2 - Boundary Step Increment")
- test_case: detailed step-by-step test procedure / scenario (minimum 15 words)
- expected_result: concrete required device behavior matching the requirement text (minimum 10 words)
"""


def call_gemini_api(prompt: str) -> Optional[List[Dict[str, Any]]]:
    """
    Call Gemini using primary and candidate fallback models with bounded retry.
    Returns parsed list of test case dictionaries, or None on failure.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY is not configured; using rule-based fallback.")
        return None

    # Skip external calls if hermetic test mode is explicitly requested
    if os.getenv("FORCE_FALLBACK_TESTS") == "1":
        return None

    from google import genai

    all_models = [PRIMARY_MODEL] + [m for m in FALLBACK_MODELS if m != PRIMARY_MODEL]

    for model_name in all_models:
        for attempt in range(2):
            try:
                # Do not set manually short deadline that triggers 400 or 504
                client = genai.Client(api_key=api_key)

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "section_number": {"type": "STRING"},
                                    "scenario_type": {"type": "STRING"},
                                    "scenario": {"type": "STRING"},
                                    "test_case": {"type": "STRING"},
                                    "expected_result": {"type": "STRING"}
                                },
                                "required": ["scenario", "test_case", "expected_result"]
                            }
                        }
                    }
                )

                if not response or not response.text:
                    continue

                data = json.loads(response.text)
                if isinstance(data, list) and len(data) > 0:
                    # Validate basic schema structure
                    valid = True
                    for item in data:
                        if not isinstance(item.get("test_case"), str) or len(item["test_case"].strip()) < 10:
                            valid = False
                            break
                        if not isinstance(item.get("expected_result"), str) or len(item["expected_result"].strip()) < 5:
                            valid = False
                            break
                    if valid:
                        logger.info(f"Successfully generated {len(data)} test cases using model '{model_name}'.")
                        return data

            except Exception as e:
                err_str = str(e)
                # If temporary 503/429/timeout, delay and retry or switch model
                is_temp = any(code in err_str for code in ("503", "429", "504", "500", "DEADLINE_EXCEEDED"))
                if is_temp:
                    time.sleep(2)
                else:
                    break

    return None


def generate_tests_for_selection(
    selection: Selection,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    Generate 3-5 genuinely distinct QA test cases from a saved version-pinned selection.
    Ensures zero duplicate test cases, covers distinct scenarios (normal, boundary, error),
    respects duplicate generation policy, and guarantees exact source traceability.
    """
    store = TestCaseStore()
    existing_tests = store.get_by_selection_id(selection.id)

    # Return cached tests if already generated and force_regenerate is False
    if existing_tests and not force_regenerate:
        return {
            "status": "cached",
            "message": "Returned existing generated test cases for this selection (use force_regenerate=true to regenerate).",
            "selection_id": selection.id,
            "generation_method": existing_tests[0].get("generation_method", "unknown"),
            "total_tests": len(existing_tests),
            "tests": existing_tests
        }

    items = selection.items
    if not items:
        return {
            "status": "empty",
            "message": "Selection has no pinned sections.",
            "selection_id": selection.id,
            "total_tests": 0,
            "tests": []
        }

    target_count = min(max(len(items), 3), 5)
    item_by_sec = {str(item.section_number).strip(): item for item in items}
    default_item = items[0]

    # Attempt LLM generation
    prompt = build_llm_prompt(items, target_count)
    llm_results = call_gemini_api(prompt)

    generated_cases: List[Dict[str, Any]] = []
    seen_steps = set()

    if llm_results:
        method = PRIMARY_MODEL
        for raw in llm_results:
            tc_text = raw.get("test_case", "").strip()
            norm = normalize_for_dedup(tc_text)
            if norm in seen_steps:
                continue
            seen_steps.add(norm)

            raw_section = raw.get("section_number")
            if raw_section is None or not str(raw_section).strip():
                # With one pinned item the source is unambiguous; with several,
                # do not invent provenance when the model omits the section.
                if len(items) == 1:
                    matching_item = items[0]
                else:
                    logger.warning("Skipping generated case without section_number for multi-item selection.")
                    continue
            else:
                sec_num = str(raw_section).strip()
                matching_item = item_by_sec.get(sec_num)
                if matching_item is None:
                    logger.warning("Skipping generated case with unpinned section_number: %s", sec_num)
                    continue

            case_dict = {
                "test_id": str(uuid.uuid4())[:8],
                "selection_id": selection.id,
                "source_node_id": matching_item.section_id,
                "logical_id": matching_item.logical_id or matching_item.section_number,
                "section_number": matching_item.section_number,
                "source_heading": matching_item.heading,
                "source_version": matching_item.version,
                "source_hash": matching_item.pinned_hash,
                "scenario": raw.get("scenario") or f"Section {matching_item.section_number} Verification",
                "scenario_type": raw.get("scenario_type") or "SPECIFICATION_CHECK",
                "test_case": tc_text,
                "expected_result": raw.get("expected_result", "").strip(),
                "generation_method": method,
                "created_at": datetime.utcnow().isoformat()
            }
            generated_cases.append(case_dict)
            if len(generated_cases) >= target_count:
                break

    # If LLM failed, returned insufficient cases, or was unavailable -> use domain fallback
    if len(generated_cases) < 3:
        method = "rule-based-fallback"
        generated_cases = []
        seen_steps.clear()

        # Keep each fallback scenario paired with the pinned item that produced it.
        # Interleave scenarios across sections so the first cases cover different
        # pinned sections when the selection contains multiple items.
        candidate_cases = []
        if len(items) == 1:
            candidate_cases.extend(
                (items[0], cand)
                for cand in get_distinct_fallback_cases_for_item(items[0])
            )
        else:
            per_item_cases = [
                (item, get_distinct_fallback_cases_for_item(item))
                for item in items
            ]
            max_scenarios = max(
                (len(cases) for _, cases in per_item_cases),
                default=0,
            )
            for scenario_index in range(max_scenarios):
                for item, cases in per_item_cases:
                    if scenario_index < len(cases):
                        candidate_cases.append((item, cases[scenario_index]))

        for matching_item, cand in candidate_cases:
            tc_text = cand["test_case"].strip()
            norm = normalize_for_dedup(tc_text)
            if norm in seen_steps:
                continue
            seen_steps.add(norm)

            case_dict = {
                "test_id": str(uuid.uuid4())[:8],
                "selection_id": selection.id,
                "source_node_id": matching_item.section_id,
                "logical_id": matching_item.logical_id or matching_item.section_number,
                "section_number": matching_item.section_number,
                "source_heading": matching_item.heading,
                "source_version": matching_item.version,
                "source_hash": matching_item.pinned_hash,
                "scenario": cand.get("scenario"),
                "scenario_type": cand.get("scenario_type"),
                "test_case": tc_text,
                "expected_result": cand.get("expected_result", "").strip(),
                "generation_method": method,
                "created_at": datetime.utcnow().isoformat()
            }
            generated_cases.append(case_dict)
            if len(generated_cases) >= target_count:
                break

    # Save to store, replacing any previous cases for this selection (deduplicated)
    saved_cases = store.save_cases_for_selection(selection.id, generated_cases)

    return {
        "status": "generated",
        "message": f"Successfully generated {len(saved_cases)} distinct QA test cases.",
        "selection_id": selection.id,
        "generation_method": saved_cases[0]["generation_method"] if saved_cases else "unknown",
        "total_tests": len(saved_cases),
        "tests": saved_cases
    }
