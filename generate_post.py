# generate_post.py
import os, random, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFilter, ImageColor, ImageFont
import yaml
import overlays  # NEW

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

# ---------------- helpers ----------------

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

# ------------- caption (kept smart but free) -------------

def build_caption(topic: str) -> str:
    hooks = [
        f"Today’s focus: {topic}.",
        f"Leveling up: {topic}.",
        f"Shipping progress on {topic}.",
        f"Building in public: {topic}.",
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

# ------------- styles (no text inside image) -------------

def _signature_chip(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    chip = Image.new("RGBA", (560, 64), (0,0,0,0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle([0,0,559,63], radius=22, fill=(0,0,0,90))
    font = load_font(26)
    tw = cd.textlength(text, font=font)
    cd.text((560-20-tw, 18), text, fill=(255,255,255,235), font=font)
    img.alpha_composite(chip, (w-560-28, h-64-28))

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

def style_glow(palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(10):
        cx, cy = random.randint(0,w), random.randint(0,h)
        r = random.randint(80, 220)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255,255,255,28), width=2)
    bg = Image.alpha_composite(bg.filter(ImageFilter.GaussianBlur(6)), bg)
    return bg

def style_grid(palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    step = 32
    for x in range(0, w, step):
        d.line([(x,0),(x,h)], fill=(255,255,255,28), width=1)
    for y in range(0, h, step):
        d.line([(0,y),(w,y)], fill=(255,255,255,18), width=1)
    return bg

STYLE_FNS = {
    "blueprint": style_blueprint,
    "neon":      style_neon,
    "glow":      style_glow,
    "grid":      style_grid,
}

def build_image(topic, palette):
    style_name = random.choices(
        population=list(STYLE_FNS.keys()),
        weights=[3,3,2,2],  # tweak if you like
        k=1
    )[0]
    img = STYLE_FNS[style_name](palette)
    # NEW: add overlays (phone, crane, gears, wrench, dotted guides)
    overlays.apply_overlays(img, palette)
    # tiny signature chip only (no text headlines)
    _signature_chip(img, CONFIG["brand"]["signature_text"])
    return img.convert("RGB"), style_name

# ------------- pipeline -------------

def build():
    ensure_dirs()
    topic   = pick_topic()
    caption = build_caption(topic)
    palette = pick_palette()
    img, style_name = build_image(topic, palette)

    now = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    img.save(img_path, quality=95, subsampling=0)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(caption)

    return {"image": img_path, "text": caption, "topic": topic, "style": style_name, "stamp": stamp}

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
