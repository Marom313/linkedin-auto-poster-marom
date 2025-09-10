# generate_post.py

import os, random, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import yaml, requests

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

HF_TOKEN     = os.environ.get("HF_TOKEN")         # optional (FREE)
OPENAI_KEY   = os.environ.get("OPENAI_API_KEY")   # optional (PAID — keep disabled to stay $0)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

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
    except:
        return ImageFont.load_default()

def gradient_bg(w, h, c1, c2):
    """Simple vertical gradient."""
    base = Image.new("RGB", (w, h), c2)
    top  = Image.new("RGB", (w, h), c1)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line((0, y, w, y), fill=int(255 * (1 - y / max(1, h-1))))
    return Image.composite(top, base, mask)

def add_signature(img, text):
    """Small, tasteful signature only (no other text)."""
    d = ImageDraw.Draw(img)
    font = load_font(28)
    tw = d.textlength(text, font=font)
    pad = 18
    # translucent chip background
    chip_w, chip_h = int(tw + pad * 2.2), 46
    x = img.width - chip_w - 28
    y = img.height - chip_h - 28
    chip = Image.new("RGBA", (chip_w, chip_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle([0, 0, chip_w, chip_h], radius=14, fill=(0, 0, 0, 90))
    img.alpha_composite(chip, (x, y))
    d.text((x + pad, y + 10), text, fill=(255, 255, 255, 220), font=font)
    return img

# ---------------------------------------------------------------------
# Smart caption (text for LinkedIn post – NOT drawn on the image)
# ---------------------------------------------------------------------

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
        "Idea → prototype → polish — fast feedback loops.",
        "Clarity, observability, and performance as defaults.",
    ]
    hook = random.choice(hooks)
    value = random.choice(principles)
    tags = " ".join(CONFIG["brand"]["hashtags"])
    sig  = CONFIG["brand"]["signature_text"]
    return f"{hook}\n{value}\n\n{tags}\n\n{sig}"

def hf_generate_text(prompt: str, model: str, max_words: int) -> str:
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max(40, min(160, max_words*2)),
            "temperature": 0.7,
            "top_p": 0.9,
        },
        "options": {"wait_for_model": True}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data and "generated_text" in data[0]:
        return data[0]["generated_text"]
    if isinstance(data, dict) and "generated_text" in data:
        return data["generated_text"]
    if isinstance(data, str):
        return data
    raise RuntimeError(f"Unexpected HF response: {str(data)[:200]}")

def openai_generate_text(prompt: str, model: str, max_words: int) -> str:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
        json={
            "model": model,
            "messages": [{"role":"user","content": prompt}],
            "temperature": 0.7,
        },
        timeout=40
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def build_copy(topic: str) -> str:
    cfg = (CONFIG.get("ai",{}).get("text",{}) or {})
    provider = (cfg.get("provider","none") or "none").lower()
    model    = cfg.get("model","")
    max_words = int(cfg.get("max_words",70))

    if provider == "huggingface" and HF_TOKEN:
        try:
            sys_prompt = (
                "You write concise, professional LinkedIn captions for a senior mobile engineer. "
                "Output 2 short sentences total (<= {mw} words). "
                "Sentence 1: a concrete hook about: '{topic}'. "
                "Sentence 2: a value takeaway (why it matters). "
                "Tone: warm, confident, specific. No hashtags, no links, no emojis."
            ).format(mw=max_words, topic=topic)
            txt = hf_generate_text(sys_prompt, model or "HuggingFaceH4/zephyr-7b-beta", max_words)
            lines = txt.strip().splitlines()
            core = " ".join([l.strip() for l in lines if l.strip()])[:500]
            tags = " ".join(CONFIG["brand"]["hashtags"])
            sig  = CONFIG["brand"]["signature_text"]
            return f"{core}\n\n{tags}\n\n{sig}"
        except Exception:
            return offline_smart_caption(topic)

    if provider == "openai" and OPENAI_KEY:
        try:
            prompt = (
                "Write a concise LinkedIn caption (<= {mw} words). "
                "Persona: welcoming, senior mobile engineer (Flutter, APIs, UX). "
                "Structure: 1 short hook about '{topic}', then 1 short value sentence. "
                "No hashtags, no links, no emojis."
            ).format(mw=max_words, topic=topic)
            txt = openai_generate_text(prompt, model or "gpt-4o-mini", max_words)
            tags = " ".join(CONFIG["brand"]["hashtags"])
            sig  = CONFIG["brand"]["signature_text"]
            return f"{txt}\n\n{tags}\n\n{sig}"
        except Exception:
            return offline_smart_caption(topic)

    return offline_smart_caption(topic)

# ---------------------------------------------------------------------
# Visual styles (NO TEXT ON IMAGE except small signature)
# ---------------------------------------------------------------------

def style_cartoon(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    # playful rounded shapes
    for _ in range(18):
        x0 = random.randint(-120, w)
        y0 = random.randint(-80, h)
        x1 = x0 + random.randint(80, 220)
        y1 = y0 + random.randint(60, 180)
        d.rounded_rectangle([x0,y0,x1,y1], radius=24, outline=(255,255,255,35), width=3)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_futuristic(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(10):
        cx, cy = random.randint(0,w), random.randint(0,h)
        r = random.randint(80, 220)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255,255,255,30), width=3)
    bg = Image.alpha_composite(bg.filter(ImageFilter.GaussianBlur(2)), bg)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_grid(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    step = 36
    for x in range(0, w, step):
        d.line([(x,0),(x,h)], fill=(255,255,255,26), width=1)
    for y in range(0, h, step):
        d.line([(0,y),(w,y)], fill=(255,255,255,18), width=1)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_blueprint(topic, palette):
    w, h = 1600, 900
    bg = Image.new("RGBA", (w,h), "#0a4aa3")
    d = ImageDraw.Draw(bg)
    for x in range(0, w, 40):
        d.line([(x,0),(x,h)], fill=(255,255,255,35))
    for y in range(0, h, 40):
        d.line([(0,y),(w,y)], fill=(255,255,255,35))
    d.rectangle([20,20,w-20,h-20], outline=(255,255,255,170), width=4)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_halftone(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    dots = Image.new("RGBA", (w,h), (0,0,0,0))
    dd = ImageDraw.Draw(dots)
    step = 24
    for y in range(0,h,step):
        for x in range(0,w,step):
            r = int(3 + 2.5*math.sin(x*0.015) * math.cos(y*0.02))
            dd.ellipse([x-r,y-r,x+r,y+r], fill=(0,0,0,18))
    bg.alpha_composite(dots)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_neon(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], "#0b1021").convert("RGBA")
    d = ImageDraw.Draw(bg)
    for k in range(8):
        a = random.uniform(20, 90)
        f = random.uniform(0.008, 0.02)
        y0 = random.randint(0, h)
        path = []
        for x in range(0, w, 8):
            y = int(y0 + a * math.sin(f*x + k))
            path.append((x,y))
        d.line(path, fill=(255,255,255,40), width=3)
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_cubes(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(60):
        cx, cy = random.randint(-80,w+80), random.randint(-80,h+80)
        size = random.randint(14, 32)
        top = [(cx,cy-size),(cx+size,cy),(cx,cy+size),(cx-size,cy)]
        d.polygon(top, outline=(255,255,255,40))
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

def style_pastel(topic, palette):
    w, h = 1600, 900
    pastel = ["#ffd6e7","#d6f0ff","#e6ffd6","#fff1cc","#e6e0ff"]
    c1, c2 = random.choice(pastel), random.choice(pastel)
    bg = gradient_bg(w, h, c1, c2).convert("RGBA")
    # soft blobs
    for _ in range(12):
        rx, ry = random.randint(80, 260), random.randint(60, 180)
        x, y = random.randint(-100,w), random.randint(-80,h)
        blob = Image.new("RGBA", (rx*2, ry*2), (0,0,0,0))
        bd = ImageDraw.Draw(blob)
        bd.ellipse([0,0,rx*2,ry*2], fill=(255,255,255,70))
        blob = blob.filter(ImageFilter.GaussianBlur(18))
        bg.alpha_composite(blob, (x-rx, y-ry))
    return add_signature(bg, CONFIG["brand"]["signature_text"]).convert("RGB")

STYLE_VARIANTS = {
    "cartoon":   style_cartoon,
    "futuristic":style_futuristic,
    "grid":      style_grid,
    "blueprint": style_blueprint,
    "halftone":  style_halftone,
    "neon":      style_neon,
    "cubes":     style_cubes,
    "pastel":    style_pastel,
}

def weighted_choice(weights_map):
    items = [(k, max(0, int(v))) for k, v in (weights_map or {}).items()]
    items = [(k,v) for k,v in items if k in STYLE_VARIANTS and v > 0]
    if not items:
        return random.choice(list(STYLE_VARIANTS.keys()))
    total = sum(v for _,v in items)
    r = random.randint(1, total)
    acc = 0
    for k, v in items:
        acc += v
        if r <= acc:
            return k
    return items[-1][0]

def build_image(topic, palette):
    name = weighted_choice(CONFIG.get("style_weights", {}))
    img  = STYLE_VARIANTS[name](topic, palette)
    return img, name

# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def build():
    ensure_dirs()
    topic = pick_topic()
    text  = build_copy(topic)     # Caption for LinkedIn (NOT drawn on image)
    palette = pick_palette()
    img, style_name = build_image(topic, palette)

    now = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    img.save(img_path, quality=95, subsampling=0)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {"image": img_path, "text": text, "topic": topic, "style": style_name, "stamp": stamp}

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
