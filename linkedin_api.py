import os, time, json, requests

LI_CLIENT_ID     = os.environ["LI_CLIENT_ID"]
LI_CLIENT_SECRET = os.environ["LI_CLIENT_SECRET"]
LI_REDIRECT_URI  = os.environ["LI_REDIRECT_URI"]
LI_REFRESH_TOKEN = os.environ["LI_REFRESH_TOKEN"]

LI_API = "https://api.linkedin.com"
RESTLI = {"X-Restli-Protocol-Version": "2.0.0"}

def get_access_token_from_refresh():
    # 3-legged OAuth refresh flow
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "refresh_token",
        "refresh_token": LI_REFRESH_TOKEN,
        "client_id": LI_CLIENT_ID,
        "client_secret": LI_CLIENT_SECRET,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def get_person_urn(token):
    r = requests.get(f"{LI_API}/v2/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    lid = r.json().get("id")
    return f"urn:li:person:{lid}"

def upload_image_and_get_urn(token, person_urn, image_path):
    # Initialize upload
    init_url = f"{LI_API}/v2/images?action=initializeUpload"
    init_body = {"initializeUploadRequest": {"owner": person_urn}}
    r = requests.post(init_url, headers={"Authorization": f"Bearer {token}", **RESTLI, "Content-Type":"application/json"}, json=init_body, timeout=30)
    r.raise_for_status()
    data = r.json()
    upload_url = data["value"]["uploadUrl"]
    image_urn  = data["value"]["image"]

    # Upload binary
    with open(image_path, "rb") as f:
        ur = requests.put(upload_url, data=f.read(), headers={"Authorization": f"Bearer {token}"}, timeout=60)
        ur.raise_for_status()

    return image_urn

def create_ugc_post(token, person_urn, message_text, image_urn):
    url = f"{LI_API}/v2/ugcPosts"
    body = {
      "author": person_urn,
      "lifecycleState": "PUBLISHED",
      "specificContent": {
        "com.linkedin.ugc.ShareContent": {
          "shareCommentary": {"text": message_text},
          "shareMediaCategory": "IMAGE",
          "media": [{
             "status": "READY",
             "media": image_urn
          }]
        }
      },
      "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", **RESTLI, "Content-Type":"application/json"}, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def post_with_image(image_path, message_text):
    token = get_access_token_from_refresh()
    person_urn = get_person_urn(token)
    img_urn = upload_image_and_get_urn(token, person_urn, image_path)
    res = create_ugc_post(token, person_urn, message_text, img_urn)
    return res
