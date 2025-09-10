import os, time, requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _post(method: str, **data):
    r = requests.post(f"{API}/{method}", data=data, timeout=60)
    try:
        jr = r.json()
    except Exception:
        r.raise_for_status()
        return r  # not JSON, but OK
    if not jr.get("ok", False):
        # Surface Telegram error in logs
        raise RuntimeError(f"Telegram error on {method}: {jr}")
    return jr

def send_preview(image_path, text, approval_code):
    caption = (
        "Preview for LinkedIn post\n"
        f"Approval code: {approval_code}\n\n"
        "Reply with:\n  APPROVE {code}\n  or\n  SKIP {code}\n\n"
    ).format(code=approval_code) + text

    with open(image_path, "rb") as f:
        r = requests.post(
            f"{API}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
            timeout=60,
        )
    jr = r.json()
    if not jr.get("ok", False):
        raise RuntimeError(f"Telegram sendPhoto failed: {jr}")
    return True

def wait_for_approval(approval_code, timeout_minutes):
    deadline = time.time() + timeout_minutes * 60
    offset = None
    code_upper = str(approval_code).upper()

    while time.time() < deadline:
        params = {"timeout": 20}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=40)
        jr = r.json()
        if not jr.get("ok", False):
            time.sleep(3); continue

        for upd in jr.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg: continue
            chat = msg.get("chat", {})
            if str(chat.get("id")) != str(CHAT_ID):  # only your chat
                continue
            txt = (msg.get("text") or "").strip().upper()
            if txt == f"APPROVE {code_upper}":
                return True
            if txt == f"SKIP {code_upper}":
                return False

        time.sleep(3)

    return None  # timeout
