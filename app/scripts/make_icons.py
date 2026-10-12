"""Erzeugt die App-Symbole (PNG und SVG) für das Web-App-Manifest.

Motiv: fünf gleichmäßig steigende Balken über einem Zollstock – „gleichmäßig steigend“
über einer Zeitskala. Gelb/Tinte wie das Zeitlineal der App.

Aufruf (einmalig, Ergebnis liegt versioniert in app/public/icons):
    python app/scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

YELLOW = (243, 198, 20, 255)
INK = (22, 25, 29, 255)
OUT = Path(__file__).resolve().parents[1] / "public" / "icons"

# Geometrie in Anteilen der Kantenlänge (liegt vollständig in der Schutzzone maskierbarer Symbole)
BARS = [(0.240, 0.540), (0.348, 0.465), (0.456, 0.390), (0.564, 0.315), (0.672, 0.240)]  # (x links, y oben)
BAR_W = 0.088
BASE_Y = 0.640
TICK_TOP = 0.690
TICKS = 19
TICK_X0, TICK_X1 = 0.240, 0.760


def draw(size: int, *, maskable: bool, rounded: bool) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable or not rounded:
        d.rectangle([0, 0, s, s], fill=YELLOW)
    else:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(0.22 * s), fill=YELLOW)
    for x, top in BARS:
        x0, x1 = int(x * s), int((x + BAR_W) * s)
        d.rounded_rectangle([x0, int(top * s), x1, int(BASE_Y * s)], radius=int(0.018 * s), fill=INK)
    d.rectangle([int(TICK_X0 * s), int(BASE_Y * s), int((TICK_X1 + 0.004) * s), int((BASE_Y + 0.012) * s)], fill=INK)
    for k in range(TICKS):
        x = TICK_X0 + k * (TICK_X1 - TICK_X0) / (TICKS - 1)
        length = 0.075 if k % 6 == 0 else 0.05 if k % 3 == 0 else 0.03
        w = 0.010 if k % 6 == 0 else 0.007
        d.rectangle([int((x - w / 2) * s), int(TICK_TOP * s), int((x + w / 2) * s), int((TICK_TOP + length) * s)], fill=INK)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def svg() -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">',
        '<rect width="512" height="512" rx="112" fill="#f3c614"/>',
    ]
    for x, top in BARS:
        parts.append(f'<rect x="{x * 512:.1f}" y="{top * 512:.1f}" width="{BAR_W * 512:.1f}" height="{(BASE_Y - top) * 512:.1f}" rx="9" fill="#16191d"/>')
    parts.append(f'<rect x="{TICK_X0 * 512:.1f}" y="{BASE_Y * 512:.1f}" width="{(TICK_X1 - TICK_X0 + 0.004) * 512:.1f}" height="6" fill="#16191d"/>')
    for k in range(TICKS):
        x = TICK_X0 + k * (TICK_X1 - TICK_X0) / (TICKS - 1)
        length = 0.075 if k % 6 == 0 else 0.05 if k % 3 == 0 else 0.03
        w = 0.010 if k % 6 == 0 else 0.007
        parts.append(f'<rect x="{(x - w / 2) * 512:.1f}" y="{TICK_TOP * 512:.1f}" width="{w * 512:.1f}" height="{length * 512:.1f}" fill="#16191d"/>')
    parts.append("</svg>")
    return "".join(parts) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192, maskable=False, rounded=True).save(OUT / "icon-192.png", optimize=True)
    draw(512, maskable=False, rounded=True).save(OUT / "icon-512.png", optimize=True)
    draw(192, maskable=True, rounded=False).save(OUT / "maskable-192.png", optimize=True)
    draw(512, maskable=True, rounded=False).save(OUT / "maskable-512.png", optimize=True)
    draw(180, maskable=True, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
    draw(32, maskable=False, rounded=True).save(OUT / "icon-32.png", optimize=True)
    (OUT / "icon.svg").write_text(svg(), encoding="utf-8")
    print("Symbole geschrieben nach", OUT)


if __name__ == "__main__":
    main()
