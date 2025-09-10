# overlays.py
import random, math
from typing import Tuple
from PIL import Image, ImageDraw

RGBA = Tuple[int, int, int, int]

def _mix(a: Tuple[int,int,int], b: Tuple[int,int,int], t: float) -> Tuple[int,int,int]:
    return (int(a[0]*(1-t)+b[0]*t), int(a[1]*(1-t)+b[1]*t), int(a[2]*(1-t)+b[2]*t))

def _to_rgba(rgb: Tuple[int,int,int], alpha: int) -> RGBA:
    return (rgb[0], rgb[1], rgb[2], alpha)

def _hex_to_rgb(h: str) -> Tuple[int,int,int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore

def _stroke(draw: ImageDraw.ImageDraw, shape, outline: RGBA, width: int = 3, fill=None, radius: int = 0):
    if radius > 0 and isinstance(shape, (list, tuple)) and len(shape) == 4:
        draw.rounded_rectangle(shape, radius=radius, outline=outline, width=width, fill=fill)
    else:
        if isinstance(shape, (list, tuple)) and len(shape) == 4 and fill is not None:
            draw.rectangle(shape, outline=outline, width=width, fill=fill)
        else:
            draw.rectangle(shape, outline=outline, width=width)

# ---------- Individual overlay primitives (no text) ----------

def phone_frame(img, accent_rgb, alpha=220):
    """Draw a big rounded phone outline."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    phone_w, phone_h = int(w*0.32), int(h*0.62)
    x = int(w*0.16)
    y = int(h*0.18)
    radius = int(min(phone_w, phone_h)*0.08)

    outer = [x, y, x+phone_w, y+phone_h]
    inner = [x+10, y+10, x+phone_w-10, y+phone_h-10]

    d.rounded_rectangle(outer, radius=radius, outline=_to_rgba(accent_rgb, alpha), width=6)
    d.rounded_rectangle(inner, radius=radius-8, outline=_to_rgba(accent_rgb, int(alpha*0.7)), width=2)

    # small camera notch
    notch_w, notch_h = int(phone_w*0.28), 10
    nx = x + phone_w//2 - notch_w//2
    ny = y + 18
    d.rectangle([nx, ny, nx+notch_w, ny+notch_h], fill=_to_rgba(accent_rgb, int(alpha*0.7)))

def mini_crane(img, accent_rgb, alpha=200):
    """Simple isometric crane near the phone—playful construction vibe."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    base_x = int(w*0.58)
    base_y = int(h*0.22)
    height = int(h*0.48)
    arm = int(w*0.18)

    col = _to_rgba(accent_rgb, alpha)
    # mast
    for i in range(0, height, 24):
        d.line([(base_x, base_y+i), (base_x, base_y+i+18)], fill=col, width=3)
        d.line([(base_x-10, base_y+i+9), (base_x+10, base_y+i+9)], fill=col, width=3)

    # arm
    d.line([(base_x, base_y), (base_x+arm, base_y)], fill=col, width=5)
    d.line([(base_x+arm, base_y), (base_x+arm-20, base_y+14)], fill=col, width=3)
    # cable + hook
    d.line([(base_x+arm-20, base_y+14), (base_x+arm-20, base_y+100)], fill=col, width=2)
    d.arc([base_x+arm-30, base_y+100, base_x+arm-10, base_y+120], 180, 360, fill=col, width=3)

def gear(img, cx, cy, r, teeth, accent_rgb, alpha=180, width=3):
    """Simple gear outline."""
    d = ImageDraw.Draw(img, "RGBA")
    col = _to_rgba(accent_rgb, alpha)
    # outer circle
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=width)
    # teeth
    for k in range(teeth):
        a = (2*math.pi/teeth)*k
        x1 = cx + int(r*0.82*math.cos(a))
        y1 = cy + int(r*0.82*math.sin(a))
        x2 = cx + int(r*math.cos(a))
        y2 = cy + int(r*math.sin(a))
        d.line([(x1,y1),(x2,y2)], fill=col, width=width)

    # inner hole
    d.ellipse([cx-int(r*0.35), cy-int(r*0.35), cx+int(r*0.35), cy+int(r*0.35)], outline=col, width=width)

def wrench(img, x, y, length, accent_rgb, alpha=180, width=4):
    """Minimal wrench outline."""
    d = ImageDraw.Draw(img, "RGBA")
    col = _to_rgba(accent_rgb, alpha)
    # handle
    d.line([(x, y), (x+length, y)], fill=col, width=width)
    # head
    d.arc([x+length-10, y-10, x+length+10, y+10], 330, 150, fill=col, width=width)

def build_guides(img, accent_rgb, alpha=110):
    """Dotted assembly guides around the focal area."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    m = 96
    col = _to_rgba(accent_rgb, alpha)
    # dotted rectangle
    for x in range(m, w-m, 16):
        d.line([(x, m), (x+8, m)], fill=col, width=2)
        d.line([(x, h-m), (x+8, h-m)], fill=col, width=2)
    for y in range(m, h-m, 16):
        d.line([(m, y), (m, y+8)], fill=col, width=2)
        d.line([(w-m, y), (w-m, y+8)], fill=col, width=2)

# ---------- Public API ----------

def apply_overlays(img, palette_hex):
    """
    Adds mobile-dev construction vibes without text or logos.
    Palette hex -> choose accent for strokes that contrasts with bg.
    """
    p1 = _hex_to_rgb(palette_hex[0])
    p2 = _hex_to_rgb(palette_hex[1])
    # choose a bright-ish accent between p1 & white, to lift line art over bg
    accent = _mix(p1, (255,255,255), 0.35)

    # Always add subtle guides
    build_guides(img, accent)

    # Random choice of 2-3 elements for variety
    choices = [phone_frame, mini_crane, lambda i,a: gear(i, int(i.size[0]*0.78), int(i.size[1]*0.65), 48, 10, a),
               lambda i,a: wrench(i, int(i.size[0]*0.62), int(i.size[1]*0.76), 120, a)]
    random.shuffle(choices)
    how_many = random.choice([2,3])

    for fn in choices[:how_many]:
        # lambdas have (img, accent) signature, named have (img, accent_rgb)
        try:
            fn(img, accent)  # type: ignore
        except TypeError:
            fn(img, accent)  # type: ignore

    return img
