"""App icon, drawn in code so the tray can recolor it by state and the build can export a .ico."""

import sys

from PIL import Image, ImageDraw

ACTIVE = "#1E5EFF"
WAITING = "#7A7A7A"
PROBLEM = "#D93025"

_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def make_icon(size: int = 64, color: str = ACTIVE) -> Image.Image:
    """A white microphone on a colored circle."""
    scale = 4  # draw large and downsample for smooth edges
    s = size * scale
    u = s / 64  # design units: the icon is laid out on a 64x64 grid
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=color)
    line = round(3.5 * u)
    d.rounded_rectangle((25 * u, 11 * u, 39 * u, 37 * u), radius=7 * u, fill="white")
    d.arc((18 * u, 19 * u, 46 * u, 45 * u), start=0, end=180, fill="white", width=line)
    d.line((32 * u, 45 * u, 32 * u, 52 * u), fill="white", width=line)
    d.line((24 * u, 52 * u, 40 * u, 52 * u), fill="white", width=line)
    return img.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    # Used by the Windows build: python -m pmtpc.icon out.ico
    make_icon(256).save(sys.argv[1], sizes=_ICO_SIZES)
