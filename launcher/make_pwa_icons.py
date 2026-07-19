"""Generate Matevio PWA icons (green knight) into webapp/static/icons/.

Run once on any machine with Pillow; the PNGs are committed and shipped. Uses a
system font that carries the chess knight glyph (Segoe UI Symbol on Windows,
DejaVuSans elsewhere)."""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "webapp", "static", "icons")
os.makedirs(OUT, exist_ok=True)

# brand greens (match the app accent)
TOP = (95, 190, 129)      # #5fbe81
BOT = (47, 125, 77)       # #2f7d4d
GLYPH = "♞"          # ♞ black knight (rendered white)

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguisym.ttf",   # Segoe UI Symbol (Windows) — has chess glyphs
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
    "arialuni.ttf",
]


def _font(size):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        r = int(TOP[0] + (BOT[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOT[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOT[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b, 255)
    return img


def _rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make(size, path, *, rounded=True, glyph_frac=0.70):
    bg = _gradient(size)
    if rounded:
        bg.putalpha(_rounded_mask(size, int(size * 0.22)))
    draw = ImageDraw.Draw(bg)
    font = _font(int(size * glyph_frac))
    # center the glyph using its bounding box
    l, t, r, b = draw.textbbox((0, 0), GLYPH, font=font)
    w, h = r - l, b - t
    x = (size - w) / 2 - l
    y = (size - h) / 2 - t
    # soft shadow then white knight
    draw.text((x, y + size * 0.012), GLYPH, font=font, fill=(0, 0, 0, 60))
    draw.text((x, y), GLYPH, font=font, fill=(255, 255, 255, 255))
    bg.save(path)
    print("wrote", path)


make(512, os.path.join(OUT, "icon-512.png"), rounded=True, glyph_frac=0.70)
make(192, os.path.join(OUT, "icon-192.png"), rounded=True, glyph_frac=0.70)
# maskable: full-bleed square, glyph kept inside the safe zone (~55%)
make(512, os.path.join(OUT, "icon-maskable-512.png"), rounded=False, glyph_frac=0.55)
# apple touch icon: full square (iOS applies its own rounding)
make(180, os.path.join(OUT, "apple-touch-180.png"), rounded=False, glyph_frac=0.70)
make(32, os.path.join(OUT, "favicon-32.png"), rounded=True, glyph_frac=0.72)
print("done")
