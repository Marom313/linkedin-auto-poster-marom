import os, time, json, requests, pathlib

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

def send_preview(image_path, text, approval_code):
    caption = f"Preview for LinkedIn post\nApproval code: {approval_code}\n\nReply with:\n  APPROVE {approval_code}\n  or\n  SKIP {approval_code}\n\n{text}"
    with open(image_path, "rb") as f:
        r = requests.post(f"{API}/sendPhoto", data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": f}, timeout=60)
        r.raise_for_status()
    return True

def wait_for_approval(approval_code, timeout_minutes):
    deadline = time.time() + timeout_minutes*60
    offset = None
    approve = None
    code_upper = str(approval_code).upper()
    while time.time() < deadline:
        params = {"timeout": 20}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=40)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            time.sleep(3);
            continue
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg: continue
            if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
                continue
            txt = (msg.get("text") or "").strip().upper()
            if txt == f"APPROVE {code_upper}":
                approve = True; return approve
            if txt == f"SKIP {code_upper}":
                approve = False; return approve
        # brief pause before next poll
        time.sleep(3)
    return None  # timeout (no approval)
