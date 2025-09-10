import os, random, textwrap, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageColor
import yaml, requests

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

HF_TOKEN     = os.environ.get("HF_TOKEN")         # optional (FREE)
OPENAI_KEY   = os.environ.get("OPENAI_API_KEY")   # optional (PAID — disabled by default)

# ----------------------------- helpers ---------------------------------------

def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)

def pick_palette():
    return random.choice(CONFIG["brand"]["palette_choices"])

def rand_emoji():
    return random.choice(CONFIG["style"]["emoji_pool"]) if CONFIG["style"]["allow_emojis"] else ""

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
    base = Image.new("RGB", (w, h), c2)
    top  = Image.new("RGB", (w, h), c1)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line((0, y, w, y), fill=int(255 * (1 - y / max(1, h-1))))
    return Image.composite(top, base, mask)

def text_wrap(draw, text, font, max_width):
    lines, words = [], text.split()
    cur=[]
    for w in words:
        trial=" ".join(cur+[w])
        if draw.textlength(trial, font=font) <= max_width:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur=[w]
    if cur: lines.append(" ".join(cur))
    return lines

# ----------------------------- smarter copy ----------------------------------

def offline_smart_caption(topic: str) -> str:
    """Crisp, value-dense template (free)."""
    hooks = [
        f"{rand_emoji()} Shipping progress on {topic}.",
        f"{rand_emoji()} Today’s focus: {topic}.",
        f"{rand_emoji()} Building in public: {topic}.",
        f"{rand_emoji()} Leveling up: {topic}.",
    ]
    principles = [
        "Momentum over perfection. Iterate, measure, refine.",
        "Small, consistent improvements > big, rare releases.",
        "Clean architecture, smooth UX, and real-world speed.",
        "From idea → prototype → polish — fast feedback loops.",
        "Clarity, observability, and performance as defaults.",
    ]
    hook = random.choice(hooks)
    value = random.choice(principles)
    tags = " ".join(CONFIG["brand"]["hashtags"])
    sig  = CONFIG["brand"]["signature_text"]
    return f"{hook}\n{value}\n\n{tags}\n\n{sig}"

def hf_generate_text(prompt: str, model: str, max_words: int) -> str:
    """FREE (tokened) HuggingFace text-generation."""
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
    # Some models return dict with 'generated_text'
    if isinstance(data, dict) and "generated_text" in data:
        return data["generated_text"]
    # Fallback to raw string
    if isinstance(data, str):
        return data
    raise RuntimeError(f"Unexpected HF response: {str(data)[:200]}")

def openai_generate_text(prompt: str, model: str, max_words: int) -> str:
    """PAID OpenAI path — present in code but **do not enable** unless you want costs."""
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

    # 1) HuggingFace (FREE) if selected & token present
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
            # sanitize & append brand
            lines = txt.strip().splitlines()
            core = " ".join([l.strip() for l in lines if l.strip()])[:500]
            tags = " ".join(CONFIG["brand"]["hashtags"])
            sig  = CONFIG["brand"]["signature_text"]
            return f"{core}\n\n{tags}\n\n{sig}"
        except Exception:
            # fall back to free template
            return offline_smart_caption(topic)

    # 2) OpenAI (PAID) — DISABLED unless provider is "openai" and key exists
    if provider == "openai" and OPENAI_KEY:
        try:
            prompt = (
                "Write a concise LinkedIn caption (<= {mw} words). "
                "Persona: welcoming, senior mobile engineer (Flutter, APIs, UX). "
                "Structure: 1 short hook sentence about: '{topic}'. "
                "Then 1 short value sentence (what/why). No hashtags, no links, no emojis. "
                "Tone: confident, friendly, specific."
            ).format(mw=max_words, topic=topic)
            txt = openai_generate_text(prompt, model or "gpt-4o-mini", max_words)
            tags = " ".join(CONFIG["brand"]["hashtags"])
            sig  = CONFIG["brand"]["signature_text"]
            return f"{txt}\n\n{tags}\n\n{sig}"
        except Exception:
            return offline_smart_caption(topic)

    # 3) Default free template
    return offline_smart_caption(topic)

# ----------------------------- visuals (FREE) ---------------------------------

def draw_card(canvas, title, sub, signature):
    w, h = canvas.size
    card = Image.new("RGBA", (w-220, h-280), (255,255,255,238))
    shadow = Image.new("RGBA", (card.size[0]+40, card.size[1]+40), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([0,0,shadow.size[0]-1,shadow.size[1]-1], radius=28, fill=(0,0,0,85))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    canvas.alpha_composite(shadow, (110-16,110-16))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0,0,card.size[0]-1,card.size[1]-1], radius=28, fill=(255,255,255,245))
    title_font = load_font(56, bold=True)
    sub_font   = load_font(34)
    wrap = text_wrap(cd, title, title_font, card.size[0]-80)
    y = 44
    for line in wrap:
        cd.text((40,y), line, fill=(22,27,34), font=title_font)
        y += 62
    cd.text((40,y+6), sub, fill=(70,84,98), font=sub_font)
    sig_font = load_font(28)
    tw = cd.textlength(signature, font=sig_font)
    cd.text((card.size[0]-tw-40, card.size[1]-52), signature, fill=(60,72,88), font=sig_font)
    return card

def avatar_badge(card, x, y, r=46):
    d = ImageDraw.Draw(card)
    d.ellipse([x-r, y-r, x+r, y+r], fill=(255,255,255,235))
    d.ellipse([x-r+10, y-r+10, x+r-10, y+r-10], fill=(245,208,170,255))
    d.arc([x-20, y-5, x+20, y+25], 15, 165, fill=(40,40,40,255), width=3)
    d.ellipse([x-12, y-5, x-4, y+3], fill=(40,40,40,255))
    d.ellipse([x+4,  y-5, x+12, y+3], fill=(40,40,40,255))

# 8 varied free styles
def style_cartoon_card(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(14):
        x0 = random.randint(-100, w)
        y0 = random.randint(-60, h)
        x1 = x0 + random.randint(60, 180)
        y1 = y0 + random.randint(30, 120)
        d.rounded_rectangle([x0,y0,x1,y1], radius=18, outline=(255,255,255,30), width=2)
    card = draw_card(bg, topic, "Building, learning, iterating — every week.", CONFIG["brand"]["signature_text"])
    avatar_badge(card, card.size[0]-120, 120)
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_futuristic_glow(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(12):
        cx, cy = random.randint(0,w), random.randint(0,h)
        r = random.randint(70, 220)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255,255,255,28), width=2)
    blur = bg.filter(ImageFilter.GaussianBlur(6))
    bg = Image.alpha_composite(blur, bg)
    card = draw_card(bg, topic, "Clean architecture and real-world speed.", CONFIG["brand"]["signature_text"])
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_lineart_grid(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    step = 32
    for x in range(0, w, step):
        d.line([(x,0),(x,h)], fill=(255,255,255,28), width=1)
    for y in range(0, h, step):
        d.line([(0,y),(w,y)], fill=(255,255,255,18), width=1)
    card = draw_card(bg, topic, "Fast feedback loops from idea to polish.", CONFIG["brand"]["signature_text"])
    avatar_badge(card, card.size[0]-120, 120)
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_blueprint(topic, palette):
    w, h = 1600, 900
    blue = "#0a4aa3"
    bg = Image.new("RGB", (w,h), blue).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for x in range(0, w, 40):
        d.line([(x,0),(x,h)], fill=(255,255,255,35))
    for y in range(0, h, 40):
        d.line([(0,y),(w,y)], fill=(255,255,255,35))
    d.rectangle([20,20,w-20,h-20], outline=(255,255,255,170), width=4)
    card = draw_card(bg, topic, "Blueprinting great mobile experiences.", CONFIG["brand"]["signature_text"])
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_retro_halftone(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    dots = Image.new("RGBA", (w,h), (0,0,0,0))
    dd = ImageDraw.Draw(dots)
    step = 24
    for y in range(0,h,step):
        for x in range(0,w,step):
            r = int(4 + 3*math.sin(x*0.015) * math.cos(y*0.02))
            dd.ellipse([x-r,y-r,x+r,y+r], fill=(0,0,0,20))
    bg.alpha_composite(dots)
    card = draw_card(bg, topic, "Retro vibes, modern performance.", CONFIG["brand"]["signature_text"])
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_neon_wave(topic, palette):
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
    card = draw_card(bg, topic, "Neon clarity for complex problems.", CONFIG["brand"]["signature_text"])
    avatar_badge(card, card.size[0]-120, 120)
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_isometric_cubes(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(60):
        cx, cy = random.randint(-80,w+80), random.randint(-80,h+80)
        size = random.randint(14, 32)
        top = [(cx,cy-size),(cx+size,cy),(cx,cy+size),(cx-size,cy)]
        d.polygon(top, outline=(255,255,255,40))
    card = draw_card(bg, topic, "Systems that scale without the bloat.", CONFIG["brand"]["signature_text"])
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_anime_pastel(topic, palette):
    w, h = 1600, 900
    pastel = ["#ffd6e7","#d6f0ff","#e6ffd6","#fff1cc","#e6e0ff"]
    c1, c2 = random.choice(pastel), random.choice(pastel)
    bg = gradient_bg(w, h, c1, c2).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(12):
        rx, ry = random.randint(80, 260), random.randint(60, 180)
        x, y = random.randint(-100,w), random.randint(-80,h)
        blob = Image.new("RGBA", (rx*2, ry*2), (0,0,0,0))
        bd = ImageDraw.Draw(blob)
        bd.ellipse([0,0,rx*2,ry*2], fill=(255,255,255,80))
        blob = blob.filter(ImageFilter.GaussianBlur(18))
        bg.alpha_composite(blob, (x-rx, y-ry))
    badge = Image.new("RGBA", (280,280), (255,255,255,220))
    bd = ImageDraw.Draw(badge)
    bd.ellipse([0,0,279,279], fill=(255,255,255,220))
    bd.ellipse([20,20,259,259], fill=(245,208,170,255))
    bd.arc([80,120,200,220], 15, 165, fill=(40,40,40,255), width=5)
    bg.alpha_composite(badge, (w-360, 120))
    card = draw_card(bg, topic, "Soft look, sharp craft.", CONFIG["brand"]["signature_text"])
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

STYLE_VARIANTS = {
    "cartoon_card":     style_cartoon_card,
    "futuristic_glow":  style_futuristic_glow,
    "lineart_grid":     style_lineart_grid,
    "blueprint":        style_blueprint,
    "retro_halftone":   style_retro_halftone,
    "neon_wave":        style_neon_wave,
    "isometric_cubes":  style_isometric_cubes,
    "anime_pastel":     style_anime_pastel,
}

def build_image(topic, palette):
    name = random.choice(list(STYLE_VARIANTS.keys()))
    img  = STYLE_VARIANTS[name](topic, palette)
    return img, name

# ----------------------------- pipeline ---------------------------------------

def build():
    ensure_dirs()
    topic = pick_topic()
    text  = build_copy(topic)  # smart/free
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
