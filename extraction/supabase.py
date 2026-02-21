import requests
from django.conf import settings


def save_proof(data):

    url = f"{settings.SUPABASE_URL}/rest/v1/extracted_proofs"

    headers = {

        "apikey": settings.SUPABASE_KEY,

        "Authorization":
        f"Bearer {settings.SUPABASE_KEY}",

        "Content-Type": "application/json",

        "Prefer": "return=minimal"
    }

    response = requests.post(
        url,
        json=data,
        headers=headers
    )

    return response.status_code

