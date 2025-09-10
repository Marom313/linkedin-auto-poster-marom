import os, random, textwrap, json, csv, datetime, pytz
from dateutil import tz
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import yaml

ROOT = os.path.dirname(__file__)
OUT = os.path.join(ROOT, "out")
LOG_CSV = os.path.join(ROOT, "content_log.csv")
LOG_MD  = os.path.join(ROOT, "content_log.md")
CONFIG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8"))

def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)

def pick_palette():
    return random.choice(CONFIG["brand"]["palette_choices"])

def rand_emoji():
    return random.choice(CONFIG["style"]["emoji_pool"]) if CONFIG["style"]["allow_emojis"] else ""

def pick_topic():
    return random.choice(CONFIG["topics"])

def make_one_liner(topic):
    # A simple, sharp template system
    bits = [
        f"{rand_emoji()} Shipping something small but meaningful: {topic}.",
        f"{rand_emoji()} Crafting cleaner edges in {topic}.",
        f"{rand_emoji()} Today’s focus: {topic} — momentum over perfection.",
        f"{rand_emoji()} Building, learning, iterating: {topic}.",
        f"{rand_emoji()} Hands-on with {topic} — always optimizing."
    ]
    line = random.choice(bits)
    sig = CONFIG["brand"]["signature_text"]
    tags = " ".join(CONFIG["brand"]["hashtags"])
    return f"{line}\n\n{tags}\n\n{sig}"

def draw_dev_scene(w=1600, h=900, bg1="#0ea5e9", bg2="#111827"):
    # gradient background
    img = Image.new("RGBA", (w, h), bg2)
    overlay = Image.new("RGBA", (w, h))
    od = ImageDraw.Draw(overlay)
    for y in range(h):
        t = y / max(h-1,1)
        # simple vertical gradient
        r1,g1,b1 = ImageColor_getrgb(bg1)
        r2,g2,b2 = ImageColor_getrgb(bg2)
        r = int(r1*(1-t) + r2*t); g=int(g1*(1-t)+g2*t); b=int(b1*(1-t)+b2*t)
        od.line([(0,y),(w,y)], fill=(r,g,b,255))
    img = Image.alpha_composite(img, overlay)

    d = ImageDraw.Draw(img)

    # Futuristic shapes
    for _ in range(20):
        x0 = random.randint(-200, w)
        y0 = random.randint(-200, h)
        x1 = x0 + random.randint(80, 260)
        y1 = y0 + random.randint(40, 180)
        d.ellipse([x0,y0,x1,y1], outline=(255,255,255,30), width=2)

    # "Desk" platform
    d.rectangle([80, h-240, w-80, h-160], fill=(0,0,0,120))
    d.rectangle([140, h-340, w-140, h-240], fill=(255,255,255,15), outline=(255,255,255,40), width=3)

    # Monitor
    mx, my = w//2-260, h-530
    d.rounded_rectangle([mx, my, mx+520, my+320], radius=18, fill=(15,20,35,210), outline=(255,255,255,50), width=3)
    # Code lines
    for i in range(14):
        cx = mx+30
        cy = my+30 + i*20
        lw = random.randint(120, 440)
        d.rounded_rectangle([cx,cy,cx+lw,cy+10], radius=5, fill=(80,200,255,80))

    # Laptop
    lx, ly = 240, h-380
    d.rounded_rectangle([lx, ly, lx+360, ly+220], radius=20, fill=(20,25,40,220), outline=(255,255,255,40), width=2)
    for i in range(8):
        cx = lx+24
        cy = ly+24 + i*20
        lw = random.randint(80, 300)
        d.rounded_rectangle([cx,cy,cx+lw,cy+10], radius=5, fill=(120,220,255,70))

    # Simple, friendly avatar
    ax, ay = w-520, h-460
    # body
    d.ellipse([ax+40, ay+120, ax+260, ay+360], fill=(255,255,255,28), outline=(255,255,255,50))
    # head
    d.ellipse([ax+90, ay+60, ax+210, ay+180], fill=(255,224,189,255))
    # hair
    d.arc([ax+70, ay+40, ax+230, ay+160], 0, 180, fill=(20,20,20,240), width=30)
    # eyes
    d.ellipse([ax+120, ay+110, ax+135, ay+125], fill=(20,20,20,255))
    d.ellipse([ax+165, ay+110, ax+180, ay+125], fill=(20,20,20,255))
    # smile
    d.arc([ax+120, ay+120, ax+180, ay+160], 15, 165, fill=(20,20,20,220), width=4)
    # tablet
    d.rounded_rectangle([ax-40, ay+220, ax+260, ay+320], radius=14, fill=(255,255,255,18), outline=(255,255,255,40))

    return img.convert("RGB")

def ImageColor_getrgb(c):
    from PIL import ImageColor
    return ImageColor.getrgb(c)

def add_signature(img, text):
    d = ImageDraw.Draw(img)
    try:
        # use a generic font available on ubuntu
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except:
        font = ImageFont.load_default()
    w, h = img.size
    tw, th = d.textlength(text, font=font), 40
    pad = 24
    d.rectangle([w - tw - pad*2, h - th - pad, w - pad, h - pad], fill=(0,0,0,120))
    d.text((w - tw - pad*1.5, h - th - pad*1.2), text, fill=(255,255,255), font=font)
    return img

def build():
    ensure_dirs()
    topic = pick_topic()
    line = make_one_liner(topic)
    bg1, bg2 = pick_palette()
    img = draw_dev_scene(bg1=bg1, bg2=bg2)
    img = add_signature(img, CONFIG["brand"]["signature_text"])

    # file naming
    now = datetime.datetime.now(pytz.timezone("Asia/Jerusalem"))
    stamp = now.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(OUT, f"post_{stamp}.jpg")
    txt_path = os.path.join(OUT, f"post_{stamp}.txt")

    img.save(img_path, quality=92)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(line)

    # return metadata
    return {"image": img_path, "text": line, "topic": topic, "stamp": stamp}

def append_logs(meta, status="PREVIEW"):
    exists = os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp","topic","status","image","text"])
        w.writerow([meta["stamp"], meta["topic"], status, os.path.basename(meta["image"]), meta["text"]])
    if not os.path.exists(LOG_MD):
        with open(LOG_MD,"w",encoding="utf-8") as f:
            f.write("# Content Log\n\n")
            f.write("| Timestamp | Topic | Status |\n|---|---|---|\n")
    with open(LOG_MD,"a",encoding="utf-8") as f:
        f.write(f"| {meta['stamp']} | {meta['topic']} | {status} |\n")

if __name__ == "__main__":
    meta = build()
    append_logs(meta, "PREVIEW")
    print(json.dumps(meta, ensure_ascii=False))
