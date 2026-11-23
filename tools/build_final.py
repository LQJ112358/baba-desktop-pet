"""Build the final desktop-pet sprites: the person from the photos, crawling.

No hood, no props, no accessories -- just the person in his grey hoodie,
dark trousers and white shoes, plus a plain "爸爸" speech bubble.
"""
from __future__ import annotations

import math
import random
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SPRITES = ASSETS / "sprites"
HEAD_SRC = ASSETS / "head_nohood.png"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

W, H = 280, 220
OUT_SCALE = 2
K = 4
OW, OH = W * OUT_SCALE, H * OUT_SCALE
CW, CH = W * K, H * K

HOODIE = (201, 205, 212)
HOODIE_HI = (224, 227, 232)
HOODIE_LO = (169, 175, 185)
SEAM = (151, 158, 168)
OUTLINE = (105, 112, 122)
PANTS = (58, 63, 72)
PANTS_HI = (82, 88, 99)
SKIN = (232, 184, 157)
SKIN_HI = (244, 203, 178)
SHOE = (243, 241, 234)
SOLE = (158, 156, 150)
LACE = (92, 97, 104)
INK = (54, 49, 48)


def S(v: float) -> float:
    return v * K


def sp(pts):
    return [(S(x), S(y)) for x, y in pts]


def blob(d, pts, fill, outline=None, width=1.8):
    d.polygon(sp(pts), fill=fill)
    if outline:
        d.line(sp(pts) + [sp(pts)[0]], fill=outline, width=max(1, int(S(width))), joint="curve")


def ellipse(d, box, fill=None, outline=None, width=1.6):
    d.ellipse([S(v) for v in box], fill=fill, outline=outline, width=max(1, int(S(width))))


def capsule(d, p1, p2, r1, r2, fill, outline=None, width=1.4):
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    pts = [
        (x1 + nx * r1, y1 + ny * r1),
        (x2 + nx * r2, y2 + ny * r2),
        (x2 - nx * r2, y2 - ny * r2),
        (x1 - nx * r1, y1 - ny * r1),
    ]
    d.polygon(sp(pts), fill=fill)
    ellipse(d, (x1 - r1, y1 - r1, x1 + r1, y1 + r1), fill=fill)
    ellipse(d, (x2 - r2, y2 - r2, x2 + r2, y2 + r2), fill=fill)
    if outline:
        for a, b in ((pts[0], pts[1]), (pts[3], pts[2])):
            d.line(sp([a, b]), fill=outline, width=max(1, int(S(width))))


def draw_hand(d, x, y, near=True):
    c = SKIN if near else (206, 159, 135)
    ellipse(d, (x - 4.3, y - 3.4, x + 4.3, y + 4.0), fill=c,
            outline=(154, 112, 94), width=0.9)
    ellipse(d, (x - 2.1, y - 5.0, x + 1.3, y - 1.2), fill=SKIN_HI, outline=None)
    if near:
        d.arc([S(x - 2), S(y - 1.2), S(x + 2), S(y + 3.2)], 300, 80,
              fill=(202, 154, 131), width=max(1, int(S(0.8))))


def draw_shoe(d, x, y, scale=1.0, near=True):
    w, h = 30 * scale, 13 * scale
    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    ellipse(d, box, fill=SHOE if near else (216, 213, 205), outline=(102, 105, 110), width=1.2)
    ellipse(d, (box[0] + 1.5, box[1] + h * 0.56, box[2] - 1.5, box[3] + 0.8),
            fill=SOLE if near else (190, 187, 181), outline=(103, 104, 105), width=1.0)
    ellipse(d, (box[0] + 1.5, box[1] + 1.5, box[0] + w * 0.4, box[3] - 3),
            fill=(255, 254, 249) if near else (230, 227, 220))
    if near:
        for i in range(2):
            d.line(sp([(x + 1 + i * 5, y - 3), (x + 4 + i * 5, y - 1.3)]),
                   fill=LACE, width=max(1, int(S(1.0))))


def build_head() -> Image.Image:
    src = Image.open(HEAD_SRC).convert("RGBA")
    # fit into a 58 x 81 logical box, facing right
    head = src.resize((int(64 * K), int(89 * K)), Image.LANCZOS)
    return head.transpose(Image.FLIP_LEFT_RIGHT)


def render_frame(head: Image.Image, phase: int, mode: str) -> Image.Image:
    layer = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    if mode == "crawl":
        t = phase / 8.0 * math.tau
        swing = math.sin(t)
        bob = -2.2 * abs(math.sin(t))
        tilt = 2.2 * math.sin(t + math.pi / 2)
        hdx = 1.3 * math.sin(t)
    else:
        t = phase / 4.0 * math.tau
        swing = 0.10 * math.sin(t)
        bob = -1.6 * (0.5 - 0.5 * math.cos(t))
        tilt = 0.8 * math.sin(t)
        hdx = 0.6 * math.sin(t)

    # ground shadow stays put
    shadow = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([S(42), S(178), S(238), S(202)], fill=(36, 32, 33, 118))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S(6))))

    by = bob
    a = swing
    far = -swing

    # ---- far limbs -------------------------------------------------------
    B.capsule(d, (120, 140 + by), (96, 160 + by - 1.8 * max(0, far)), 9, 7,
              (48, 53, 61), outline=(36, 40, 47), width=1.3)
    B.capsule(d, (96, 160 + by - 1.8 * max(0, far)), (80, 181 + by - 1.8 * max(0, far)),
              7, 5.5, (48, 53, 61), outline=(36, 40, 47), width=1.3)
    B.draw_shoe(d, 67, 190 + by, 0.9, near=False)

    B.capsule(d, (170, 112 + by), (190 + 3 * far, 142 + by - 2.0 * max(0, far)), 8.2, 6.2,
              (174, 180, 188), outline=OUTLINE, width=1.4)
    B.capsule(d, (190 + 3 * far, 142 + by - 2.0 * max(0, far)),
              (199 + 6 * far, 175 + by - 3.0 * max(0, far)), 6.2, 5.0,
              (174, 180, 188), outline=OUTLINE, width=1.4)
    B.draw_hand(d, 201 + 6 * far, 182 + by - 3.0 * max(0, far), near=False)

    # ---- torso -----------------------------------------------------------
    B.capsule(d, (170, 118 + by), (112, 147 + by), 24, 27, HOODIE, outline=OUTLINE, width=2.1)
    B.capsule(d, (164, 106 + by), (120, 132 + by), 12, 14, HOODIE_HI, outline=None)
    # hem / fabric seam
    d.arc([S(98), S(137 + by), S(170), S(166 + by)], 25, 155, fill=SEAM, width=max(1, int(S(1.4))))
    d.line(sp([(177, 124 + by), (183, 141 + by), (182, 154 + by)]), fill=SEAM,
           width=max(1, int(S(1.2))))
    # trouser seat
    B.blob(d, [(91, 145 + by), (95, 135 + by), (106, 130 + by), (118, 134 + by),
               (124, 144 + by), (121, 156 + by), (112, 164 + by), (99, 160 + by),
               (92, 153 + by)], PANTS, outline=(36, 40, 47), width=1.5)

    # ---- near limbs ------------------------------------------------------
    B.capsule(d, (112, 150 + by), (84, 169 + by - 2.2 * max(0, -a)), 11, 8,
              PANTS, outline=(37, 41, 48), width=1.4)
    B.capsule(d, (84, 169 + by - 2.2 * max(0, -a)), (68, 186 + by - 2.2 * max(0, -a)),
              8, 6, PANTS, outline=(37, 41, 48), width=1.4)
    B.draw_shoe(d, 53, 193 + by, 1.0, near=True)

    B.capsule(d, (180, 116 + by), (204 + 4 * a, 146 + by - 2.5 * max(0, a)), 9.2, 7.0,
              HOODIE, outline=OUTLINE, width=1.7)
    B.capsule(d, (204 + 4 * a, 146 + by - 2.5 * max(0, a)),
              (213 + 8 * a, 175 + by - 4.0 * max(0, a)), 7.0, 5.5,
              HOODIE, outline=OUTLINE, width=1.7)
    B.draw_hand(d, 216 + 8 * a, 182 + by - 4.0 * max(0, a), near=True)

    # ---- neck / collar ---------------------------------------------------
    B.blob(d, [(176, 106 + by), (184, 99 + by), (198, 97 + by), (210, 102 + by),
               (215, 111 + by), (210, 119 + by), (198, 122 + by), (186, 117 + by),
               (178, 112 + by)], HOODIE_LO, outline=OUTLINE, width=1.6)

    # ---- head ------------------------------------------------------------
    # rotate around the neck point (198, 108)
    cx = (198 - 166) * K
    cy = (108 - 24) * K
    rot = head.rotate(tilt, resample=Image.BICUBIC, center=(cx, cy))
    layer.alpha_composite(rot, (int(S(166 + hdx)), int(S(24 + by))))

    return layer


def render_bubble(text: str) -> Image.Image:
    bw, bh = 220, 120
    k = 3
    img = Image.new("RGBA", (bw * k, bh * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_BOLD, 36 * k)
    bb = d.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    box_w = max(130 * k, tw + 48 * k)
    box_h = 76 * k
    cx = bw * k // 2
    x0 = cx - box_w // 2
    y0 = 12 * k
    x1 = x0 + box_w
    y1 = y0 + box_h

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([x0 + 3 * k, y0 + 5 * k, x1 + 3 * k, y1 + 5 * k],
                         radius=20 * k, fill=(48, 42, 44, 90))
    sd.polygon([(cx - 12 * k + 3 * k, y1 + 3 * k), (cx + 16 * k + 3 * k, y1 + 3 * k),
                (cx + 2 * k + 3 * k, y1 + 22 * k + 3 * k)], fill=(48, 42, 44, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3.5 * k)))

    fill = (255, 253, 247, 255)
    line = (63, 57, 55, 255)
    d.rounded_rectangle([x0, y0, x1, y1], radius=20 * k, fill=fill, outline=line, width=3 * k)
    d.polygon([(cx - 12 * k, y1 - 1), (cx + 16 * k, y1 - 1), (cx + 2 * k, y1 + 21 * k)],
              fill=fill, outline=line)
    d.rectangle([cx - 9 * k, y1 - 5 * k, cx + 13 * k, y1 + 3 * k], fill=fill)
    # subtle inner top highlight
    d.rounded_rectangle([x0 + 4 * k, y0 + 4 * k, x1 - 4 * k, y0 + 8 * k],
                        radius=2 * k, fill=(255, 255, 255, 120))

    tx = cx - (bb[0] + tw) / 2
    ty = y0 + (box_h - (bb[3] - bb[1])) / 2 - bb[1] + 1 * k
    d.text((tx, ty), text, font=font, fill=(58, 53, 51, 255))
    return img.resize((bw, bh), Image.LANCZOS)


def save_bmp(path: Path, img: Image.Image):
    img = img.convert("RGBA")
    w, h = img.size
    a = np.asarray(img).astype(np.uint16)
    alpha = a[..., 3]
    rgb = (a[..., :3] * alpha[..., None] // 255).astype(np.uint8)
    bgra = np.empty((h, w, 4), np.uint8)
    bgra[..., 0] = rgb[..., 2]
    bgra[..., 1] = rgb[..., 1]
    bgra[..., 2] = rgb[..., 0]
    bgra[..., 3] = alpha.astype(np.uint8)
    pixels = bgra.tobytes()
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, len(pixels), 2835, 2835, 0, 0)
    path.write_bytes(header + info + pixels)


def checker(w, h):
    im = Image.new("RGB", (w, h), (236, 237, 242))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 26):
        for x in range(0, w, 26):
            if (x // 26 + y // 26) % 2 == 0:
                d.rectangle([x, y, x + 25, y + 25], fill=(219, 221, 228))
    return im


def main():
    SPRITES.mkdir(parents=True, exist_ok=True)
    head = build_head()
    previews = []
    for mode, count in (("crawl", 8), ("idle", 4)):
        for phase in range(count):
            frame = render_frame(head, phase, mode).resize((OW, OH), Image.LANCZOS)
            save_bmp(SPRITES / f"pet_r_{mode[0]}{phase}.bmp", frame)
            save_bmp(SPRITES / f"pet_l_{mode[0]}{phase}.bmp", frame.transpose(Image.FLIP_LEFT_RIGHT))
            if phase < 4:
                previews.append((f"{mode}{phase}", frame.resize((W, H), Image.LANCZOS)))

    sheet = checker(W * 4 + 70, H * 2 + 80)
    for i, (name, im) in enumerate(previews):
        col, row = i % 4, i // 4
        sheet.paste(im, (24 + col * (W + 8), 30 + row * (H + 10)), im)
    sheet.save(ASSETS / "preview_frames.png")

    # desktop mock with a plain bubble
    desk = Image.new("RGB", (1280, 800), (39, 47, 63))
    dd = ImageDraw.Draw(desk)
    dd.rounded_rectangle([370, 100, 1210, 700], radius=16, fill=(249, 250, 252))
    dd.rounded_rectangle([370, 100, 1210, 146], radius=16, fill=(234, 236, 241))
    for c in [(398, 118, 255, 112, 110), (422, 118, 255, 190, 100), (446, 118, 120, 208, 140)]:
        dd.ellipse([c[0], c[1], c[0] + 12, c[1] + 12], fill=c[2:])
    dd.rectangle([400, 190, 900, 204], fill=(211, 215, 223))
    dd.rectangle([400, 224, 780, 236], fill=(225, 228, 234))
    dd.rectangle([400, 270, 1100, 282], fill=(232, 234, 239))
    pet = render_frame(head, 2, "crawl").resize((OW, OH), Image.LANCZOS).resize((W, H), Image.LANCZOS)
    desk.paste(pet, (850, 505), pet)
    bubble = render_bubble("爸爸")
    desk.paste(bubble, (930, 390), bubble)
    dd.polygon([(1130, 590), (1130, 628), (1140, 619), (1147, 635), (1155, 631),
                (1147, 616), (1159, 615)], fill=(255, 255, 255), outline=(30, 30, 30))
    desk.save(ASSETS / "preview_desktop.png")

    for i, text in enumerate(["爸爸", "爸爸~", "爸爸！", "爸爸？"]):
        b = render_bubble(text)
        b.save(ASSETS / f"bubble_{i}.png")
        save_bmp(SPRITES / f"bubble_{i}.bmp", b)
    print("frames:", len(list(SPRITES.glob("*.bmp"))))


# local alias so the sprite code can stay terse
B = None


if __name__ == "__main__":
    # the helper calls in render_frame use B.*, bind them to this module
    import sys
    B = sys.modules[__name__]
    main()
