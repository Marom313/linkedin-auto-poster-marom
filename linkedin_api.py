import os
import json
import requests

# Env (refresh-token path optional; we mainly use LI_ACCESS_TOKEN for now)
LI_CLIENT_ID     = os.environ.get("LI_CLIENT_ID")
LI_CLIENT_SECRET = os.environ.get("LI_CLIENT_SECRET")
LI_REDIRECT_URI  = os.environ.get("LI_REDIRECT_URI")
LI_REFRESH_TOKEN = os.environ.get("LI_REFRESH_TOKEN")
LI_ACCESS_TOKEN  = os.environ.get("LI_ACCESS_TOKEN")  # direct token from OAuth tool

LI_API = "https://api.linkedin.com"
RESTLI = {"X-Restli-Protocol-Version": "2.0.0"}

class LinkedInError(Exception):
    pass

def get_access_token():
    """
    Prefers refresh-token flow if provided, otherwise uses LI_ACCESS_TOKEN directly.
    """
    if LI_REFRESH_TOKEN:
        r = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": LI_REFRESH_TOKEN,
                "client_id": LI_CLIENT_ID,
                "client_secret": LI_CLIENT_SECRET,
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise LinkedInError(f"Refresh token exchange failed: {r.status_code} {r.text}")
        return r.json()["access_token"]

    if LI_ACCESS_TOKEN:
        return LI_ACCESS_TOKEN

    raise LinkedInError("No LI_REFRESH_TOKEN or LI_ACCESS_TOKEN provided.")

def get_person_urn(token: str) -> str:
    """
    Try OpenID userinfo first (works with 'openid profile' scopes from the OAuth tool).
    Fallback to /v2/me (requires r_liteprofile) if userinfo is unavailable.
    """
    try:
        r = requests.get(f"{LI_API}/v2/userinfo", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code == 200:
            lid = r.json().get("sub")
            if lid:
                return f"urn:li:person:{lid}"
    except Exception:
        pass  # fall back to /v2/me

    r = requests.get(f"{LI_API}/v2/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code >= 400:
        raise LinkedInError(f"/v2/me failed: {r.status_code} {r.text}")
    lid = r.json().get("id")
    if not lid:
        raise LinkedInError("Could not extract LinkedIn member id.")
    return f"urn:li:person:{lid}"

def upload_image_and_get_urn(token: str, person_urn: str, image_path: str) -> str:
    """
    Initialize an image upload, PUT the bytes, and return the image URN.
    """
    init_url = f"{LI_API}/v2/images?action=initializeUpload"
    init_body = {"initializeUploadRequest": {"owner": person_urn}}
    rh = {"Authorization": f"Bearer {token}", **RESTLI, "Content-Type": "application/json"}
    r = requests.post(init_url, headers=rh, json=init_body, timeout=30)
    if r.status_code >= 400:
        raise LinkedInError(f"Image init failed: {r.status_code} {r.text}")
    data = r.json()
    upload_url = data["value"]["uploadUrl"]
    image_urn  = data["value"]["image"]

    with open(image_path, "rb") as f:
        ur = requests.put(upload_url, data=f.read(), headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if ur.status_code >= 400:
            raise LinkedInError(f"Image upload failed: {ur.status_code} {ur.text}")

    return image_urn

def create_ugc_post(token: str, person_urn: str, message_text: str, image_urn: str) -> dict:
    """
    Create a public UGC image post.
    """
    url = f"{LI_API}/v2/ugcPosts"
    body = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": message_text},
                "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY", "media": image_urn}],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", **RESTLI, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if r.status_code >= 400:
        raise LinkedInError(f"UGC post failed: {r.status_code} {r.text}")
    return r.json()

def post_with_image(image_path: str, message_text: str) -> dict:
    token = get_access_token()
    person_urn = get_person_urn(token)
    image_urn = upload_image_and_get_urn(token, person_urn, image_path)
    return create_ugc_post(token, person_urn, message_text, image_urn)
