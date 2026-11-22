"""
Programmatically generates 2 crisp, realistic sample advertisement PNGs inside
backend/sample_assets/ using Pillow:
  1. sample_violation_ad.png — flashy, clashing ad with forbidden ROI guarantee & slang
  2. sample_compliant_ad.png — clean, minimal Apple-inspired enterprise graphic
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent / "sample_assets"

BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

REGULAR_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = BOLD_FONT_CANDIDATES if bold else REGULAR_FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: Tuple[int, int, int] | str,
    stroke_width: int = 0,
    stroke_fill: Tuple[int, int, int] | str | None = None,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        (center_x - w // 2, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return h


def _draw_starburst(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    outer_r: int,
    inner_r: int,
    points: int,
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
) -> None:
    coords = []
    for i in range(points * 2):
        angle = (math.pi * i) / points
        r = outer_r if i % 2 == 0 else inner_r
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(coords, fill=fill, outline=outline)


def generate_violation_ad(output_path: Path) -> Path:
    """Create a loud, clashing violation ad banner."""
    width, height = 1200, 675
    img = Image.new("RGB", (width, height), (255, 22, 84))  # Clashing hot neon crimson
    draw = ImageDraw.Draw(img)

    # Clashing diagonal neon yellow stripes
    for offset in range(-height, width, 110):
        draw.polygon(
            [
                (offset, 0),
                (offset + 48, 0),
                (offset + 48 + height, height),
                (offset + height, height),
            ],
            fill=(255, 238, 0),
        )

    # Harsh magenta center card with thick cyan border
    draw.rounded_rectangle(
        [(70, 62), (width - 70, height - 62)],
        radius=28,
        fill=(210, 0, 145),
        outline=(0, 255, 240),
        width=12,
    )

    # Top flashing urgency ribbon
    draw.rectangle([(100, 95), (width - 100, 165)], fill=(255, 255, 0))
    f_badge = _load_font(34, bold=True)
    _draw_centered_text(
        draw,
        width // 2,
        110,
        "LIMITED TIME!! ACT NOW CUSTOMERS!!",
        f_badge,
        fill=(220, 0, 0),
    )

    # Starburst badge on right
    _draw_starburst(
        draw,
        cx=1030,
        cy=235,
        outer_r=86,
        inner_r=60,
        points=14,
        fill=(0, 255, 102),
        outline=(255, 0, 0),
    )
    f_star = _load_font(22, bold=True)
    _draw_centered_text(draw, 1030, 208, "RISK", f_star, fill=(20, 20, 20))
    _draw_centered_text(draw, 1030, 236, "FREE!!", f_star, fill=(220, 0, 0))

    # Main headline (exact required violation text)
    f_hero = _load_font(62, bold=True)
    _draw_centered_text(
        draw,
        width // 2 - 20,
        212,
        "100% GUARANTEED",
        f_hero,
        fill=(255, 255, 0),
        stroke_width=4,
        stroke_fill=(0, 0, 0),
    )
    _draw_centered_text(
        draw,
        width // 2 - 20,
        300,
        "10X ROI OVERNIGHT!!!",
        f_hero,
        fill=(0, 255, 240),
        stroke_width=4,
        stroke_fill=(0, 0, 0),
    )

    # Low-contrast clashing subtext
    f_sub = _load_font(30, bold=True)
    _draw_centered_text(
        draw,
        width // 2,
        416,
        "Crazy insane profits! Hey guys, get rich fast!",
        f_sub,
        fill=(255, 175, 225),
    )

    # Garish CTA button sized cleanly around text
    draw.rounded_rectangle(
        [(235, 492), (965, 574)],
        radius=41,
        fill=(0, 255, 72),
        outline=(255, 255, 0),
        width=6,
    )
    f_cta = _load_font(32, bold=True)
    _draw_centered_text(
        draw,
        width // 2,
        515,
        "BUY NOW BEFORE IT'S GONE!!!",
        f_cta,
        fill=(200, 0, 0),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def generate_compliant_ad(output_path: Path) -> Path:
    """Create a calm, Apple-clean compliant enterprise graphic."""
    width, height = 1200, 675
    img = Image.new("RGB", (width, height), (251, 251, 253))  # #FBFBFD
    draw = ImageDraw.Draw(img)

    # Subtle elevated card container
    draw.rounded_rectangle(
        [(64, 56), (width - 64, height - 56)],
        radius=32,
        fill=(255, 255, 255),
        outline=(229, 229, 234),
        width=2,
    )

    # Subtle Apple-blue top accent bar
    draw.rounded_rectangle(
        [(112, 108), (192, 116)],
        radius=4,
        fill=(0, 113, 227),  # #0071E3
    )

    # Brand kicker
    f_kicker = _load_font(22, bold=True)
    draw.text((112, 136), "BRANDGUARD ENTERPRISE", font=f_kicker, fill=(0, 113, 227))

    # Main compliant headline
    f_title = _load_font(60, bold=True)
    draw.text((112, 198), "Enterprise Clarity", font=f_title, fill=(29, 29, 31))  # #1D1D1F
    draw.text((112, 272), "for Modern Clients", font=f_title, fill=(29, 29, 31))

    # Calm secondary copy cleanly bounded to left column (never collides with emblem)
    f_body = _load_font(26, bold=False)
    draw.text(
        (112, 368),
        "Consistent governance, measurable quality,",
        font=f_body,
        fill=(110, 110, 115),  # #6E6E73
    )
    draw.text(
        (112, 404),
        "and accessible design built for enterprise teams.",
        font=f_body,
        fill=(110, 110, 115),
    )

    # Clean CTA pill
    draw.rounded_rectangle(
        [(112, 488), (404, 554)],
        radius=33,
        fill=(0, 113, 227),
    )
    f_cta = _load_font(24, bold=True)
    _draw_centered_text(draw, 258, 507, "Request a Briefing", f_cta, fill=(255, 255, 255))

    # Minimal geometric governance emblem cleanly positioned on the right side
    cx, cy = 942, 326
    draw.ellipse(
        [(cx - 116, cy - 116), (cx + 116, cy + 116)],
        fill=(242, 247, 255),
        outline=(214, 231, 252),
        width=2,
    )
    draw.ellipse(
        [(cx - 78, cy - 78), (cx + 78, cy + 78)],
        fill=(255, 255, 255),
        outline=(0, 113, 227),
        width=4,
    )
    # Crisp checkmark inside emblem
    draw.line(
        [(cx - 32, cy + 4), (cx - 8, cy + 28), (cx + 38, cy - 24)],
        fill=(29, 127, 66),
        width=10,
        joint="curve",
    )

    # Verified badge caption centered inside right column with generous margin
    f_cap = _load_font(16, bold=True)
    _draw_centered_text(draw, cx, cy + 138, "ACCESSIBLE CONTRAST · WCAG AA", f_cap, fill=(110, 110, 115))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def ensure_sample_assets(assets_dir: Path | None = None) -> Tuple[Path, Path]:
    target = assets_dir or ASSETS_DIR
    violation_path = generate_violation_ad(target / "sample_violation_ad.png")
    compliant_path = generate_compliant_ad(target / "sample_compliant_ad.png")
    return violation_path, compliant_path


if __name__ == "__main__":
    v_path, c_path = ensure_sample_assets()
    print(f"Generated: {v_path}")
    print(f"Generated: {c_path}")
