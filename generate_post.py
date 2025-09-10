import os, io, random, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageColor
import yaml, requests

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

# Optional free keys (PEXELS used if present)
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------
def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)

def pick_palette():
    return random.choice(CONFIG["brand"]["palette_choices"])

def pick_topic():
    return random.choice(CONFIG["topics"])

def load_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold \
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def add_signature(img: Image.Image, text: str) -> Image.Image:
    """Put a tiny signature at bottom-right. No other text in the image."""
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    font = load_font(28)
    pad = 20
    tw = d.textlength(text, font=font)
    th = 32
    w, h = img.size
    # subtle pill background
    bg = Image.new("RGBA", (int(tw + pad*1.5), th + pad//2), (0,0,0,120))
    img.alpha_composite(bg, (w - bg.size[0] - pad, h - bg.size[1] - pad))
    d.text((w - tw - pad - pad//4, h - th - pad), text, fill=(255,255,255,230), font=font)
    return img.convert("RGB")

# --------------------------------------------------------------------------------------
# Caption (free template; you still have your HF option in config if you want later)
# --------------------------------------------------------------------------------------
def offline_smart_caption(topic: str) -> str:
    hooks = [
        f"Shipping progress on {topic}.",
        f"Today’s focus: {topic}.",
        f"Building in public: {topic}.",
        f"Leveling up: {topic}.",
    ]
    principles = [
        "Momentum over perfection. Iterate, measure, refine.",
        "Small, consistent improvements > big, rare releases.",
        "Clean architecture, smooth UX, and real-world speed.",
        "Fast feedback loops: idea → prototype → polish.",
        "Clarity, observability, and performance as defaults.",
    ]
    hook = random.choice(hooks)
    value = random.choice(principles)
    tags = " ".join(CONFIG["brand"]["hashtags"])
    sig  = CONFIG["brand"]["signature_text"]
    return f"{hook}\n{value}\n\n{tags}\n\n{sig}"

def build_copy(topic: str) -> str:
    # Keep it simple & free for now
    return offline_smart_caption(topic)

# --------------------------------------------------------------------------------------
# Image search (FREE)
#   1) Pexels (needs PEXELS_API_KEY)
#   2) Openverse (no key)
#   3) Procedural fallback
# --------------------------------------------------------------------------------------
def fetch_pexels_image(topic: str) -> Image.Image | None:
    if not PEXELS_API_KEY:
        return None
    try:
        q = topic.split("(")[0].split(":")[0]  # softer query
        params = {
            "query": f"{q} mobile developer desk code",
            "per_page": 30,
            "orientation": "landscape"
        }
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params=params,
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        photos = data.get("photos", [])
        if not photos:
            return None
        choice = random.choice(photos)
        url = (choice.get("src", {}) or {}).get("large2x") or choice.get("src", {}).get("original")
        if not url:
            return None
        img_resp = requests.get(url, timeout=40)
        img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        return img
    except Exception:
        return None

def fetch_openverse_image(topic: str) -> Image.Image | None:
    try:
        q = topic.split("(")[0].split(":")[0]
        params = {
            "q": f"{q} mobile app developer desk code office",
            "page_size": 50,
            "license_type": "all-cc",
        }
        r = requests.get(
            "https://api.openverse.engineering/v1/images",
            params=params,
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            return None
        choice = random.choice(results)
        url = choice.get("url") or choice.get("thumbnail")
        if not url:
            return None
        img_resp = requests.get(url, timeout=40)
        img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        return img
    except Exception:
        return None

# --------------------------------------------------------------------------------------
# Procedural fallback visuals (no text, only signature)
# --------------------------------------------------------------------------------------
def gradient_bg(w, h, c1, c2):
    base = Image.new("RGB", (w, h), c2)
    top  = Image.new("RGB", (w, h), c1)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line((0, y, w, y), fill=int(255 * (1 - y / max(1, h-1))))
    return Image.composite(top, base, mask)

def fallback_procedural(palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    step = 40
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(255,255,255,25), width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(255,255,255,25), width=1)
    d.rectangle([20, 20, w-20, h-20], outline=(255,255,255,140), width=3)
    return bg.convert("RGB")

# --------------------------------------------------------------------------------------
# Build pipeline
# --------------------------------------------------------------------------------------
def build():
    ensure_dirs()
    topic = pick_topic()
    text  = build_copy(topic)

    # 1) Try Pexels → 2) Openverse → 3) Procedural
    img = fetch_pexels_image(topic)
    if img is None:
        img = fetch_openverse_image(topic)
    if img is None:
        img = fallback_procedural(pick_palette())

    # Ensure landscape 1600x900 crop without distortion
    target_w, target_h = 1600, 900
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        # too wide, crop sides
        new_w = int(img.height * target_ratio)
        offset = (img.width - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, img.height))
    elif img_ratio < target_ratio:
        # too tall, crop top/bottom
        new_h = int(img.width / target_ratio)
        offset = (img.height - new_h) // 2
        img = img.crop((0, offset, img.width, offset + new_h))
    img = img.resize((target_w, target_h), Image.LANCZOS)

    # Only a tiny signature on the image
    img = add_signature(img, CONFIG["brand"]["signature_text"])

    # file naming
    now = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    img.save(img_path, quality=95, subsampling=0)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {"image": img_path, "text": text, "topic": topic, "style": "photo_or_fallback", "stamp": stamp}

def append_logs(meta, status="PREVIEW"):
    exists = os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp","topic","status","style","image","text"])
        w.writerow([meta["stamp"], meta["topic"], status, meta.get("style","-"), os.path.basename(meta["image"]), meta["text"]])

    if not os.path.exists(LOG_MD):
        with open(LOG_MD,"w",encoding="utf-8") as f:
            f.write("# Content Log\n\n")
            f.write("| Timestamp | Topic | Status | Style |\n|---|---|---|---|\n")
    with open(LOG_MD,"a",encoding="utf-8") as f:
        f.write(f"| {meta['stamp']} | {meta['topic']} | {status} | {meta.get('style','-')} |\n")

if __name__ == "__main__":
    meta = build()
    append_logs(meta, "PREVIEW")
    print(json.dumps(meta, ensure_ascii=False))
