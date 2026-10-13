"""Clean z-buffered isometric render (matplotlib's 3D painter sorts badly)."""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import mount  # noqa: E402
from boxcad import Part  # noqa: E402


def box(x0, x1, y0, y1, z0, z1):
    p = Part("g")
    p.add(x0, x1, y0, y1, z0, z1)
    return p


def render(objs, azim_deg, elev_deg, size=(1000, 760), scale=2.6, title=""):
    W, H = size
    az, el = math.radians(azim_deg), math.radians(elev_deg)
    # view basis: right, up, toward viewer
    fwd = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    right = np.cross(np.array([0, 0, 1.0]), fwd)
    right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    light = np.array([0.3, -0.5, 0.8])
    light /= np.linalg.norm(light)
    zbuf = np.full((H, W), -1e9)
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    for part, color, dz in objs:
        base = np.array(color, dtype=float)
        for n, a, b, c in part.triangles():
            n = np.array(n, dtype=float)
            if np.dot(n, fwd) <= 0:
                continue
            shade = 0.55 + 0.45 * max(0.0, float(np.dot(n, light)))
            col = np.clip(base * shade, 0, 255).astype(np.uint8)
            pts = []
            for v in (a, b, c):
                v = np.array(v, dtype=float) + np.array([0, 0, dz])
                sx = W / 2 + scale * np.dot(v, right)
                sy = H * 0.62 - scale * np.dot(v, up)
                pts.append((sx, sy, np.dot(v, fwd)))
            (x0, y0, d0), (x1, y1, d1), (x2, y2, d2) = pts
            minx, maxx = int(max(0, math.floor(min(x0, x1, x2)))), int(min(W - 1, math.ceil(max(x0, x1, x2))))
            miny, maxy = int(max(0, math.floor(min(y0, y1, y2)))), int(min(H - 1, math.ceil(max(y0, y1, y2))))
            if minx > maxx or miny > maxy:
                continue
            xs, ys = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
            det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if abs(det) < 1e-9:
                continue
            l1 = ((xs - x0) * (y2 - y0) - (x2 - x0) * (ys - y0)) / det
            l2 = ((x1 - x0) * (ys - y0) - (xs - x0) * (y1 - y0)) / det
            l0 = 1 - l1 - l2
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            depth = l0 * d0 + l1 * d1 + l2 * d2
            sub = zbuf[miny:maxy + 1, minx:maxx + 1]
            upd = inside & (depth > sub)
            sub[upd] = depth[upd]
            img[miny:maxy + 1, minx:maxx + 1][upd] = col
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    d.text((16, 12), title, fill=(20, 20, 20), font=font)
    return im


tray, lid = mount.build_tray(), mount.build_lid()
zb, zl = mount.z_bank0, mount.z_lid1
rails = [(box(sx * 80, sx * 90, -72, 72, -20, 0), (120, 120, 120), 0) for sx in (-1, 1)]
bank = box(-40.5, 40.5, -80, 80, zb, zb + 27)
cy = mount.CASE_Y
case = box(-61, 61, cy - 47.5, cy + 47.5, zl, zl + 45)
display = box(-41.6, -40.5, -67, -52, zb + 9, zb + 19)
button = box(-41.6, -40.5, -44, -33, zb + 9, zb + 19)
BLUE, ORANGE, GREY, DARK, CYAN, RED = (70, 140, 210), (235, 125, 50), (205, 205, 205), (60, 60, 60), (40, 200, 230), (220, 40, 40)

out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__)
a = render(rails + [(tray, BLUE, 0), (bank, GREY, 20), (display, CYAN, 20), (button, RED, 20), (lid, ORANGE, 45), (case, DARK, 80)],
           azim_deg=-125, elev_deg=30, title="Exploded, from the rear-left: rails > tray > power bank > lid > Jetson case")
b = render(rails + [(tray, BLUE, 0), (bank, GREY, 0), (display, CYAN, 0), (button, RED, 0), (lid, ORANGE, 0), (case, DARK, 0)],
           azim_deg=-125, elev_deg=25, title="Assembled, rear-left: bank display (cyan) and button (red) visible through the wall window")
c = render([(tray, BLUE, 0)], azim_deg=-55, elev_deg=40, scale=3.0, title="Tray alone, from the front-right")
d_ = render([(lid, ORANGE, 0)], azim_deg=-55, elev_deg=-35, scale=3.6, title="Lid alone, seen from BELOW: head pockets around the two case slots")
sheet = Image.new("RGB", (2000, 1520), "white")
sheet.paste(a, (0, 0)); sheet.paste(b, (1000, 0)); sheet.paste(c, (0, 760)); sheet.paste(d_, (1000, 760))
sheet.save(os.path.join(out, "preview-iso.png"))
print("ok")
