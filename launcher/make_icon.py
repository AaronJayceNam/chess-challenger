"""Generate the Chess Coach app icon (chesscoach.ico).

Draws a rounded green board-tile background with a white knight glyph, exported
as a multi-size Windows .ico. Run:  python launcher/make_icon.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chesscoach.ico")
SIZE = 256
BG1 = (115, 149, 82)     # chess green
BG2 = (96, 128, 64)      # darker green (checker accent)
GLYPH = "♞"         # ♞ black chess knight (solid)


def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def make() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded board background
    rounded(d, (8, 8, SIZE - 8, SIZE - 8), 46, BG1)
    # subtle checker: two darker tiles
    tile = (SIZE - 16) / 4
    for (cx, cy) in [(1, 0), (3, 0), (0, 1), (2, 1), (1, 2), (3, 2), (0, 3), (2, 3)]:
        x0 = 8 + cx * tile
        y0 = 8 + cy * tile
        d.rectangle((x0, y0, x0 + tile, y0 + tile), fill=BG2)
    # re-round corners by overpainting outside the radius with transparency mask
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=46, fill=255)
    img.putalpha(mask)

    # knight glyph centered
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", 170)
    bbox = d.textbbox((0, 0), GLYPH, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1] - 6)
    # shadow + white knight
    d.text((pos[0] + 4, pos[1] + 4), GLYPH, font=font, fill=(0, 0, 0, 120))
    d.text(pos, GLYPH, font=font, fill=(250, 250, 250, 255))
    return img


def main():
    img = make()
    img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
