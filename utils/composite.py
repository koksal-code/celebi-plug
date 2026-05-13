"""Info-card overlay on top of a static map image.

Pillow is an *optional* dependency. When it is missing, ``compose_card``
returns ``None`` and callers fall back to delivering the raw map PNG
alongside a JSON sidecar.

Install (only if you want composite cards)::

    pip install Pillow
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False


# CelebiPlug palette
_ORANGE = (255, 159, 28, 255)
_BONE = (243, 238, 229, 255)
_INK = (7, 7, 10, 220)


def is_available() -> bool:
    return HAS_PIL


def _load_font(size: int):
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose_card(
    bg: Path,
    *,
    title: str,
    subtitle: str | None = None,
    lines: Sequence[str] = (),
    output: Path | None = None,
) -> Path | None:
    """Draw a CelebiPlug-style info card over ``bg`` and return the path.

    Returns ``None`` if Pillow is not installed or the background can't be
    opened — callers should fall back to delivering ``bg`` + a JSON sidecar.
    """
    if not HAS_PIL:
        return None
    try:
        base = Image.open(bg).convert("RGBA")
    except (OSError, FileNotFoundError):
        return None

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    margin = 24
    pad = 18
    title_font = _load_font(28)
    sub_font = _load_font(15)
    body_font = _load_font(17)

    # Measure
    title_w, title_h = _text_size(draw, title, title_font)
    sub_h = _text_size(draw, subtitle, sub_font)[1] if subtitle else 0
    body_h = len(lines) * 24
    card_w = max(title_w, 280) + pad * 2
    card_h = pad + title_h + (6 + sub_h if subtitle else 0) + 10 + body_h + pad

    # Pin card to bottom-right
    x0 = base.size[0] - card_w - margin
    y0 = base.size[1] - card_h - margin

    # Bracket-cornered translucent panel
    draw.rectangle([x0, y0, x0 + card_w, y0 + card_h], fill=_INK)
    _draw_brackets(draw, x0, y0, card_w, card_h, _ORANGE, length=14, width=2)

    cy = y0 + pad
    draw.text((x0 + pad, cy), title, fill=_ORANGE, font=title_font)
    cy += title_h
    if subtitle:
        cy += 6
        draw.text((x0 + pad, cy), subtitle, fill=_BONE, font=sub_font)
        cy += sub_h
    cy += 10
    for line in lines:
        draw.text((x0 + pad, cy), line, fill=_BONE, font=body_font)
        cy += 24

    composed = Image.alpha_composite(base, layer).convert("RGB")
    out = output or bg.with_name(bg.stem + "-card.png")
    composed.save(out, "PNG")
    return out


def _text_size(draw, text: str | None, font) -> tuple[int, int]:
    if not text:
        return (0, 0)
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return (box[2] - box[0], box[3] - box[1])
    except AttributeError:  # ancient Pillow
        return draw.textsize(text, font=font)


def _draw_brackets(draw, x0, y0, w, h, color, *, length: int = 12, width: int = 2):
    # top-left
    draw.line([x0, y0, x0 + length, y0], fill=color, width=width)
    draw.line([x0, y0, x0, y0 + length], fill=color, width=width)
    # top-right
    draw.line([x0 + w, y0, x0 + w - length, y0], fill=color, width=width)
    draw.line([x0 + w, y0, x0 + w, y0 + length], fill=color, width=width)
    # bottom-left
    draw.line([x0, y0 + h, x0 + length, y0 + h], fill=color, width=width)
    draw.line([x0, y0 + h, x0, y0 + h - length], fill=color, width=width)
    # bottom-right
    draw.line([x0 + w, y0 + h, x0 + w - length, y0 + h], fill=color, width=width)
    draw.line([x0 + w, y0 + h, x0 + w, y0 + h - length], fill=color, width=width)
