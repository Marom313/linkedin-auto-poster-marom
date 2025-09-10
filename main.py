import os, json, uuid, pytz, datetime, yaml
from generate_post import build, append_logs
from telegram_approval import send_preview, wait_for_approval
from linkedin_api import post_with_image

CONFIG = yaml.safe_load(open("config.yaml","r",encoding="utf-8"))

def is_scheduled_now():
    tz = pytz.timezone("Asia/Jerusalem")
    now = datetime.datetime.now(tz)
    day = now.strftime("%a").upper()  # SUN/MON/...
    time_str = now.strftime("%H:%M")
    return (day in CONFIG["post_schedule"]["days"]) and (time_str == CONFIG["post_schedule"]["local_time"])

def run_once(force=False):
    if (not force) and (not is_scheduled_now()):
        print("Not scheduled time; exiting.")
        return 0

    meta = build()
    approval_code = uuid.uuid4().hex[:6].upper()
    send_preview(meta["image"], meta["text"], approval_code)

    if CONFIG["dry_run"]["enabled"]:
        append_logs(meta, "DRY_RUN_PREVIEW")
        print("Dry-run enabled; not waiting for approval.")
        return 0

    decision = wait_for_approval(approval_code, CONFIG["telegram"]["approval_timeout_minutes"])
    if decision is True:
        try:
            res = post_with_image(meta["image"], meta["text"])
            append_logs(meta, "POSTED")
            print(json.dumps({"status":"posted","linkedin_response":res}, ensure_ascii=False))
            return 0
        except Exception as e:
            # fallback: inform in logs (the Telegram preview already has image+text)
            append_logs(meta, f"FAILED:{e}")
            print(f"Failed to post: {e}")
            return 1
    elif decision is False:
        append_logs(meta, "SKIPPED")
        print("User skipped.")
        return 0
    else:
        append_logs(meta, "NO_APPROVAL")
        print("No approval received within timeout; exiting.")
        return 0

if __name__ == "__main__":
    force = os.environ.get("FORCE_RUN") == "1"
    run_once(force=force)
