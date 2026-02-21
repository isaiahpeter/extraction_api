import os
import uuid
import requests
from datetime import datetime
from django.conf import settings


def upload_file(file_content: bytes, file_name: str, content_type: str = None) -> dict:
    """
    Upload file to Supabase Storage using REST API
    """

    try:
        file_extension = os.path.splitext(file_name)[1]
        unique_name = f"{uuid.uuid4()}{file_extension}"
        file_path = f"uploads/{datetime.utcnow().strftime('%Y/%m/%d')}/{unique_name}"

        url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET_NAME}/{file_path}"

        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": content_type or "application/octet-stream",
            "x-upsert": "false"
        }

        response = requests.post(
            url,
            headers=headers,
            data=file_content
        )

        if response.status_code not in (200, 201):
            return {
                "success": False,
                "error": response.text
            }

        return {
            "success": True,
            "file_path": file_path,
            "original_name": file_name,
            "unique_name": unique_name,
            "uploaded_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def delete_file(file_path: str) -> dict:
    """
    Delete file from Supabase Storage via REST
    """

    try:
        url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET_NAME}/{file_path}"

        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        }

        response = requests.delete(url, headers=headers)

        if response.status_code not in (200, 204):
            return {
                "success": False,
                "error": response.text
            }

        return {
            "success": True,
            "message": "File deleted successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_signed_url(file_path: str, expires_in: int = 3600) -> str:
    """
    Generate signed URL for private bucket file
    """

    try:
        url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/{settings.SUPABASE_BUCKET_NAME}/{file_path}"

        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            url,
            headers=headers,
            json={"expiresIn": expires_in}
        )

        if response.status_code != 200:
            return None

        signed_path = response.json().get("signedURL")

        return f"{settings.SUPABASE_URL}/storage/v1{signed_path}"

    except Exception:
        return None

