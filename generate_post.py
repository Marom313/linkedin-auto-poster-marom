import os, random, json, csv, datetime, pytz, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import yaml

# NEW: stock photos (Pexels/Openverse) with free fallbacks
from stock_images import try_pexels, try_openverse

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

# ----------------------------- helpers ---------------------------------------

def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)

def pick_palette():
    return random.choice(CONFIG["brand"]["palette_choices"])

def rand_emoji():
    pool = CONFIG["style"]["emoji_pool"]
    return random.choice(pool) if CONFIG["style"]["allow_emojis"] else ""

def pick_topic():
    return random.choice(CONFIG["topics"])

def load_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold \
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
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
    lines, words, cur = [], text.split(), []
    for w in words:
        trial = " ".join(cur + [w])
        if draw.textlength(trial, font=font) <= max_width:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    return lines

# ----------------------------- persona-guided copy ----------------------------

def persona_caption(topic: str) -> str:
    p = CONFIG.get("persona", {})
    traits  = p.get("traits", [])
    anchors = p.get("anchors", [])
    humor   = int(p.get("humor", 1))
    depth   = int(p.get("depth", 2))

    humor_openers = ["", f"{rand_emoji()} Tiny win:", f"{rand_emoji()} Quick flex:"]
    opener = humor_openers[min(max(humor,0),2)]

    if depth == 1:
        value = "Momentum over perfection."
    elif depth == 2:
        value = "Clean architecture, smooth UX, real-world speed."
    else:
        technical = random.choice([
            "guarded routes + DI keep screens honest",
            "interceptors add resilience and observability",
            "offline queues de-risk flaky networks",
            "crash-free starts with signals and traces",
            "MVVM boundaries keep tests fast",
        ])
        value = f"{technical.capitalize()}."

    anchor = random.choice(anchors) if anchors else ""
    trait  = random.choice(traits) if traits else ""

    lines = [f"{opener} Building in public: {topic}".strip(), value]
    if depth >= 2 and trait:   lines.append(trait.capitalize())
    if depth >= 3 and anchor:  lines.append(f"Focus lately: {anchor}.")

    body = "\n".join([ln for ln in lines if ln])
    tags = " ".join(CONFIG["brand"]["hashtags"])
    sig  = CONFIG["brand"]["signature_text"]
    return f"{body}\n\n{tags}\n\n{sig}"

# ----------------------------- signature overlay -----------------------------

def add_signature_only(img: Image.Image, signature: str) -> Image.Image:
    """Put only a small signature in bottom-right of a photo or canvas."""
    d = ImageDraw.Draw(img)
    font = load_font(28)
    pad = 24
    tw = d.textlength(signature, font=font)
    th = 34
    w, h = img.size
    # soft plate behind text for contrast
    d.rectangle([w - tw - pad*2, h - th - pad, w - pad, h - pad], fill=(0,0,0,120))
    d.text((w - tw - pad*1.5, h - th - pad*1.2), signature, fill=(255,255,255), font=font)
    return img

# ----------------------------- procedural visuals (fallback) ------------------

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

def style_cartoon_card(topic, palette):
    w, h = 1600, 900
    bg = gradient_bg(w, h, palette[0], palette[1]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for _ in range(14):
        x0 = random.randint(-100, w); y0 = random.randint(-60, h)
        x1 = x0 + random.randint(60, 180); y1 = y0 + random.randint(30, 120)
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
    for x in range(0, w, step): d.line([(x,0),(x,h)], fill=(255,255,255,28), width=1)
    for y in range(0, h, step): d.line([(0,y),(w,y)], fill=(255,255,255,18), width=1)
    card = draw_card(bg, topic, "Fast feedback loops from idea to polish.", CONFIG["brand"]["signature_text"])
    avatar_badge(card, card.size[0]-120, 120)
    bg.alpha_composite(card, (110,110))
    return bg.convert("RGB")

def style_blueprint(topic, palette):
    w, h = 1600, 900
    blue = "#0a4aa3"
    bg = Image.new("RGB", (w,h), blue).convert("RGBA")
    d = ImageDraw.Draw(bg)
    for x in range(0, w, 40): d.line([(x,0),(x,h)], fill=(255,255,255,35))
    for y in range(0, h, 40): d.line([(0,y),(w,y)], fill=(255,255,255,35))
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
        a = random.uniform(20, 90); f = random.uniform(0.008, 0.02); y0 = random.randint(0, h)
        path = [(x, int(y0 + a * math.sin(f*x + k))) for x in range(0, w, 8)]
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
    # badge + card, still no text in the photo area other than signature
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
    text  = persona_caption(topic)  # persona-guided copy (free)

    # file naming early (so stock fetchers can write directly)
    now = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    # 1) Try stock photos (Pexels → Openverse)
    got_stock = try_pexels(topic, img_path) or try_openverse(topic, img_path)
    style_name = "stock:pexels" if got_stock else ""

    if got_stock:
        # open, add small signature, save
        img = Image.open(img_path).convert("RGB")
        img = add_signature_only(img, CONFIG["brand"]["signature_text"])
        img.save(img_path, quality=95, subsampling=0)
    else:
        # 2) Fallback to procedural visual
        palette = pick_palette()
        img, style_name = build_image(topic, palette)
        img = add_signature_only(img, CONFIG["brand"]["signature_text"])
        img.save(img_path, quality=95, subsampling=0)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {"image": img_path, "text": text, "topic": topic, "style": style_name or "procedural", "stamp": stamp}

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
