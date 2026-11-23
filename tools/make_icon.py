from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
head = Image.open(ROOT / "assets" / "head_nohood.png").convert("RGBA")
# drop the faded neck at the bottom, keep the head/face
w, h = head.size
head = head.crop((0, 0, w, int(h * 0.90)))
bbox = head.getbbox()
head = head.crop(bbox)

size = 512
icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(icon)
# soft badge background
d.ellipse([8, 8, size - 8, size - 8], fill=(247, 240, 228, 255), outline=(98, 96, 98, 255), width=12)
d.ellipse([40, 40, size - 40, size - 40], fill=(232, 238, 246, 255))
# scale head to fit
target_h = 380
target_w = int(head.width * target_h / head.height)
head = head.resize((target_w, target_h), Image.LANCZOS)
icon.alpha_composite(head, ((size - target_w) // 2, (size - target_h) // 2 + 18))
icon.save(ROOT / "assets" / "pet_icon.png")
icon.save(ROOT / "assets" / "pet.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written", icon.size)
