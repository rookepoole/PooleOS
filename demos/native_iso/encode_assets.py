"""Encode approved raster art and licensed type into bounded firmware data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

ASSETS = Path(__file__).resolve().parent / "boot/assets"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    source = ASSETS / "pooleglass-emblem.png"
    original = Image.open(source).convert("RGB")
    indexed = original.resize((192, 192), Image.Resampling.LANCZOS).quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    encoded = {"emblem.index8": indexed.tobytes(), "emblem.rgb": bytes(indexed.getpalette()[:768])}
    for name, text, size, dimensions in (("title", "PooleOS", 40, (192, 48)),
                                          ("caption", "Native engineering preview", 13, (224, 20))):
        font = ImageFont.truetype(str(args.font), size)
        mask = Image.new("L", dimensions)
        draw = ImageDraw.Draw(mask)
        box = draw.textbbox((0, 0), text, font=font)
        width, height = box[2] - box[0], box[3] - box[1]
        if width > dimensions[0] or height > dimensions[1]:
            raise ValueError("Text does not fit its fixed atlas")
        draw.text(((dimensions[0] - width) // 2 - box[0], (dimensions[1] - height) // 2 - box[1]), text, font=font, fill=255)
        pixels = [(value + 8) // 17 for value in mask.tobytes()]
        encoded[f"{name}.alpha4"] = bytes((a << 4) | b for a, b in zip(pixels[::2], pixels[1::2], strict=True))
    for name, data in encoded.items():
        (ASSETS / name).write_bytes(data)
    inputs = {"pooleglass-emblem.png": source.read_bytes(), "Vera.ttf": args.font.read_bytes()}
    receipt = {"pillow_version": pillow_version, "purpose": "technical_asset_encoding_not_art_generation",
               "source": {name: hashlib.sha256(data).hexdigest().upper() for name, data in inputs.items()},
               "encoded": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper()} for name, data in encoded.items()}}
    (ASSETS / "encoding.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="ascii", newline="\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
