import hashlib
import re


def generate_hash(data):

    raw = "|".join(str(v) for v in data.values())

    return hashlib.sha256(raw.encode()).hexdigest()

import re


def extract_certificate(text):

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    data = {
        "certificate_title": "Unknown",
        "recipient_name": "Unknown",
        "issuer": "Unknown",
        "issuer_signatory": "Unknown",
        "issuer_title": "Unknown",
        "issue_date": "Unknown",
        "credential_type": "Unknown",
        "verification_url": "Unknown",
        "program_duration": "Unknown"
    }

    full_text = " ".join(lines)


    # issuer detection
    if "freecodecamp" in full_text.lower():
        data["issuer"] = "freeCodeCamp"


    # recipient name
    for i, line in enumerate(lines):

        if "certifies that" in line.lower():

            if i + 1 < len(lines):
                data["recipient_name"] = lines[i + 1]
                break


    # certificate title
    for i, line in enumerate(lines):

        if "successfully completed" in line.lower():

            if i + 1 < len(lines):
                data["certificate_title"] = lines[i + 1]
                break


    # credential type
    match = re.search(
        r"(Developer Certification)",
        full_text,
        re.IGNORECASE
    )

    if match:
        data["credential_type"] = match.group(1)


    # issue date
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
        full_text
    )

    if match:
        data["issue_date"] = match.group(0)


    # signatory
    match = re.search(
        r"(Quincy Larson)",
        full_text
    )

    if match:
        data["issuer_signatory"] = match.group(1)


    # signatory title
    match = re.search(
        r"(Executive Director)",
        full_text
    )

    if match:
        data["issuer_title"] = match.group(1)


    # verification url
    match = re.search(
        r"https://[^\s]+",
        full_text
    )

    if match:
        data["verification_url"] = match.group(0)


    # program duration
    match = re.search(
        r"(\d+)\s+hours",
        full_text
    )

    if match:
        data["program_duration"] = match.group(1) + " hours"


    return data


import re
from typing import Optional

# ── Shared constants ──────────────────────────────────────────────────────────

MONTH = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
YEAR  = r'\d{4}'
DATE  = rf'(?:{MONTH}\s+)?{YEAR}'
DATE_RANGE_PAT = re.compile(
    rf'({DATE})\s*[-–]\s*({DATE}|Present)', re.IGNORECASE
)

EMPLOYMENT_TYPES = [
    "full-time", "part-time", "contract", "freelance",
    "internship", "seasonal", "self-employed", "remote"
]

LINKEDIN_SEPARATOR = r'\s*[·•]\s*'


# ── Schema detector ───────────────────────────────────────────────────────────

def detect_schema(text: str) -> str:
    """
    Returns one of: 'linkedin' | 'resume_block' | 'generic'

    LinkedIn card signals:
      - · separator appears in the first ~200 chars (company · type line)
      - duration annotation like "2 yrs 3 mos"
      - known employment type on the company line

    Resume block signals:
      - First non-empty line is ALL CAPS or TITLE CASE with no · separator
      - Date range appears on its own line or inline with location
      - Bullet-pointed responsibilities follow

    Generic: everything else.
    """
    head = text[:300]
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if not lines:
        return "generic"

    first = lines[0]

    # Strong LinkedIn signals
    has_midot       = bool(re.search(r'[·•]', head))
    has_duration    = bool(re.search(r'\d+\s+yrs?\b|\d+\s+mos?\b', text))
    has_type_on_l2  = (
        len(lines) > 1 and
        any(t in lines[1].lower() for t in EMPLOYMENT_TYPES)
    )

    if has_midot and (has_duration or has_type_on_l2):
        return "linkedin"

    # Resume block signals
    is_caps_header  = first.isupper() or re.match(r'^[A-Z][A-Z\s\d\.\-]{8,}$', first)
    has_bullet      = bool(re.search(r'^\s*[•●\-\*]', text, re.MULTILINE))
    date_on_line1   = bool(DATE_RANGE_PAT.search(first))

    if is_caps_header and (has_bullet or date_on_line1):
        return "resume_block"

    # Fallback: resume block without bullets, or plain text
    if is_caps_header and DATE_RANGE_PAT.search(text):
        return "resume_block"

    return "generic"


# ── LinkedIn extractor ────────────────────────────────────────────────────────

def extract_linkedin_job(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # job_title: always first line
    job_title = lines[0] if lines else None

    # company + employment_type: split on · separator
    company = None
    employment_type = None

    for line in lines[1:]:
        parts = re.split(LINKEDIN_SEPARATOR, line)
        for i, p in enumerate(parts):
            if any(t in p.lower() for t in EMPLOYMENT_TYPES):
                employment_type = p.strip()
                remaining = [parts[j] for j in range(len(parts)) if j != i]
                if remaining:
                    company = remaining[0].strip()
                break
        if company:
            break

    # date_range: match before any duration annotation
    date_range = None
    date_line_idx = None
    for i, line in enumerate(lines):
        m = DATE_RANGE_PAT.search(line)
        if m:
            date_range = f"{m.group(1)} - {m.group(2)}"
            date_line_idx = i
            break

    # location: · separated line immediately after the date line
    location = None
    if date_line_idx is not None and date_line_idx + 1 < len(lines):
        candidate = lines[date_line_idx + 1]
        if '·' in candidate and len(candidate) < 60:
            location = candidate

    return {
        "schema":          "linkedin",
        "job_title":       job_title,
        "company":         company,
        "employment_type": employment_type,
        "date_range":      date_range,
        "location":        location,
    }


# ── Generic extractor ─────────────────────────────────────────────────────────

def extract_generic_job(text: str) -> dict:
    """
    Best-effort extraction for plain text with no reliable structural signals.
    Prioritises recall over precision — returns whatever it can find.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # job_title: first line that looks like a title (not a date, not all caps noise)
    date_re = re.compile(r'\b\d{4}\b')
    job_title = next(
        (l for l in lines if not date_re.search(l) and len(l) < 80),
        lines[0] if lines else None
    )

    # company: look for org-name patterns — capitalised short phrases
    company = None
    for line in lines:
        if re.match(r'^[A-Z][a-zA-Z\s&\.,\-]{2,40}$', line) and line != job_title:
            company = line
            break

    # employment_type: keyword scan
    employment_type = None
    for token in EMPLOYMENT_TYPES:
        if token in text.lower():
            employment_type = token
            break

    # date_range
    date_range = None
    m = DATE_RANGE_PAT.search(text)
    if m:
        date_range = f"{m.group(1)} - {m.group(2)}"

    return {
        "schema":          "generic",
        "job_title":       job_title,
        "company":         company,
        "employment_type": employment_type,
        "date_range":      date_range,
    }

# ── Resume block extractor ────────────────────────────────────────────────────

def extract_resume_block_job(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # company: first line, strip trailing location/date noise
    # e.g. "BITCOIN PIZZA DAY FEST 2025. Pan-Africa (Remote)"
    raw_company = lines[0] if lines else ""
    company = re.sub(r'\s*[\(\[].*?[\)\]]', '', raw_company)  # drop (Remote)
    company = re.sub(r'\s*\d{4}[\s\S]*$', '', company).strip()  # drop year+

    # date_range: often on line 1 inline, or on its own line
    date_range = None
    date_line_idx = None

    # First check line 0 itself (inline date like "March - June 2025")
    m = DATE_RANGE_PAT.search(lines[0]) if lines else None
    if m:
        date_range = f"{m.group(1)} - {m.group(2)}"
        date_line_idx = 0
    else:
        for i, line in enumerate(lines):
            m = DATE_RANGE_PAT.search(line)
            if m:
                date_range = f"{m.group(1)} - {m.group(2)}"
                date_line_idx = i
                break

    # job_title: first sentence-case line that isn't the company,
    # isn't a date line, and isn't a location/keyword line
    date_re   = re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b')
    bullet_re = re.compile(r'^[•●\-\*]')
    job_title = None

    for i, line in enumerate(lines[1:], start=1):
        if i == date_line_idx:
            continue
        if bullet_re.match(line):
            break                          # hit responsibilities, stop looking
        if date_re.search(line[:20]):
            continue                       # skip pure date lines
        if line.isupper():
            continue                       # skip another caps header
        if any(t in line.lower() for t in EMPLOYMENT_TYPES) and len(line) < 30:
            continue                       # skip standalone type tags
        job_title = line
        break

    # employment_type: keyword scan across full text
    employment_type = None
    for token in EMPLOYMENT_TYPES:
        if token in text.lower():
            employment_type = token
            break

    return {
        "schema":          "resume_block",
        "job_title":       job_title,
        "company":         company,
        "employment_type": employment_type,
        "date_range":      date_range,
    }


import requests
import base64
import json
import re
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL           = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-haiku-4-5-20251001"

PROMPT = """Extract job details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "job_title":        "...",
  "company":          "...",
  "employment_type":  "...",
  "date_range":       "...",
  "location":         "...",
  "confidence": {
    "job_title":       0.0,
    "company":         0.0,
    "employment_type": 0.0,
    "date_range":      0.0,
    "location":        0.0
  }
}

Rules:
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only"""


class ExtractionError(Exception):
    """Raised when the API call or JSON parsing fails."""
    pass


def _build_payload(b64_image: str, mime_type: str) -> dict:
    return {
        "model":      MODEL,
        "max_tokens": 512,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type":       "base64",
                        "media_type": mime_type,
                        "data":       b64_image,
                    }
                },
                {
                    "type": "text",
                    "text": PROMPT,
                }
            ]
        }]
    }


def _parse_response(raw: str) -> dict:
    """Strip any accidental markdown fences then parse JSON."""
    cleaned = re.sub(r"^```json|^```|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Model returned invalid JSON: {e}\nRaw output: {raw}")


def _low_confidence_fields(result: dict, threshold: float = 0.5) -> list[str]:
    """Return field names whose confidence is below threshold."""
    scores = result.get("confidence") or {}
    return [field for field, score in scores.items() if (score or 0) < threshold]



def extract_job(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Send an image to Claude and return structured job extraction.

    Returns a dict with keys:
      job_title, company, employment_type, date_range, location,
      confidence, needs_review, low_confidence_fields

    Raises ExtractionError on API or parse failure.
    """
    if not ANTHROPIC_API_KEY:
        raise ExtractionError("ANTHROPIC_API_KEY environment variable is not set.")

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        response = requests.post(
            API_URL,
            headers={
                "x-api-key":          ANTHROPIC_API_KEY,
                "anthropic-version":  "2023-06-01",
                "content-type":       "application/json",
            },
            json=_build_payload(b64, mime_type),
            timeout=30,
        )
        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise ExtractionError("Request to Anthropic API timed out.")
    except requests.exceptions.HTTPError as e:
        raise ExtractionError(f"Anthropic API returned {response.status_code}: {e} {response.text}")
    except requests.exceptions.RequestException as e:
        raise ExtractionError(f"Network error: {e}")

    raw_text = response.json()["content"][0]["text"]
    result   = _parse_response(raw_text)

    # Annotate with review flag so the caller can route accordingly
    low_fields            = _low_confidence_fields(result)
    result["needs_review"]          = len(low_fields) > 0
    result["low_confidence_fields"] = low_fields

    return result

def extract_skill(text):

    return {

        "skill_name": first_line(text),

        "category": keyword(
        text,
        ["Programming", "Design"]),

        "level": keyword(
        text,
        ["Beginner", "Intermediate", "Advanced"])
    }


def extract_milestone(text):

    return {

        "milestone_type": keyword(
        text,
        ["Award", "Promotion"]),

        "issuer": find(text, r"by (.+)"),

        "date": find(text, r"\b\d{4}\b"),

        "summary": text[:200]
    }


def first_line(text):

    return text.strip().split("\n")[0]

def find(text, pattern):

    try:

        match = re.search(pattern, text)

        if not match:
            return "Unknown"

        return match.group(1) if match.lastindex else match.group(0)

    except Exception:

        return "Unknown"




def keyword(text, words):

    for word in words:

        if word.lower() in text.lower():

            return word

    return "Unknown"

