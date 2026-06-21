"""Generate ThaiCarbide logo — 1200x1200 PNG"""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1200, 1200
BG      = (26,  58,  26)   # #1a3a1a
GOLD    = (212, 175, 55)   # #d4af37
GOLD_LT = (240, 210, 90)
GOLD_DK = (148, 118, 28)
GOLD_MU = (170, 138, 40)   # muted gold for tagline

# ── Canvas ────────────────────────────────────────────────────────────────────
img  = Image.new("RGBA", (W, H), (*BG, 255))
draw = ImageDraw.Draw(img)

# Subtle vignette overlay
vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
vd  = ImageDraw.Draw(vig)
for step in range(120):
    r     = W // 2 - step * 4
    alpha = int(step * 0.55)
    vd.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=(0, 0, 0, alpha))
img = Image.alpha_composite(img, vig)
draw = ImageDraw.Draw(img)

# ── Hexagon icon ──────────────────────────────────────────────────────────────
ICX, ICY, IR = 600, 390, 185   # center, radius

def hex_pts(cx, cy, r, a0=-90):
    return [(cx + r*math.cos(math.radians(60*i+a0)),
             cy + r*math.sin(math.radians(60*i+a0))) for i in range(6)]

pts = hex_pts(ICX, ICY, IR)

# Glow behind hex
glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow_layer)
for g in range(30, 0, -1):
    alpha = int(g * 4)
    gd.polygon(hex_pts(ICX, ICY, IR + g), fill=(*GOLD, alpha))
glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(18))
img = Image.alpha_composite(img, glow_layer)
draw = ImageDraw.Draw(img)

# Base gold hex
draw.polygon(pts, fill=GOLD)

# Beveled faces — lighter top-right, darker bottom-left
for i in range(6):
    p1 = pts[i]; p2 = pts[(i+1) % 6]
    mid_angle = (60*i - 90 + 30) % 360
    lightness  = math.cos(math.radians(mid_angle - 315))   # light from top-right
    shade = 0.78 + 0.28 * lightness
    fc = tuple(min(255, max(0, int(c * shade))) for c in GOLD)
    draw.polygon([p1, p2, (ICX, ICY)], fill=fc)

# Inner raised platform (creates 3-D depth)
draw.polygon(hex_pts(ICX, ICY, IR * 0.78), fill=(196, 160, 48))

# Chip-breaker groove ring
draw.ellipse([ICX - IR*0.48, ICY - IR*0.48, ICX + IR*0.48, ICY + IR*0.48],
             outline=GOLD_DK, width=6)

# Center mounting hole with bevel
hole = IR * 0.22
draw.ellipse([ICX-hole-3, ICY-hole-3, ICX+hole+3, ICY+hole+3], fill=GOLD_DK)
draw.ellipse([ICX-hole,   ICY-hole,   ICX+hole,   ICY+hole  ], fill=BG)

# Outer hex border lines
draw.polygon(pts, outline=GOLD_LT, width=3)

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_DIN   = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
F_THAI  = "/Library/Fonts/Arial Unicode.ttf"
F_ARIAL = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

font_title = ImageFont.truetype(F_DIN,   165)
font_thai  = ImageFont.truetype(F_THAI,   78)
font_tag   = ImageFont.truetype(F_ARIAL,  36)

def centered_text(d, text, y, font, color):
    bb = d.textbbox((0, 0), text, font=font)
    x  = (W - (bb[2] - bb[0])) // 2 - bb[0]
    d.text((x, y), text, fill=color, font=font)

# ── "THAI CARBIDE" main text ──────────────────────────────────────────────────
centered_text(draw, "THAI CARBIDE", 620, font_title, GOLD)

# ── Decorative divider ────────────────────────────────────────────────────────
DY, DM = 823, 160
draw.rectangle([DM, DY, W-DM, DY+3], fill=(*GOLD, 140))
for xp in [DM, W-DM]:
    draw.ellipse([xp-5, DY-3, xp+5, DY+6], fill=GOLD)

# ── Thai subtitle ─────────────────────────────────────────────────────────────
centered_text(draw, "คาร์ไบด์ไทย", 845, font_thai, GOLD)

# ── Tagline ───────────────────────────────────────────────────────────────────
centered_text(draw, "TUNGSTEN CARBIDE SCRAP BUYERS  ·  THAILAND", 978, font_tag, GOLD_MU)

# ── Double border ─────────────────────────────────────────────────────────────
draw.rectangle([ 22,  22, W- 22, H- 22], outline=GOLD,    width=3)
draw.rectangle([ 32,  32, W- 32, H- 32], outline=GOLD_DK, width=1)

# Corner ornaments
for cx2, cy2 in [(22,22),(W-22,22),(22,H-22),(W-22,H-22)]:
    draw.rectangle([cx2-5, cy2-5, cx2+5, cy2+5], fill=GOLD)

# ── Save ──────────────────────────────────────────────────────────────────────
out = img.convert("RGB")
out.save("/Users/marvin/Downloads/carbide-thai/logo.png", "PNG", dpi=(300, 300))
print("logo.png saved — 1200×1200 @300dpi")
