#!/usr/bin/env python3
"""Apply the skill's Bayer threshold formula to an actual Blender render.

Requires Pillow 10.1 or newer. No generated-image model is used in this path.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def srgb_decode(value):
    value /= 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def srgb_encode(value):
    encoded = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1.0 / 2.4) - 0.055
    return round(255.0 * min(1.0, max(0.0, encoded)))


def bayer8_rank(x, y):
    """Same 8x8 rank construction as references/mapping-and-shaders.md."""
    rank = 0
    for bit in range(3):
        xb, yb = ((x % 8) >> bit) & 1, ((y % 8) >> bit) & 1
        digit = ((xb ^ yb) << 1) | yb
        rank |= digit << (2 * (2 - bit))
    return rank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('color-render.png'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'assets')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with Image.open(args.input) as source:
        if source.mode == 'RGBA' and source.getextrema()[3] != (255, 255):
            raise ValueError('Composite transparent source pixels before quantization.')
        rgb = source.convert('RGB')

    width, height = rgb.size
    decode = [srgb_decode(i) for i in range(256)]
    # Blender writes an sRGB-encoded display render. Decode it before computing
    # Rec.709 luminance. f(Y)=Y: no additional artistic curve or random noise.
    tones = [0.2126 * decode[r] + 0.7152 * decode[g] + 0.0722 * decode[b]
             for r, g, b in rgb.getdata()]
    gray = Image.new('L', (width, height))
    gray.putdata([srgb_encode(v) for v in tones])

    bits = [255 if v > (bayer8_rank(i % width, i // width) + 0.5) / 64.0 else 0
            for i, v in enumerate(tones)]
    dither = Image.new('L', (width, height))
    dither.putdata(bits)
    gray.save(args.output / 'fruit-vase-grayscale.png')
    dither.save(args.output / 'fruit-vase-bayer8.png')

    # Presentation does not alter the quantized pixels: integer nearest scaling.
    scale, margin, header = 2, 24, 64
    panel = (width * scale, height * scale)
    comparison = Image.new('RGB', (panel[0] * 2 + margin * 3, panel[1] + header + margin), 'white')
    comparison.paste(gray.resize(panel, Image.Resampling.NEAREST).convert('RGB'), (margin, header))
    comparison.paste(dither.resize(panel, Image.Resampling.NEAREST).convert('RGB'), (panel[0] + margin * 2, header))
    draw = ImageDraw.Draw(comparison)
    font = ImageFont.load_default(size=24)
    draw.text((margin, 25), '3D RENDER / GRAYSCALE', fill='black', font=font)
    draw.text((panel[0] + margin * 2, 25), '8 x 8 BAYER / ONE BIT', fill='black', font=font)
    comparison.save(args.output / 'fruit-vase-dithering-example.png')

    print(f'Processed actual render: {args.input} ({width}x{height})')
    print('Pipeline: sRGB decode -> linear Rec.709 luminance -> Bayer threshold -> 0/255')
    print(f'Output values: {sorted(set(bits))}; nearest presentation: {scale}x')
    print(f'Images saved in {args.output}')


if __name__ == '__main__':
    main()
