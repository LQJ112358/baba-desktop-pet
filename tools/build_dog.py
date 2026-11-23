"""Build the fallback body: the person's head on a small crawling dog.

Only the character + the requested "爸爸" bubble. No clothes, no props.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_final as F

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "assets" / "sprites"

FUR = (198, 201, 206)
FUR_HI = (226, 228, 232)
FUR_LO = (163, 167, 174)
CREAM = (244, 237, 225)
CREAM_HI = (255, 251, 243)
INK = (98, 96, 98)
PAW = (247, 241, 230)
PAW_LO = (204, 198, 186)


def head_image():
    src = Image.open(ROOT / "assets" / "head_nohood.png").convert("RGBA")
    h = src.resize((int(64 * F.K), int(89 * F.K)), Image.LANCZOS)
    return h.transpose(Image.FLIP_LEFT_RIGHT)


def fur_ruff(d, by=0.0):
    spots = [
        (172, 120, 6.5), (180, 114, 7), (189, 112, 7), (198, 114, 6.5),
        (205, 120, 6), (207, 127, 5), (202, 133, 5), (194, 136, 5),
        (186, 135, 5), (179, 132, 5), (173, 127, 5.5),
    ]
    for x, y, r in spots:
        F.ellipse(d, (x - r, y + by - r, x + r, y + by + r), fill=CREAM)
    for i, (x, y, r) in enumerate(spots):
        if i % 2 == 0:
            F.ellipse(d, (x - r * 0.55, y + by - r * 0.6, x + r * 0.55, y + by + r * 0.35),
                      fill=CREAM_HI)
    # a couple of darker fur wisps so it reads as a mane, not a necklace
    for x, y, r in [(176, 124, 3.0), (190, 130, 3.2), (201, 124, 2.8)]:
        F.ellipse(d, (x - r, y + by - r, x + r, y + by + r), fill=FUR_HI)


def render(head, phase, mode):
    layer = Image.new("RGBA", (F.CW, F.CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    if mode == "crawl":
        t = phase / 8.0 * math.tau
        swing = math.sin(t)
        bob = -1.8 * abs(math.sin(t))
        tail_swing = 1.0 * math.sin(t + math.pi / 2)
        tilt = 1.8 * math.sin(t + math.pi / 2)
        hdx = 1.0 * math.sin(t)
    else:
        t = phase / 4.0 * math.tau
        swing = 0.12 * math.sin(t)
        bob = -1.2 * (0.5 - 0.5 * math.cos(t))
        tail_swing = 0.55 * math.sin(t)
        tilt = 0.7 * math.sin(t)
        hdx = 0.4 * math.sin(t)

    # ground shadow
    shadow = Image.new("RGBA", (F.CW, F.CH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([F.S(45), F.S(186), F.S(240), F.S(209)], fill=(39, 34, 34, 118))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(F.S(6))))

    by = bob
    # tail (behind the body), wags
    tx = 58 - 7 * tail_swing
    ty = 122 + 5 * abs(tail_swing) + by
    F.capsule(d, (87, 137 + by), (68, 127 + by), 8.5, 6.0, FUR, outline=INK, width=1.4)
    F.capsule(d, (68, 127 + by), (56, 120 + by), 6.0, 4.5, FUR, outline=INK, width=1.4)
    F.ellipse(d, (tx - 9, ty - 9, tx + 9, ty + 9), fill=FUR_HI, outline=INK, width=1.3)
    F.ellipse(d, (tx - 5, ty - 5, tx + 4, ty + 4), fill=CREAM)

    # far legs
    F.capsule(d, (170, 140 + by), (178 + 3 * -swing, 162 + by), 7.0, 5.4,
              FUR_LO, outline=INK, width=1.3)
    F.capsule(d, (178 + 3 * -swing, 162 + by), (181 + 5 * -swing, 187 + by), 5.4, 4.3,
              FUR_LO, outline=INK, width=1.3)
    F.ellipse(d, (181 + 5 * -swing - 7, 188 + by, 181 + 5 * -swing + 7, 195 + by),
              fill=PAW_LO, outline=INK, width=1.1)
    F.capsule(d, (112, 148 + by), (98, 166 + by), 7.6, 5.6, FUR_LO, outline=INK, width=1.3)
    F.capsule(d, (98, 166 + by), (90, 187 + by), 5.6, 4.4, FUR_LO, outline=INK, width=1.3)
    F.ellipse(d, (83, 188 + by, 97, 195 + by), fill=PAW_LO, outline=INK, width=1.1)

    # body
    F.blob(d, [(86, 150 + by), (85, 140 + by), (92, 130 + by), (105, 122 + by),
               (122, 117 + by), (145, 115 + by), (166, 116 + by), (183, 121 + by),
               (192, 130 + by), (194, 140 + by), (189, 151 + by), (179, 160 + by),
               (164, 167 + by), (146, 171 + by), (127, 170 + by), (110, 165 + by),
               (96, 159 + by)], FUR, outline=INK, width=2.0)
    # back highlight
    F.blob(d, [(97, 132 + by), (110, 124 + by), (128, 120 + by), (149, 119 + by),
               (168, 121 + by), (181, 127 + by), (176, 134 + by), (158, 129 + by),
               (137, 128 + by), (118, 131 + by), (104, 138 + by)], FUR_HI, outline=None)
    # belly / chest cream
    F.blob(d, [(178, 139 + by), (185, 143 + by), (185, 153 + by), (176, 160 + by),
               (166, 162 + by), (170, 152 + by)], CREAM, outline=None)
    F.ellipse(d, (166, 128 + by, 191, 153 + by), fill=CREAM, outline=None)

    # near legs
    F.capsule(d, (188, 138 + by), (199 + 3 * swing, 160 + by), 7.8, 6.0,
              FUR, outline=INK, width=1.4)
    F.capsule(d, (199 + 3 * swing, 160 + by), (204 + 6 * swing, 187 + by),
              6.0, 4.8, FUR, outline=INK, width=1.4)
    F.ellipse(d, (204 + 6 * swing - 8, 188 + by, 204 + 6 * swing + 8, 196 + by),
              fill=PAW, outline=INK, width=1.2)
    F.capsule(d, (101, 147 + by), (84 + 4 * -swing, 166 + by), 9.0, 6.6,
              FUR, outline=INK, width=1.4)
    F.capsule(d, (84 + 4 * -swing, 166 + by), (74 + 7 * -swing, 187 + by),
              6.6, 5.0, FUR, outline=INK, width=1.4)
    F.ellipse(d, (74 + 7 * -swing - 9, 188 + by, 74 + 7 * -swing + 9, 196 + by),
              fill=PAW, outline=INK, width=1.2)
    # toe lines
    for px, py in [(204 + 6 * swing, 192 + by), (74 + 7 * -swing, 192 + by)]:
        for k in (-4, 0, 4):
            d.line(F.sp([(px + k, py), (px + k, py + 3)]), fill=(196, 185, 169),
                   width=max(1, int(F.S(0.9))))

    # furry neck patch behind the head, so the head sits on the dog
    F.blob(d, [(181, 108 + by), (190, 103 + by), (201, 106 + by), (209, 114 + by),
               (207, 126 + by), (199, 138 + by), (188, 141 + by), (180, 132 + by),
               (177, 119 + by)], FUR, outline=INK, width=1.7)

    # head
    cx = (198 - 170) * F.K
    cy = (108 - 25) * F.K
    rot = head.rotate(tilt, resample=Image.BICUBIC, center=(cx, cy))
    layer.alpha_composite(rot, (int(F.S(170 + hdx)), int(F.S(25 + by))))

    # fluffy neck ruff, drawn over the neck fade
    fur_ruff(d, by)
    return layer


def main():
    head = head_image()
    previews = []
    for mode, count in (("crawl", 8), ("idle", 4)):
        for phase in range(count):
            frame = render(head, phase, mode).resize((F.OW, F.OH), Image.LANCZOS)
            F.save_bmp(SPRITES / f"pet_r_{mode[0]}{phase}.bmp", frame)
            F.save_bmp(SPRITES / f"pet_l_{mode[0]}{phase}.bmp", frame.transpose(Image.FLIP_LEFT_RIGHT))
            if phase < 4:
                previews.append(frame.resize((F.W, F.H), Image.LANCZOS))
    sheet = F.checker(F.W * 4 + 70, F.H * 2 + 80)
    for i, im in enumerate(previews):
        col, row = i % 4, i // 4
        sheet.paste(im, (24 + col * (F.W + 8), 30 + row * (F.H + 10)), im)
    sheet.save(ROOT / "assets" / "preview_dog.png")
    print("dog frames written")


if __name__ == "__main__":
    main()
