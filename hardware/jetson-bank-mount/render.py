import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(__file__))
import mount
from boxcad import Part


def ghost_box(name, x0, x1, y0, y1, z0, z1):
    p = Part(name)
    p.add(x0, x1, y0, y1, z0, z1)
    return p


def draw(ax, part, color, alpha=1.0, dz=0.0, edge=True):
    polys = [[(a[0], a[1], a[2] + dz), (b[0], b[1], b[2] + dz), (c[0], c[1], c[2] + dz)]
             for _, a, b, c in part.triangles()]
    coll = Poly3DCollection(polys, facecolors=color, edgecolors="k" if edge else "none",
                            linewidths=0.15, alpha=alpha)
    ax.add_collection3d(coll)


def scene(ax, exploded):
    tray, lid = mount.build_tray(), mount.build_lid()
    z_b = mount.z_bank0
    z_l = mount.z_lid1
    dz_lid = 40 if exploded else 0
    dz_case = 80 if exploded else 0
    # rails
    for sx in (-1, 1):
        draw(ax, ghost_box("rail", sx * 80, sx * 90, -72, 72, -20, 0), "#777777", 0.9, edge=False)
    draw(ax, tray, "#5b9bd5", 1.0)
    draw(ax, ghost_box("bank", -40.5, 40.5, -80, 80, z_b, z_b + 27), "#c9c9c9", 0.95, dz=dz_lid / 2 if exploded else 0, edge=False)
    draw(ax, lid, "#ed7d31", 1.0, dz=dz_lid)
    draw(ax, ghost_box("case", -61, 61, mount.CASE_Y - 47.5, mount.CASE_Y + 47.5, z_l, z_l + 45), "#333333", 0.9, dz=dz_case, edge=False)
    ax.set_xlim(-110, 110)
    ax.set_ylim(-110, 110)
    ax.set_zlim(-20, 200)
    ax.set_box_aspect((220, 220, 220))
    ax.set_xlabel("X across (mm)")
    ax.set_ylabel("Y along (+ = front)")
    ax.set_zlabel("Z")


out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__)
fig = plt.figure(figsize=(16, 7), dpi=110)
ax1 = fig.add_subplot(1, 2, 1, projection="3d")
scene(ax1, exploded=True)
ax1.view_init(elev=28, azim=-50)
ax1.set_title("Exploded: rails (grey) > tray (blue) > power bank > lid (orange) > Jetson case")
ax2 = fig.add_subplot(1, 2, 2, projection="3d")
scene(ax2, exploded=False)
ax2.view_init(elev=22, azim=-130)
ax2.set_title("Assembled, seen from the rear (ports side)")
plt.tight_layout()
fig.savefig(os.path.join(out, "preview.png"))

# top view of the two parts, 2D, with dimensions
fig2, (a, b) = plt.subplots(1, 2, figsize=(16, 7), dpi=110)
for ax, part, title in ((a, mount.build_tray(), "Tray, top view"), (b, mount.build_lid(), "Lid, top view (pockets are underneath)")):
    xs, ys, zs, solid = part.solid_cells()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            top = max((zs[k + 1] for k in range(len(zs) - 1) if solid[i][j][k]), default=None)
            if top is None:
                continue
            shade = 0.85 - 0.55 * (top - zs[0]) / (zs[-1] - zs[0])
            ax.add_patch(plt.Rectangle((xs[i], ys[j]), xs[i + 1] - xs[i], ys[j + 1] - ys[j],
                                       facecolor=(shade, shade, shade), edgecolor="none"))
    ax.set_xlim(-100, 100)
    ax.set_ylim(-90, 90)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_title(title)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm), + = front")
for sx in (-1, 1):
    a.axvspan(sx * 80, sx * 90, color="tab:red", alpha=0.15)
a.text(85, 0, "rail", ha="center", color="tab:red")
a.text(-85, 0, "rail", ha="center", color="tab:red")
a.add_patch(plt.Rectangle((-40.5, -80), 81, 160, fill=False, edgecolor="tab:green", linestyle="--"))
a.text(0, 0, "power bank\n160 x 81", ha="center", va="center", color="tab:green")
b.add_patch(plt.Rectangle((-61, mount.CASE_Y - 47.5), 122, 95, fill=False, edgecolor="tab:green", linestyle="--"))
b.text(0, mount.CASE_Y + 40, "Jetson case 122 x 95", ha="center", va="center", color="tab:green")
a.add_patch(plt.Rectangle((-44.5, -67), 3, 15, color="tab:cyan"))
a.text(-52, -60, "display", ha="right", va="center", fontsize=8)
a.add_patch(plt.Rectangle((-44.5, -44), 3, 11, color="tab:red"))
a.text(-52, -38, "button", ha="right", va="center", fontsize=8)
a.add_patch(plt.Rectangle((-76, mount.LID_Y0), 152, mount.LID_Y1 - mount.LID_Y0, fill=False, edgecolor="tab:orange", linestyle=":"))
a.text(60, mount.LID_Y0 + 4, "lid outline", color="tab:orange", fontsize=8)
plt.tight_layout()
fig2.savefig(os.path.join(out, "preview-top.png"))
print("ok")
