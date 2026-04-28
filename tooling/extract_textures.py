"""Extract textures from SoH .o2r archives as PNG files.

The .o2r format is a ZIP containing binary OTEX resources.
OTEX header (little-endian):
  0x00: 4 bytes padding
  0x04: 4 bytes magic "XETO" (OTEX reversed)
  0x40: 1 byte  texture format (4=CI8, 0=RGBA32, 1=RGBA16, etc.)
  0x44: 4 bytes width (LE uint32)
  0x48: 4 bytes height (LE uint32)
  0x50: pixel data starts

For CI8 textures, we also need the TLUT (palette) from a matching *TLUT entry.
For RGBA16/RGBA32, pixel data is direct.
"""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path

from PIL import Image

# N64 texture format IDs used in SoH
TEX_RGBA32 = 0
TEX_RGBA16 = 1  # 5551
TEX_CI8 = 4
TEX_CI4 = 5
TEX_IA16 = 2
TEX_IA8 = 3
TEX_I8 = 6
TEX_I4 = 7
TEX_IA4 = 8


def read_otex_header(data: bytes) -> tuple[int, int, int]:
    """Return (format, width, height) from OTEX binary."""
    fmt = data[0x40]
    w = struct.unpack("<I", data[0x44:0x48])[0]
    h = struct.unpack("<I", data[0x48:0x4C])[0]
    return fmt, w, h


def rgba16_to_rgba32(pixel: int) -> tuple[int, int, int, int]:
    """Convert N64 RGBA5551 to RGBA8888."""
    r = ((pixel >> 11) & 0x1F) * 255 // 31
    g = ((pixel >> 6) & 0x1F) * 255 // 31
    b = ((pixel >> 1) & 0x1F) * 255 // 31
    a = 255 if (pixel & 1) else 0
    return r, g, b, a


def decode_rgba32(data: bytes, w: int, h: int) -> Image.Image:
    """Decode RGBA32 texture."""
    pixels = data[0x50:]
    img = Image.frombytes("RGBA", (w, h), pixels[:w * h * 4])
    return img


def decode_rgba16(data: bytes, w: int, h: int) -> Image.Image:
    """Decode RGBA16 (5551) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            offset = (y * w + x) * 2
            if offset + 2 > len(pixels):
                break
            pixel = struct.unpack(">H", pixels[offset:offset + 2])[0]
            img.putpixel((x, y), rgba16_to_rgba32(pixel))
    return img


def decode_ci8(data: bytes, w: int, h: int, tlut_data: bytes | None) -> Image.Image:
    """Decode CI8 (color-indexed, 8-bit) texture with TLUT palette."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))

    palette = []
    if tlut_data and len(tlut_data) > 0x50:
        tlut_pixels = tlut_data[0x50:]
        for i in range(0, min(512, len(tlut_pixels)), 2):
            pixel = struct.unpack(">H", tlut_pixels[i:i + 2])[0]
            palette.append(rgba16_to_rgba32(pixel))

    for y in range(h):
        for x in range(w):
            idx = pixels[y * w + x] if (y * w + x) < len(pixels) else 0
            if idx < len(palette):
                img.putpixel((x, y), palette[idx])
            else:
                img.putpixel((x, y), (0, 0, 0, 255))
    return img


def decode_ia16(data: bytes, w: int, h: int) -> Image.Image:
    """Decode IA16 (intensity 8bit + alpha 8bit) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            offset = (y * w + x) * 2
            if offset + 2 > len(pixels):
                break
            intensity = pixels[offset]
            alpha = pixels[offset + 1]
            img.putpixel((x, y), (intensity, intensity, intensity, alpha))
    return img


def decode_ci4(data: bytes, w: int, h: int, tlut_data: bytes | None) -> Image.Image:
    """Decode CI4 (color-indexed, 4-bit) texture with TLUT palette."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))

    palette = []
    if tlut_data and len(tlut_data) > 0x50:
        tlut_pixels = tlut_data[0x50:]
        for i in range(0, min(32, len(tlut_pixels)), 2):
            pixel = struct.unpack(">H", tlut_pixels[i:i + 2])[0]
            palette.append(rgba16_to_rgba32(pixel))

    for y in range(h):
        for x in range(w):
            byte_offset = (y * w + x) // 2
            if byte_offset >= len(pixels):
                break
            if (y * w + x) % 2 == 0:
                idx = (pixels[byte_offset] >> 4) & 0xF
            else:
                idx = pixels[byte_offset] & 0xF
            if idx < len(palette):
                img.putpixel((x, y), palette[idx])
            else:
                img.putpixel((x, y), (0, 0, 0, 255))
    return img


def decode_i4(data: bytes, w: int, h: int) -> Image.Image:
    """Decode I4 (4-bit intensity) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            byte_offset = (y * w + x) // 2
            if byte_offset >= len(pixels):
                break
            if (y * w + x) % 2 == 0:
                val = ((pixels[byte_offset] >> 4) & 0xF) * 255 // 15
            else:
                val = (pixels[byte_offset] & 0xF) * 255 // 15
            img.putpixel((x, y), (val, val, val, 255))
    return img


def decode_ia4(data: bytes, w: int, h: int) -> Image.Image:
    """Decode IA4 (intensity 3bit + alpha 1bit, packed in nibbles) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            byte_offset = (y * w + x) // 2
            if byte_offset >= len(pixels):
                break
            if (y * w + x) % 2 == 0:
                nibble = (pixels[byte_offset] >> 4) & 0xF
            else:
                nibble = pixels[byte_offset] & 0xF
            intensity = ((nibble >> 1) & 0x7) * 255 // 7
            alpha = 255 if (nibble & 1) else 0
            img.putpixel((x, y), (intensity, intensity, intensity, alpha))
    return img


def decode_ia8(data: bytes, w: int, h: int) -> Image.Image:
    """Decode IA8 (intensity + alpha, 4+4 bit) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            offset = y * w + x
            if offset >= len(pixels):
                break
            val = pixels[offset]
            intensity = ((val >> 4) & 0xF) * 255 // 15
            alpha = (val & 0xF) * 255 // 15
            img.putpixel((x, y), (intensity, intensity, intensity, alpha))
    return img


def decode_i8(data: bytes, w: int, h: int) -> Image.Image:
    """Decode I8 (8-bit intensity) texture."""
    pixels = data[0x50:]
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            offset = y * w + x
            if offset >= len(pixels):
                break
            val = pixels[offset]
            img.putpixel((x, y), (val, val, val, 255))
    return img


def extract_textures(
    o2r_path: str,
    filter_pattern: str,
    output_dir: str,
) -> list[Path]:
    """Extract matching textures from an .o2r file as PNGs."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    extracted = []

    with zipfile.ZipFile(o2r_path, "r") as z:
        names = z.namelist()
        # Build TLUT lookup
        tlut_map: dict[str, bytes] = {}
        for n in names:
            if "TLUT" in n:
                tlut_map[n] = z.read(n)

        # Find matching texture entries
        tex_entries = [
            n for n in names
            if filter_pattern.lower() in n.lower() and "Tex" in n
        ]

        for entry in tex_entries:
            data = z.read(entry)
            if len(data) < 0x50:
                continue

            fmt, w, h = read_otex_header(data)
            if w == 0 or h == 0 or w > 4096 or h > 4096:
                print(f"  SKIP {entry}: invalid size {w}x{h}")
                continue

            # Find matching TLUT
            base_name = entry.replace("Tex", "TLUT").replace("_static/", "_pal_static/")
            tlut = tlut_map.get(base_name)

            try:
                if fmt == TEX_RGBA32:
                    img = decode_rgba32(data, w, h)
                elif fmt == TEX_RGBA16:
                    img = decode_rgba16(data, w, h)
                elif fmt == TEX_CI8:
                    img = decode_ci8(data, w, h, tlut)
                elif fmt == TEX_CI4:
                    img = decode_ci4(data, w, h, tlut)
                elif fmt == TEX_IA16:
                    img = decode_ia16(data, w, h)
                elif fmt == TEX_IA8:
                    img = decode_ia8(data, w, h)
                elif fmt == TEX_IA4:
                    img = decode_ia4(data, w, h)
                elif fmt == TEX_I8:
                    img = decode_i8(data, w, h)
                elif fmt == TEX_I4:
                    img = decode_i4(data, w, h)
                else:
                    print(f"  SKIP {entry}: unsupported format {fmt}")
                    continue

                safe_name = entry.replace("/", "_").replace(" ", "_")
                png_path = out / f"{safe_name}.png"
                img.save(png_path)
                extracted.append(png_path)
                print(f"  OK   {w:>4}x{h:<4} fmt={fmt} → {png_path.name}")
            except Exception as e:
                print(f"  ERR  {entry}: {e}")

    return extracted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract textures from SoH .o2r files")
    parser.add_argument("o2r", help="Path to .o2r file")
    parser.add_argument("--filter", "-f", default="", help="Filter pattern (e.g. 'LinksHouse', 'kokiri')")
    parser.add_argument("--output", "-o", default="./extracted_textures", help="Output directory")
    args = parser.parse_args()

    print(f"Extracting from {args.o2r} (filter: '{args.filter}')")
    results = extract_textures(args.o2r, args.filter, args.output)
    print(f"\nExtracted {len(results)} textures")
