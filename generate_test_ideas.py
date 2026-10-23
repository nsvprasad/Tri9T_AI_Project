
import os
import sys
import json
import time
import hashlib
from pathlib import Path

# Load packages installed in the project folder on D:
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))

from google import genai
from pydantic import BaseModel, Field, ValidationError


CHANGES_FILE = PROJECT_DIR / "change_records.json"
OUTPUT_FILE = PROJECT_DIR / "test_ideas.json"
MODEL_NAME = "gemini-3.8-flash"


class QATestIdea(BaseModel):
    section_number: str
    source_heading: str
    source_version: str
    source_hash: str
    test_idea: str = Field(min_length=10)
    expected_result: str = Field(min_length=5)


def calculate_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fallback_idea(change):
    """Create a clearly labelled rule-based fallback idea."""
    section = str(change["section_number"])
    heading = change.get("section_title", "Unknown section")
    content = change.get("new_content") or ""

    return {
        "test_idea": (
            f"[RULE-BASED FALLBACK] Verify that section {section} "
            f"({heading}) is implemented according to the updated manual."
        ),
        "expected_result": (
            "Observed behavior conforms to the documented requirements: "
            + content[:500]
        )
    }


def generate_with_gemini(client, prompt):
    """Try Gemini up to three times for temporary API failures."""
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "test_idea": {"type": "STRING"},
                            "expected_result": {"type": "STRING"}
                        },
                        "required": ["test_idea", "expected_result"]
                    }
                }
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            result = json.loads(response.text)

            if not isinstance(result.get("test_idea"), str):
                raise ValueError("Missing test_idea in Gemini response.")
            if not isinstance(result.get("expected_result"), str):
                raise ValueError("Missing expected_result in Gemini response.")

            return result

        except Exception as error:
            message = str(error)
            temporary_error = any(
                code in message for code in ("429", "500", "502", "503", "504")
            )

            if not temporary_error or attempt == 2:
                print(f"Gemini attempt {attempt + 1} failed: {message}")
                break

            delay = 3 * (attempt + 1)
            print(
                f"Temporary Gemini error. Retrying in {delay} seconds..."
            )
            time.sleep(delay)

    return None


def main():
    if not CHANGES_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {CHANGES_FILE.name} in {PROJECT_DIR}"
        )

    with open(CHANGES_FILE, "r", encoding="utf-8") as file:
        changes = json.load(file)

    if not isinstance(changes, list) or not changes:
        raise ValueError("change_records.json must contain a non-empty list.")

    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else None

    if client is None:
        print("GEMINI_API_KEY is not configured; using fallback ideas.")

    ideas = []
    llm_count = 0
    fallback_count = 0

    for change in changes:
        section = str(change.get("section_number", "Unknown"))
        heading = change.get("section_title", "Unknown section")
        version = change.get("version_new", "v2")
        content = change.get("new_content") or ""

        if not content.strip():
            print(f"Skipping section {section}: no new content.")
            continue

        source_hash = calculate_hash(content)
        result = None

        if client is not None:
            prompt = f"""
You are a careful QA engineer reviewing a technical device manual.

Create exactly one actionable QA test idea based only on the supplied
manual change. Do not invent requirements, device capabilities, or limits.

Return JSON with:
- test_idea: a concise, actionable verification procedure
- expected_result: the result required by the new manual content

Section: {section}
Heading: {heading}
Old version: {change.get("version_old", "unknown")}
New version: {version}
Change type: {change.get("change_type", "unknown")}

Previous content:
{change.get("old_content") or "No previous content"}

New content:
{content}
"""
            print(f"Generating QA idea for section {section}...")

            result = generate_with_gemini(client, prompt)

        if result is None:
            print(f"Using rule-based fallback for section {section}.")
            result = fallback_idea(change)
            fallback_count += 1
        else:
            llm_count += 1

        # Source metadata is set by Python, not by the LLM.
        idea = QATestIdea(
            section_number=section,
            source_heading=heading,
            source_version=version,
            source_hash=source_hash,
            test_idea=result["test_idea"],
            expected_result=result["expected_result"]
        )
        ideas.append(idea.model_dump())

    if not ideas:
        raise ValueError("No QA test ideas were produced.")

    # Validate the complete output before replacing the existing file.
    validated = [QATestIdea(**item).model_dump() for item in ideas]

    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(validated, file, indent=4, ensure_ascii=False)

    temp_file.replace(OUTPUT_FILE)

    print("\nGeneration complete.")
    print(f"Total QA ideas: {len(validated)}")
    print(f"LLM-generated: {llm_count}")
    print(f"Rule-based fallback: {fallback_count}")
    print(f"Saved to: {OUTPUT_FILE.name}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        print(f"Generation failed: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"Unexpected error: {error}")
        sys.exit(1)


