"""Regenerate packaging/windows/icon.ico and packaging/macos/icon.icns from code.

Usage: python packaging/make_icons.py   (needs Pillow; output is committed)
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SIZE = 1024


def _arrow(draw: ImageDraw.ImageDraw, y: int, right: bool) -> None:
    """A thick horizontal arrow across the middle of the icon."""
    left, rightx, half = 250, 774, 46
    head = 150
    if right:
        draw.rectangle((left, y - half, rightx - head + 10, y + half), fill="white")
        draw.polygon([(rightx - head, y - 120), (rightx, y), (rightx - head, y + 120)],
                     fill="white")
    else:
        draw.rectangle((left + head - 10, y - half, rightx, y + half), fill="white")
        draw.polygon([(left + head, y - 120), (left, y), (left + head, y + 120)], fill="white")


def render() -> Image.Image:
    top, bottom = (59, 130, 246), (20, 184, 166)  # blue to teal
    grad = Image.new("RGB", (SIZE, SIZE))
    gd = ImageDraw.Draw(grad)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        gd.line([(0, y), (SIZE, y)],
                fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    mask = Image.new("L", (SIZE, SIZE), 0)
    # macOS icon grid: ~10% margin, ~22% corner radius
    ImageDraw.Draw(mask).rounded_rectangle((100, 100, 924, 924), radius=185, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(icon)
    _arrow(draw, 400, right=True)
    _arrow(draw, 624, right=False)
    return icon


def main() -> None:
    icon = render()
    (HERE / "windows").mkdir(exist_ok=True)
    (HERE / "macos").mkdir(exist_ok=True)
    icon.save(HERE / "windows" / "icon.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save(HERE / "macos" / "icon.icns")
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(HERE / "icon-256.png")


if __name__ == "__main__":
    main()
