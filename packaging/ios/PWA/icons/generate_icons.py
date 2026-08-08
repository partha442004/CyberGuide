"""Generate PWA icons (192/512/180) for the CyberGuide dashboard.

Requires Pillow:  python -m pip install pillow
Usage:           python generate_icons.py
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required: python -m pip install pillow") from exc

HERE = Path(__file__).resolve().parent
SIZES = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background (top-left #667eea -> bottom-right #764ba2)
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(0x66 + (0x76 - 0x66) * t)
        g = int(0x7E + (0x4B - 0x7E) * t)
        b = int(0xEA + (0xA2 - 0xEA) * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Rounded corners
    radius = int(size * 0.22)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)

    # Simple "shield" glyph in white
    cx, cy = size / 2, size * 0.46
    w, h = size * 0.42, size * 0.46
    shield = [
        (int(cx), int(cy - h / 2)),
        (int(cx + w / 2), int(cy - h / 3)),
        (int(cx + w / 2), int(cy + h / 6)),
        (int(cx), int(cy + h / 2)),
        (int(cx - w / 2), int(cy + h / 6)),
        (int(cx - w / 2), int(cy - h / 3)),
    ]
    draw.polygon(shield, fill=(255, 255, 255, 245))

    # Check mark (int coordinates/width for PIL)
    sw = max(3, int(size * 0.045))
    p1 = (int(cx - w * 0.22), int(cy + h * 0.02))
    p2 = (int(cx - w * 0.04), int(cy + h * 0.18))
    p3 = (int(cx + w * 0.26), int(cy - h * 0.18))
    draw.line([p1, p2], fill=(0, 0, 0, 0), width=sw)
    draw.line([p2, p3], fill=(255, 255, 255, 255), width=sw)
    return img


def main() -> None:
    for name, size in SIZES.items():
        out = HERE / name
        make_icon(size).save(out, "PNG")
        print(f"OK {out.name} ({size}x{size})")


if __name__ == "__main__":
    main()
