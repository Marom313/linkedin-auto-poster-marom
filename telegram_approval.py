import os, time, requests, json

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _post(method: str, **data):
    r = requests.post(f"{API}/{method}", data=data, timeout=60)
    try:
        jr = r.json()
    except Exception:
        r.raise_for_status()
        return r
    if not jr.get("ok", False):
        raise RuntimeError(f"Telegram error on {method}: {jr}")
    return jr

def send_preview(image_path, text, approval_code):
    caption = (
        "Preview for LinkedIn post\n"
        f"Approval code: {approval_code}\n\n"
        "Choose:\n"
        "  ✅ Approve\n"
        "  ❌ Skip\n"
        "  🔁 Another idea\n\n"
    ) + text

    # Inline keyboard
    kb = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"APPROVE:{approval_code}"},
                {"text": "❌ Skip",    "callback_data": f"SKIP:{approval_code}"},
            ],
            [
                {"text": "🔁 Another idea", "callback_data": f"ANOTHER:{approval_code}"}
            ]
        ]
    }

    with open(image_path, "rb") as f:
        r = requests.post(
            f"{API}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption, "reply_markup": json.dumps(kb)},
            files={"photo": f},
            timeout=60,
        )
    jr = r.json()
    if not jr.get("ok", False):
        raise RuntimeError(f"Telegram sendPhoto failed: {jr}")
    return True

def _ack_callback(callback_id, text="Got it"):
    try:
        requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text}, timeout=20)
    except Exception:
        pass

def wait_for_approval(approval_code, timeout_minutes):
    """
    Returns:
      True      -> approved
      False     -> skipped
      "ANOTHER" -> user asked for another idea
      None      -> timeout
    """
    deadline = time.time() + timeout_minutes * 60
    offset = None
    code_upper = str(approval_code).upper()

    while time.time() < deadline:
        params = {"timeout": 20}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=40)
        jr = r.json()
        if not jr.get("ok", False):
            time.sleep(2); continue

        for upd in jr.get("result", []):
            offset = upd["update_id"] + 1

            # callback buttons
            cb = upd.get("callback_query")
            if cb:
                data = (cb.get("data") or "").upper()
                msg  = cb.get("message", {})
                chat = (msg.get("chat") or {}).get("id")
                if str(chat) != str(CHAT_ID):
                    _ack_callback(cb.get("id"), "Not your chat")
                    continue
                if data == f"APPROVE:{code_upper}":
                    _ack_callback(cb.get("id"), "Approved ✅")
                    return True
                if data == f"SKIP:{code_upper}":
                    _ack_callback(cb.get("id"), "Skipped ❌")
                    return False
                if data == f"ANOTHER:{code_upper}":
                    _ack_callback(cb.get("id"), "Generating another 🔁")
                    return "ANOTHER"

            # fallback text commands
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            if str((msg.get("chat") or {}).get("id")) != str(CHAT_ID):
                continue
            txt = (msg.get("text") or "").strip().upper()
            if txt == f"APPROVE {code_upper}":
                return True
            if txt == f"SKIP {code_upper}":
                return False

        time.sleep(2)

    return None
