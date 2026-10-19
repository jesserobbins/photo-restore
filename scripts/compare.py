#!/usr/bin/env python3
"""Make a size-matched visual QA sheet for a photo restoration.

Dependency: Pillow >= 9.1. This is a review aid, NOT identity verification.
"""

import argparse
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


def args_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path, help='Unmodified source image')
    parser.add_argument('enhanced', type=Path, help='Restored/upscaled image')
    parser.add_argument('--out', type=Path, default=Path('comparison.png'))
    parser.add_argument('--crop', help='Left,top,right,bottom in ORIGINAL pixel coordinates')
    parser.add_argument('--max-panel', type=int, default=1200,
                        help='Maximum display width of each comparison panel (default 1200)')
    return parser


def crop_box(text, size):
    try:
        vals = tuple(map(int, text.split(',')))
        if len(vals) != 4:
            raise ValueError()
        l, t, r, b = vals
        if not (0 <= l < r <= size[0] and 0 <= t < b <= size[1]):
            raise ValueError()
        return vals
    except ValueError:
        raise SystemExit(f'--crop must be l,t,r,b within original dimensions {size}')


def load(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB').copy()


def label_panel(im, name, width, height):
    panel = Image.new('RGB', (width, height + 54), '#ffffff')
    panel.paste(im, ((width - im.width) // 2, 54 + (height - im.height) // 2))
    d = ImageDraw.Draw(panel)
    d.text((14, 15), name, fill='#111111')
    return panel


def main():
    a = args_parser().parse_args()
    if a.max_panel < 64:
        raise SystemExit('--max-panel must be >= 64')
    src, result = load(a.original), load(a.enhanced)
    source_size, enhanced_size = src.size, result.size
    src_ratio = src.width / src.height
    dst_ratio = result.width / result.height
    if abs(src_ratio / dst_ratio - 1) > 0.005:
        raise SystemExit('Cannot align: source/result aspect ratios differ >0.5%; check for a crop.')

    if a.crop:
        l, t, r, b = crop_box(a.crop, source_size)
        x_scale, y_scale = result.width / src.width, result.height / src.height
        scaled = (round(l*x_scale), round(t*y_scale),
                  round(r*x_scale), round(b*y_scale))
        src = src.crop((l, t, r, b))
        result = result.crop(scaled)

    # Always compare at equal apparent size; Lanczos baseline is not a restoration.
    display_w = min(a.max_panel, max(src.width, result.width))
    display_h = max(1, round(display_w * src.height / src.width))
    display_size = (display_w, display_h)
    source_display = src.resize(display_size, Image.Resampling.LANCZOS)
    enhanced_display = result.resize(display_size, Image.Resampling.LANCZOS)
    # A visual delta is useful for spotting gross drift but not a pass/fail score.
    delta = ImageChops.difference(source_display, enhanced_display)
    delta = delta.point(lambda v: min(255, int(2.5 * v)))
    names = ['SOURCE (Lanczos resize)', 'RESTORED (same apparent size)',
             'AMPLIFIED PIXEL DIFFERENCE (not an identity score)']
    panels = [label_panel(img, name, display_w, display_h)
              for img, name in zip([source_display, enhanced_display, delta], names)]
    out = Image.new('RGB', (display_w*3, display_h+54), 'white')
    for i, p in enumerate(panels):
        out.paste(p, (i * display_w, 0))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out, format='PNG')
    print(f'Saved {a.out} ({out.width}x{out.height})')
    print(f'Original: {source_size}; restored: {enhanced_size}; '
          f'scale = {enhanced_size[0]/source_size[0]:.3f}x by '
          f'{enhanced_size[1]/source_size[1]:.3f}x')
    print('CHECK FACES, EXPRESSION, HANDS AND GEOMETRY VISUALLY. '
          'Pixel differences are NOT identity validation.')


if __name__ == '__main__':
    main()
