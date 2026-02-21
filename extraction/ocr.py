import requests
import base64
import json
import re
import os
import hashlib
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL           = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-haiku-4-5-20251001"

# ── Prompts for each proof type ─────────────────────────────────────────────

PROMPTS = {
    "job": """Extract job details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "job_title":        "...",
  "company":          "...",
  "employment_type":  "...",
  "date_range":       "...",
  "location":         "...",
  "job_category":     "...",
  "confidence": {
    "job_title":       0.0,
    "company":         0.0,
    "employment_type": 0.0,
    "date_range":      0.0,
    "location":        0.0,
    "job_category":    0.0
  }
}
Rules:
- employment_type must be one of: full-time, part-time, intern, contributor, contract
- job_category examples: Tech Support, Design, Engineering, Operations, Marketing, Community
- date_range format: "Month Year - Month Year" or "Month Year - Present"
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only""",

    "certificate": """Extract certificate/training details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "certificate_title": "...",
  "issuer":            "...",
  "completion_date":   "...",
  "credential_type":   "...",
  "program_category":  "...",
  "confidence": {
    "certificate_title": 0.0,
    "issuer":            0.0,
    "completion_date":   0.0,
    "credential_type":   0.0,
    "program_category":  0.0
  }
}

Rules:
- credential_type must be one of: Course, Bootcamp, Workshop, Award, Certification
- program_category examples: Blockchain Dev, UI/UX, Data Science, Marketing, DevOps
- completion_date format: "Month Year"
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only""",

    "skill": """Extract skill/competency details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "skill_name":       "...",
  "skill_category":   "...",
  "proficiency_level": "...",
  "evidence_type":    "...",
  "confidence": {
    "skill_name":       0.0,
    "skill_category":   0.0,
    "proficiency_level": 0.0,
    "evidence_type":    0.0
  }
}
Rules:
- skill_category examples: Programming, Design, Management, Communication, Technical Writing
- proficiency_level must be one of: Beginner, Intermediate, Advanced, Expert (use null if not clear)
- evidence_type examples: GitHub Activity, Portfolio, Test Result, Certificate, Work Sample
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only""",

    "milestone": """Extract career milestone details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "milestone_type":    "...",
  "issuer":            "...",
  "date":              "...",
  "milestone_summary": "...",
  "confidence": {
    "milestone_type":    0.0,
    "issuer":            0.0,
    "date":              0.0,
    "milestone_summary": 0.0
  }
}

Rules:
- milestone_type must be one of: Promotion, Award, Recognition, Key Result, Achievement
- date format: "Month Year"
- milestone_summary should be generic, 1-2 sentences max
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only""",

    "contribution": """Extract community contribution details from this document image.
Return ONLY a valid JSON object with exactly these fields:

{
  "contribution_type": "...",
  "platform_name":     "...",
  "date":              "...",
  "title":             "...",
  "url":               "...",
  "confidence": {
    "contribution_type": 0.0,
    "platform_name":     0.0,
    "date":              0.0,
    "title":             0.0,
    "url":               0.0
  }
}
Rules:
- contribution_type must be one of: Talk, Article, Open Source, Community Role, Tutorial, Workshop
- platform_name examples: GitHub, Medium, Dev.to, YouTube, Conference Name
- date format: "Month Year"
- url should be the link if visible in the image
- Use null for any field you cannot find
- confidence is a float from 0.0 (uncertain) to 1.0 (certain) per field
- No markdown, no explanation, no extra keys — raw JSON only"""
}


# ── In-memory cache ─────────────────────────────────────────────────────────

_CACHE = {}

def _image_hash(image_bytes):
    """Generate a stable hash for the image to use as cache key."""
    return hashlib.sha256(image_bytes).hexdigest()


def cached(func):
    """Cache decorator that stores results keyed by image hash."""
    @wraps(func)
    def wrapper(image_bytes, *args, **kwargs):
        cache_key = _image_hash(image_bytes)
        
        if cache_key in _CACHE:
            result = _CACHE[cache_key].copy()
            result["cache_hit"] = True
            return result
        
        result = func(image_bytes, *args, **kwargs)
        result["cache_hit"] = False
        _CACHE[cache_key] = result.copy()
        return result
    
    return wrapper

# ── Exceptions ──────────────────────────────────────────────────────────────

class ExtractionError(Exception):
    """Raised when the API call or JSON parsing fails."""
    pass


class TransientAPIError(ExtractionError):
    """Raised for retryable network/API errors."""
    pass


class PermanentAPIError(ExtractionError):
    """Raised for non-retryable errors (auth, invalid request, etc)."""
    pass


# ── Helper functions ────────────────────────────────────────────────────────

def _resolve_mime_type(mime_type, filename=""):
    """Ensure mime_type is one Claude accepts, infer from filename if needed."""
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}
    if mime_type in allowed:
        return mime_type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "gif":  "image/gif",
        "webp": "image/webp",
        "pdf":  "application/pdf",
    }.get(ext, "image/jpeg")


def _build_payload(b64_data, mime_type, prompt):
    """Build API payload - handles both images and PDFs."""
    content_item = {
        "type": "document" if mime_type == "application/pdf" else "image",
        "source": {
            "type":       "base64",
            "media_type": mime_type,
            "data":       b64_data,
        }
    }
    
    return {
        "model":      MODEL,
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                content_item,
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
        }]
    }
def _parse_response(raw):
    """Strip any accidental markdown fences then parse JSON."""
    cleaned = re.sub(r"^```json|^```|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise PermanentAPIError(f"Model returned invalid JSON: {e}\nRaw output: {raw}")


def _low_confidence_fields(result, threshold=0.5):
    """Return field names whose confidence is below threshold."""
    scores = result.get("confidence") or {}
    return [field for field, score in scores.items() if (score or 0) < threshold]


# ── Main extraction function ────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TransientAPIError),
    reraise=True
)
def _call_anthropic_api(b64_data, mime_type, prompt):
    """
    Make the actual API call with retry logic.
    Retries only on transient errors (timeouts, 5xx, rate limits).
    """
    try:
        response = requests.post(
            API_URL,
            headers={
                "x-api-key":          ANTHROPIC_API_KEY,
                "anthropic-version":  "2023-06-01",
                "content-type":       "application/json",
            },
            json=_build_payload(b64_data, mime_type, prompt),
            timeout=30,
        )
        
        # Handle different error types appropriately
        if response.status_code == 429:
            raise TransientAPIError(f"Rate limited: {response.text}")
        
        if 500 <= response.status_code < 600:
            raise TransientAPIError(f"Server error {response.status_code}: {response.text}")
        
        if response.status_code == 401:
            raise PermanentAPIError(f"Authentication failed: {response.text}")
        
        if response.status_code == 400:
            raise PermanentAPIError(f"Invalid request: {response.text}")
        
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise TransientAPIError("Request to Anthropic API timed out")
    
    except requests.exceptions.ConnectionError as e:
        raise TransientAPIError(f"Connection error: {e}")
    
    except requests.exceptions.RequestException as e:
        raise PermanentAPIError(f"Request error: {e}")

@cached
def extract_proof(file_bytes, proof_type, mime_type="image/jpeg", filename=""):
    """
    Send a document (image or PDF) to Claude and return structured extraction.
    Results are cached by file hash to avoid redundant API calls.

    Args:
        file_bytes: Raw file bytes (image or PDF)
        proof_type: One of: job, certificate, skill, milestone, contribution
        mime_type: MIME type from the upload (will be validated/corrected)
        filename: Original filename, used as fallback for mime type detection

    Returns a dict with extracted fields specific to proof_type, plus:
      confidence, needs_review, low_confidence_fields, cache_hit

    Raises:
        PermanentAPIError: For auth failures, invalid requests, parse errors
        TransientAPIError: For network issues, timeouts (after 3 retries)
    """
    if not ANTHROPIC_API_KEY:
        raise PermanentAPIError("ANTHROPIC_API_KEY environment variable is not set.")

    if proof_type not in PROMPTS:
        raise PermanentAPIError(
            f"Invalid proof_type '{proof_type}'. Must be one of: {', '.join(PROMPTS.keys())}"
        )

    mime_type = _resolve_mime_type(mime_type, filename)
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    prompt = PROMPTS[proof_type]
    api_response = _call_anthropic_api(b64, mime_type, prompt)

    raw_text = api_response["content"][0]["text"]
    result   = _parse_response(raw_text)

    low_fields                      = _low_confidence_fields(result)
    result["needs_review"]          = len(low_fields) > 0
    result["low_confidence_fields"] = low_fields
    result["proof_type"]            = proof_type

    return result


def extract_job(image_bytes, mime_type="image/jpeg", filename=""):
    """Legacy function name - calls extract_proof with proof_type='job'."""
    return extract_proof(image_bytes, "job", mime_type, filename)


def clear_cache():
    """Clear the extraction cache."""
    global _CACHE
    _CACHE.clear()


def get_cache_stats():
    """Return cache statistics."""
    return {
        "cached_entries": len(_CACHE),
        "cache_size_bytes": sum(
            len(json.dumps(v).encode()) for v in _CACHE.values()
        )
    }
