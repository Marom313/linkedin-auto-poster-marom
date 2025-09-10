import os
import json
import uuid
import pytz
import datetime
import yaml
import requests

from generate_post import build, append_logs
from telegram_approval import send_preview, wait_for_approval
from linkedin_api import post_with_image

# --- Telegram debug pings -----------------------------------------------------

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID")

def tg_notify(text: str):
    """Fire-and-forget Telegram message (for visibility on CI)."""
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": text},
            timeout=15,
        )
    except Exception:
        # Never block on debug notifications
        pass

# --- Config -------------------------------------------------------------------

with open("config.yaml", "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# --- Scheduling ---------------------------------------------------------------

def is_scheduled_now() -> bool:
    tz = pytz.timezone("Asia/Jerusalem")
    now = datetime.datetime.now(tz)
    day = now.strftime("%a").upper()      # SUN/MON/...
    time_str = now.strftime("%H:%M")      # 10:00
    return (day in CONFIG["post_schedule"]["days"]) and (
        time_str == CONFIG["post_schedule"]["local_time"]
    )

# --- Main flow ----------------------------------------------------------------

def run_once(force: bool = False) -> int:
    if (not force) and (not is_scheduled_now()):
        print("Not scheduled time; exiting.")
        return 0

    # Build content (image + text)
    meta = build()  # -> {"image": <path>, "text": <str>, "topic": ..., ...}

    # Create approval code and send preview
    approval_code = uuid.uuid4().hex[:6].upper()
    send_preview(meta["image"], meta["text"], approval_code)

    # Dry-run: log and quit (no approval waiting, no posting)
    if CONFIG.get("dry_run", {}).get("enabled", False):
        append_logs(meta, "DRY_RUN_PREVIEW")
        print("Dry-run enabled; not waiting for approval.")
        return 0

    # Wait for explicit APPROVE/SKIP from Telegram
    decision = wait_for_approval(
        approval_code,
        CONFIG.get("telegram", {}).get("approval_timeout_minutes", 120),
    )

    if decision is True:
        try:
            res = post_with_image(meta["image"], meta["text"])
            append_logs(meta, "POSTED")
            print(json.dumps({"status": "posted", "linkedin_response": res}, ensure_ascii=False))
            return 0
        except Exception as e:
            # Fallback: preview already in Telegram so you can post manually
            append_logs(meta, f"FAILED:{e}")
            print(f"Failed to post: {e}")
            tg_notify(f"❌ Post failed: {e.__class__.__name__}: {e}")
            return 1

    if decision is False:
        append_logs(meta, "SKIPPED")
        print("User skipped.")
        return 0

    # No decision within timeout
    append_logs(meta, "NO_APPROVAL")
    print("No approval received within timeout; exiting.")
    return 0

# --- Entrypoint ---------------------------------------------------------------

if __name__ == "__main__":
    force = os.environ.get("FORCE_RUN") == "1"
    try:
        tg_notify("🔧 Workflow started — generating preview… (force=%s)" % force)
        code = run_once(force=force)
        if code == 0:
            tg_notify("✅ Run finished.")
        else:
            tg_notify("⚠️ Run finished with errors (exit=%d)." % code)
    except Exception as e:
        # Surface any unexpected crash to Telegram and CI logs
        tg_notify(f"❌ Unhandled error: {e.__class__.__name__}: {e}")
        raise
