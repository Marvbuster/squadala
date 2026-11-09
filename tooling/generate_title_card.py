"""Generate a Zelda-style title card image for the Custom Dungeon landing.

Renders the dungeon name on a parchment-feel background, downscales to
OoT's 96×80 title-card format, plus exports the high-res preview so we
can iterate on the look.

Run:
    python3 tooling/generate_title_card.py "Custom Dungeon"
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# OoT vanilla title cards are 144×24 IA8 — a wide horizontal banner with
# the dungeon name reading across. We render at 8× for crisp text then
# downscale at the end. Verified against e.g. gDekuTreeTitleCardENGTex
# (place_title_cards.xml: Width="144" Height="24" Format="ia8").
SCALE = 8
TARGET_W, TARGET_H = 144, 24
W = TARGET_W * SCALE
H = TARGET_H * SCALE

# Pick a serif font that reads as fantasy / vintage. Fallback hierarchy
# in case the preferred one isn't installed.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Bodoni 72 Smallcaps Book.ttf",
    "/System/Library/Fonts/Supplemental/Trajan.ttc",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    "/System/Library/Fonts/Times New Roman.ttf",
]


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def render_title_card(name: str, out_png: Path) -> None:
    # Parchment gradient — dark golden brown bleeding to lighter cream in
    # the middle, vignetted to black at the corners. Reads as a torn page
    # in candlelight.
    bg = Image.new("RGB", (W, H), (24, 18, 10))
    grad = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grad)
    cx, cy = W // 2, H // 2
    max_r = (cx * cx + cy * cy) ** 0.5
    for y in range(H):
        for x in range(0, W, 4):   # stride for speed
            dx, dy = x - cx, y - cy
            d = (dx * dx + dy * dy) ** 0.5
            v = max(0, 255 - int(255 * (d / max_r) ** 1.4))
            gd.rectangle([x, y, x + 4, y + 1], fill=v)
    grad = grad.filter(ImageFilter.GaussianBlur(radius=10))
    parchment = Image.merge("RGB", (
        grad.point(lambda v: int(140 + 0.45 * v)),  # R
        grad.point(lambda v: int(105 + 0.40 * v)),  # G
        grad.point(lambda v: int(50  + 0.30 * v)),  # B
    ))
    img = Image.composite(parchment, bg, grad)

    # Border — subtle dark frame inset from the edge.
    draw = ImageDraw.Draw(img)
    border_pad = 8 * SCALE // 2
    draw.rectangle(
        [border_pad, border_pad, W - border_pad - 1, H - border_pad - 1],
        outline=(40, 22, 8), width=max(2, SCALE),
    )
    # Inner highlight
    draw.rectangle(
        [border_pad + 2, border_pad + 2,
         W - border_pad - 3, H - border_pad - 3],
        outline=(180, 150, 100), width=1,
    )

    # Title text — fit to width with auto-shrink.
    target_w = W - 4 * border_pad
    size = int(H * 0.5)
    while size > 8:
        font = pick_font(size)
        tw = draw.textlength(name, font=font)
        if tw <= target_w:
            break
        size -= 1
    th_bbox = draw.textbbox((0, 0), name, font=font)
    th = th_bbox[3] - th_bbox[1]
    tx = (W - tw) // 2
    ty = (H - th) // 2 - th_bbox[1]
    # Shadow then text
    draw.text((tx + 2, ty + 2), name, fill=(20, 10, 0), font=font)
    draw.text((tx, ty), name, fill=(240, 220, 160), font=font)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    # High-res preview
    img.save(out_png)
    # Down-scaled to OoT title-card dimensions (144×24 IA8).
    small = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    small_path = out_png.with_suffix(f".{TARGET_W}x{TARGET_H}.png")
    small.save(small_path)
    print(f"Wrote {out_png} ({W}×{H})")
    print(f"Wrote {small_path} ({TARGET_W}×{TARGET_H} — OoT title-card size)")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Custom Dungeon"
    out_dir = Path(__file__).parent.parent / "_raw_data" / "title_cards"
    safe = name.lower().replace(" ", "_")
    render_title_card(name, out_dir / f"{safe}.png")

    # Also emit an IA8 C header that SoH can include directly. The vanilla
    # title-card system expects a 96×80 IA8 texture (4-bit intensity +
    # 4-bit alpha packed into one byte per pixel). We feed it the
    # downscaled image and pack each pixel.
    small = Image.open(out_dir / f"{safe}.{TARGET_W}x{TARGET_H}.png").convert("LA")
    header_path = (Path(__file__).parent / "assets" / "title_cards"
                   / f"{safe}_ia8.h")
    header_path.parent.mkdir(parents=True, exist_ok=True)
    pixels = list(small.getdata())   # list of (intensity, alpha)
    ia8_bytes = bytearray()
    for intensity, alpha in pixels:
        ia8_bytes.append(((intensity & 0xF0) | (alpha >> 4)) & 0xFF)
    expected = TARGET_W * TARGET_H
    assert len(ia8_bytes) == expected, f"unexpected IA8 size {len(ia8_bytes)}"

    sym = f"k{''.join(part.capitalize() for part in name.split())}TitleCardIA8"
    lines = [
        "// Auto-generated by tooling/generate_title_card.py — do not edit.",
        f"// Source: {out_dir / f'{safe}.{TARGET_W}x{TARGET_H}.png'}",
        "#pragma once",
        "#include <cstdint>",
        "",
        f"static constexpr int {sym}Width  = {TARGET_W};",
        f"static constexpr int {sym}Height = {TARGET_H};",
        f"static constexpr uint8_t {sym}[{expected}] = {{",
    ]
    for i in range(0, len(ia8_bytes), 16):
        chunk = ", ".join(f"0x{b:02x}" for b in ia8_bytes[i:i + 16])
        lines.append(f"    {chunk},")
    lines.append("};")
    header_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {header_path}  ({len(ia8_bytes)} IA8 bytes → {sym})")
