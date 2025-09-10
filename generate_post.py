# generate_post.py
import os, random, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import yaml

import stock_images  # NEW: online stock sources (free)
import overlays      # your vector overlays for fallback/procedural styles

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)

def pick_palette():
    return random.choice(CONFIG["brand"]["palette_choices"])

def pick_topic():
    return random.choice(CONFIG["topics"])

def load_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold \
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:    return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()

def gradient_bg(w, h, c1, c2):
    base = Image.new("RGB", (w, h), c2)
    top  = Image.new("RGB", (w, h), c1)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line((0, y, w, y), fill=int(255 * (1 - y / max(1, h-1))))
    return Image.composite(top, base, mask)

# ------- caption (free, concise) -------
def build_caption(topic: str) -> str:
    hooks = [
        f"Building in public: {topic}.",
        f"Today’s focus: {topic}.",
        f"Leveling up: {topic}.",
        f"Shipping progress on {topic}.",
    ]
    principles = [
        "Idea → prototype → polish — fast feedback loops.",
        "Small, consistent improvements > big, rare releases.",
        "Clean architecture, smooth UX, and real-world speed.",
        "Clarity, observability, and performance as defaults.",
    ]
    text = f"{random.choice(hooks)}\n{random.choice(principles)}"
    tags = " ".join(CONFIG["brand"]["hashtags"])
    sig  = CONFIG["brand"]["signature_text"]
    return f"{text}\n\n{tags}\n\n{sig}"

# ------- signature chip only (no text headline) -------
def signature_chip(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    chip = Image.new("RGBA", (560, 64), (0,0,0,0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle([0,0,559,63], radius=22, fill=(0,0,0,90))
    font = load_font(26)
    tw = cd.textlength(text, font=font)
    cd.text((560-20-tw, 18), text, fill=(255,255,255,235), font=font)
    img.alpha_composite(chip, (w-560-28, h-64-28))

# ------- procedural fallback styles (no text) -------
def style_blueprint(palette):
    w, h = 1600, 900
    blue = "#0a4aa3"
    bg = Image.new("RGB", (w,h), blue).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for x in range(0, w, 40):
        d.line([(x,0),(x,h)], fill=(255,255,255,35))
    for y in range(0, h, 40):
        d.line([(0,y),(w,y)], fill=(255,255,255,35))
    d.rectangle([20,20,w-20,h-20], outline=(255,255,255,170), width=4)
    return bg

def style_neon(palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], "#0b1021").convert("RGBA")
    d = ImageDraw.Draw(bg)
    for k in range(8):
        a = random.uniform(20, 90)
        f = random.uniform(0.008, 0.02)
        y0 = random.randint(0, h)
        pts = []
        for x in range(0, w, 8):
            y = int(y0 + a * math.sin(f*x + k))
            pts.append((x,y))
        d.line(pts, fill=(255,255,255,40), width=3)
    return bg

STYLE_FNS = {
    "blueprint": style_blueprint,
    "neon":      style_neon,
}

def _procedural_image(palette):
    style_name = random.choice(list(STYLE_FNS.keys()))
    img = STYLE_FNS[style_name](palette)
    overlays.apply_overlays(img, palette)     # gears/phone/crane guides
    signature_chip(img, CONFIG["brand"]["signature_text"])
    return img.convert("RGB"), style_name

# ------- stock-photo pipeline (free) -------
def _try_stock(topic: str, stamp: str) -> str | None:
    target = tuple(CONFIG.get("images", {}).get("target_size", [1600, 900]))
    raw_path = os.path.join(OUT, f"stock_{stamp}.jpg")

    # 1) Pexels (requires free key in secret PEXELS_API_KEY)
    if "pexels" in CONFIG.get("images", {}).get("provider_order", []):
        try:
            if stock_images.try_pexels(topic, raw_path, target_size=target):
                return raw_path
        except Exception:
            pass

    # 2) Openverse (no key)
    if "openverse" in CONFIG.get("images", {}).get("provider_order", []):
        try:
            if stock_images.try_openverse(topic, raw_path, target_size=target):
                return raw_path
        except Exception:
            pass

    return None

# ------- build ---------------------------------------------------------------
def build():
    ensure_dirs()
    topic    = pick_topic()
    caption  = build_caption(topic)
    palette  = pick_palette()

    now   = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    # Try stock image (Pexels→Openverse), else procedural fallback
    source = "procedural"
    stock_file = _try_stock(topic, stamp)
    if stock_file and os.path.exists(stock_file):
        source = "stock"
        im = Image.open(stock_file).convert("RGBA")
        # subtle vignette for polish (no text)
        overlay = Image.new("RGBA", im.size, (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        w, h = im.size
        for r in range(20):
            a = int(120 * (r/19))
            d.rectangle([r*3, r*3, w-r*3, h-r*3], outline=(0,0,0,a), width=3)
        im = Image.alpha_composite(im, overlay)
        signature_chip(im, CONFIG["brand"]["signature_text"])
        im.convert("RGB").save(img_path, quality=95, subsampling=0)
    else:
        im, style_name = _procedural_image(palette)
        im.save(img_path, quality=95, subsampling=0)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(caption)

    return {
        "image": img_path,
        "text": caption,
        "topic": topic,
        "style": source,
        "stamp": stamp,
    }

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
