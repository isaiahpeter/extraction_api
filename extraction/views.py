from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .ocr import extract_proof, PermanentAPIError, TransientAPIError
import hashlib
import json
import os

def hash_result(data: dict) -> str:
    """Generate validation hash from extraction result."""
    clean = {k: v for k, v in data.items() 
             if k not in ["needs_review", "low_confidence_fields", "confidence", "cache_hit", "proof_type"]}
    serialized = json.dumps(clean, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


class ExtractView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    @extend_schema(
        summary="Extract structured data from proof documents",
        description="""
        Upload a document (image or PDF) and extract structured fields based on proof type.

        Supported proof types:
        - **job**: Job history/work experience
        - **certificate**: Certificates and training completions
        - **skill**: Skills and competencies
        - **milestone**: Career milestones (promotions, awards, achievements)
        - **contribution**: Community contributions (talks, articles, open source)

        The API returns extracted fields with confidence scores. Documents with low confidence
        are flagged for manual review.
        """,
        parameters=[
            OpenApiParameter(
                name='proof_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Type of proof document',
                required=True,
                enum=['job', 'certificate', 'skill', 'milestone', 'contribution']
            ),
            OpenApiParameter(
                name='file',
                type=OpenApiTypes.BINARY,
                location=OpenApiParameter.QUERY,
                description='Document file (JPG, PNG, PDF)',
                required=True
            ),
        ],
        examples=[
            OpenApiExample(
                'Job History Success',
                value={
                    "proof_type": "job",
                    "extracted_data": {
                        "job_title": "Community Lead",
                        "company": "EkoLance",
                        "employment_type": "part-time",
                        "date_range": "Nov 2022 - Jan 2025",
                        "location": "Germany, Remote",
                        "job_category": "Community",
                        "confidence": {
                            "job_title": 0.95,
                            "company": 0.95,
                            "employment_type": 0.95,
                            "date_range": 0.95,
                            "location": 0.95,
                            "job_category": 0.9
                        },
                        "needs_review": False,
                        "low_confidence_fields": []
                    },
                    "needs_review": False,
                    "flagged_fields": [],
                    "validation_hash": "3a9244f13222c83cc96736f91b104d0eeaf2d0db967120f336f074bac766cc5b",
                    "cached": False
                },
                response_only=True,
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "proof_type": {"type": "string"},
                    "extracted_data": {"type": "object"},
                    "needs_review": {"type": "boolean"},
                    "flagged_fields": {"type": "array"},
                    "validation_hash": {"type": "string", "nullable": True},
                    "cached": {"type": "boolean"}
                }
            },
            400: {"description": "Invalid request (missing file/proof_type, or permanent API error)"},
            503: {"description": "Service temporarily unavailable (transient API error after retries)"}
        }
    )
    def post(self, request):
        uploaded_file = request.FILES.get("file")
        proof_type = request.data.get("proof_type")

        if not uploaded_file:
            return Response({"error": "no file uploaded"}, status=400)
        
        if not proof_type:
            return Response({"error": "proof_type is required"}, status=400)

        try:
            result = extract_proof(
                uploaded_file.read(),
                proof_type,
                uploaded_file.content_type,
                uploaded_file.name
            )
        except PermanentAPIError as e:
            return Response({"error": str(e)}, status=400)
        
        except TransientAPIError as e:
            return Response({"error": f"Service temporarily unavailable: {e}"}, status=503)

        # Only hash if extraction is confident enough to be trusted
        v_hash = hash_result(result) if not result["needs_review"] else None

        return Response({
            "proof_type":      proof_type,
            "extracted_data":  result,
            "needs_review":    result["needs_review"],
            "flagged_fields":  result["low_confidence_fields"],
            "validation_hash": v_hash,
            "cached":          result.get("cache_hit", False),
        })
class DebugView(APIView):
    def get(self, request):
        return Response({
            "api_key_exists": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "api_key_prefix": os.environ.get("ANTHROPIC_API_KEY", "")[:10] + "..." if os.environ.get("ANTHROPIC_API_KEY") else "NOT SET"
        })
