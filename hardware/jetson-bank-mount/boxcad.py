"""Minimal box-based CAD: a part is a union of axis-aligned boxes minus cut boxes.

The part is voxelised on the non-uniform grid formed by every box edge, so the
extracted boundary is exact (no approximation), watertight and manifold as long
as solid cells never touch only along an edge or a corner.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field


@dataclass
class Box:
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float

    def contains(self, x: float, y: float, z: float) -> bool:
        return self.x0 < x < self.x1 and self.y0 < y < self.y1 and self.z0 < z < self.z1


@dataclass
class Part:
    name: str
    adds: list[Box] = field(default_factory=list)
    cuts: list[Box] = field(default_factory=list)

    # ---- authoring helpers -------------------------------------------------
    def add(self, x0, x1, y0, y1, z0, z1) -> None:
        self.adds.append(Box(*sorted((x0, x1)), *sorted((y0, y1)), *sorted((z0, z1))))

    def cut(self, x0, x1, y0, y1, z0, z1) -> None:
        self.cuts.append(Box(*sorted((x0, x1)), *sorted((y0, y1)), *sorted((z0, z1))))

    def add_c(self, cx, cy, sx, sy, z0, z1) -> None:
        """Add a box by centre (cx, cy) and size (sx, sy)."""
        self.add(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z1)

    def cut_c(self, cx, cy, sx, sy, z0, z1) -> None:
        """Cut a box by centre (cx, cy) and size (sx, sy)."""
        self.cut(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z1)

    # ---- evaluation --------------------------------------------------------
    def grid(self):
        xs, ys, zs = set(), set(), set()
        for b in self.adds + self.cuts:
            xs.update((b.x0, b.x1))
            ys.update((b.y0, b.y1))
            zs.update((b.z0, b.z1))
        return sorted(xs), sorted(ys), sorted(zs)

    def solid_cells(self):
        xs, ys, zs = self.grid()
        nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
        solid = [[[False] * nz for _ in range(ny)] for _ in range(nx)]
        for i in range(nx):
            cx = (xs[i] + xs[i + 1]) / 2
            for j in range(ny):
                cy = (ys[j] + ys[j + 1]) / 2
                for k in range(nz):
                    cz = (zs[k] + zs[k + 1]) / 2
                    if any(b.contains(cx, cy, cz) for b in self.adds) and not any(
                        b.contains(cx, cy, cz) for b in self.cuts
                    ):
                        solid[i][j][k] = True
        return xs, ys, zs, solid

    def triangles(self):
        """Boundary triangles as (normal, v0, v1, v2), outward, CCW seen from outside."""
        xs, ys, zs, solid = self.solid_cells()
        nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1

        def is_solid(i, j, k):
            return 0 <= i < nx and 0 <= j < ny and 0 <= k < nz and solid[i][j][k]

        tris = []
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    if not solid[i][j][k]:
                        continue
                    x0, x1 = xs[i], xs[i + 1]
                    y0, y1 = ys[j], ys[j + 1]
                    z0, z1 = zs[k], zs[k + 1]
                    # -X face
                    if not is_solid(i - 1, j, k):
                        tris += quad((-1, 0, 0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0))
                    if not is_solid(i + 1, j, k):
                        tris += quad((1, 0, 0), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
                    if not is_solid(i, j - 1, k):
                        tris += quad((0, -1, 0), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
                    if not is_solid(i, j + 1, k):
                        tris += quad((0, 1, 0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))
                    if not is_solid(i, j, k - 1):
                        tris += quad((0, 0, -1), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
                    if not is_solid(i, j, k + 1):
                        tris += quad((0, 0, 1), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
        return tris

    def volume_mm3(self) -> float:
        xs, ys, zs, solid = self.solid_cells()
        v = 0.0
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                for k in range(len(zs) - 1):
                    if solid[i][j][k]:
                        v += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) * (zs[k + 1] - zs[k])
        return v

    def bounds(self):
        xs, ys, zs, solid = self.solid_cells()
        pts = []
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                for k in range(len(zs) - 1):
                    if solid[i][j][k]:
                        pts.append((xs[i], ys[j], zs[k]))
                        pts.append((xs[i + 1], ys[j + 1], zs[k + 1]))
        return (
            (min(p[0] for p in pts), max(p[0] for p in pts)),
            (min(p[1] for p in pts), max(p[1] for p in pts)),
            (min(p[2] for p in pts), max(p[2] for p in pts)),
        )


def quad(n, a, b, c, d):
    return [(n, a, b, c), (n, a, c, d)]


def check_manifold(tris) -> dict:
    """Every undirected edge must be shared by exactly two triangles, with opposite direction."""
    directed: dict[tuple, int] = {}
    for _, a, b, c in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            directed[(p, q)] = directed.get((p, q), 0) + 1
    bad = 0
    for (p, q), n in directed.items():
        if n != 1 or directed.get((q, p), 0) != 1:
            bad += 1
    return {"triangles": len(tris), "bad_edges": bad, "watertight": bad == 0}


def write_stl(path: str, tris, name: str = "part") -> None:
    with open(path, "wb") as f:
        f.write(name.encode("ascii")[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for n, a, b, c in tris:
            f.write(struct.pack("<3f", *n))
            f.writelines(struct.pack("<3f", *v) for v in (a, b, c))
            f.write(b"\0\0")
