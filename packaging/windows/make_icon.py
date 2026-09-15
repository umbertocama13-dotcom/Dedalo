"""Draws the Dedalo icon and saves it as a Windows .ico file (build tool).

Usage: python make_icon.py <output.ico>
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PRIMARY = (31, 95, 191, 255)
WHITE = (255, 255, 255, 255)
# Windows picks the best size for each place (taskbar, desktop, Explorer views).
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw_icon(size: int = 256) -> Image.Image:
    """Draws a blue rounded square with a white labyrinth-like "D".

    Args:
        size: Side of the square image in pixels.

    Returns:
        The RGBA image.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=PRIMARY)

    stroke = size // 11
    left, top, right, bottom = size * 0.26, size * 0.2, size * 0.78, size * 0.8
    # Outer "D": vertical bar plus half ellipse.
    draw.line((left, top, left, bottom), fill=WHITE, width=stroke)
    draw.arc((left - (right - left), top, right, bottom), start=-90, end=90, fill=WHITE, width=stroke)
    draw.line((left, top + stroke / 2, left + (right - left) * 0.05, top + stroke / 2), fill=WHITE, width=stroke)
    draw.line((left, bottom - stroke / 2, left + (right - left) * 0.05, bottom - stroke / 2), fill=WHITE, width=stroke)
    # Inner path, a small labyrinth turn inside the "D".
    inner = stroke * 2.2
    draw.arc(
        (left - (right - left) + inner, top + inner, right - inner, bottom - inner), start=-90, end=60, fill=WHITE, width=stroke
    )
    return image


def main() -> None:
    """Saves the icon to the path given on the command line."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python make_icon.py <output.ico>")
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    draw_icon().save(output, sizes=ICON_SIZES)
    print(f"Icon saved to {output}")


if __name__ == "__main__":
    main()
