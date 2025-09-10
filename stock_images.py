# stock_images.py
import os, io, random, re
from urllib.parse import quote_plus
import requests
from PIL import Image

USER_AGENT = "MaromLinkedInPoster/1.0 (+github-actions)"

TOPIC_HINTS = [
    # (pattern, list of search keywords)
    (r"\bFlutter\b|\bnavigation\b|GoRouter", ["flutter ui", "mobile app interface", "developer at laptop"]),
    (r"\bIsar\b|\bRealm\b|\boffline\b|\bsync\b", ["mobile offline sync", "database developer", "phone cloud"]),
    (r"\bDio\b|\bretry\b|\bAPI\b", ["api dashboard", "backend developer desk", "network cables abstract"]),
    (r"\bMaps\b|\bgeocoding\b|\blocation\b|\bUX\b", ["maps on phone", "gps interface", "city map flatlay"]),
    (r"\bMVVM\b|\bProvider\b|\bGetIt\b|architecture", ["software architecture whiteboard", "clean code diagram"]),
    (r"\bperformance\b|\bframe\b", ["performance dashboard", "profiling graphs", "speed abstract"]),
    (r"\bobservability\b|\bcrash\b", ["logs monitoring", "error tracking dashboard", "developer observability"]),
    (r"\bCI/CD\b|\brelease\b|\bpipeline\b", ["ci cd pipeline", "devops desk", "automated deploy"]),
]

def _pick_keywords(topic: str):
    for pat, keys in TOPIC_HINTS:
        if re.search(pat, topic, flags=re.IGNORECASE):
            return keys
    # default fallbacks
    return ["mobile app developer", "clean minimal desk", "programmer workspace"]

def _center_crop(im: Image.Image, tw: int, th: int) -> Image.Image:
    w, h = im.size
    scale = max(tw / w, th / h)
    im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    w, h = im.size
    x = max(0, (w - tw) // 2)
    y = max(0, (h - th) // 2)
    return im.crop((x, y, x + tw, y + th))

# ---------- Pexels (FREE key) ----------
def try_pexels(topic: str, out_path: str, target_size=(1600,900)) -> bool:
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return False
    query = random.choice(_pick_keywords(topic))
    url = f"https://api.pexels.com/v1/search?query={quote_plus(query)}&per_page=40&orientation=landscape"
    r = requests.get(url, headers={"Authorization": api_key, "User-Agent": USER_AGENT}, timeout=25)
    if r.status_code != 200:
        return False
    data = r.json()
    photos = data.get("photos", [])
    if not photos:
        return False
    pick = random.choice(photos)
    src = pick.get("src", {}).get("large") or pick.get("src", {}).get("original")
    if not src:
        return False
    img_r = requests.get(src, headers={"User-Agent": USER_AGENT}, timeout=25)
    img_r.raise_for_status()
    im = Image.open(io.BytesIO(img_r.content)).convert("RGB")
    im = _center_crop(im, target_size[0], target_size[1])
    im.save(out_path, quality=95, subsampling=0)
    return True

# ---------- Openverse (NO key) ----------
def try_openverse(topic: str, out_path: str, target_size=(1600,900)) -> bool:
    query = random.choice(_pick_keywords(topic))
    url = (
        "https://api.openverse.engineering/v1/images/"
        f"?q={quote_plus(query)}&license_type=commercial&extensions=jpg&size=large&field_set=ids"
    )
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
    if r.status_code != 200:
        return False
    data = r.json()
    results = data.get("results", [])
    if not results:
        return False
    # fetch details to get URL
    pick = random.choice(results)
    detail_url = f"https://api.openverse.engineering/v1/images/{pick['id']}/"
    dr = requests.get(detail_url, headers={"User-Agent": USER_AGENT}, timeout=25)
    if dr.status_code != 200:
        return False
    src = dr.json().get("url")
    if not src:
        return False
    img_r = requests.get(src, headers={"User-Agent": USER_AGENT}, timeout=30)
    if img_r.status_code != 200:
        return False
    im = Image.open(io.BytesIO(img_r.content)).convert("RGB")
    im = _center_crop(im, target_size[0], target_size[1])
    im.save(out_path, quality=95, subsampling=0)
    return True
