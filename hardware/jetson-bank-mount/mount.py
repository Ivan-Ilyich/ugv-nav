"""Jetson-case + power-bank stack for the Waveshare UGV01.

Two printed parts:
  tray.stl  rests on the two 1020 rails (170 mm centres), carries the UGREEN
            PB205 power bank (160 x 81 x 27 mm) lengthwise, ports to the rear.
  lid.stl   bolts to four bosses on the tray and carries the Waveshare
            JETSON-ORIN-CASE-A (122 x 95 x 45 mm) via its two bottom holes.

Axes: X across the robot, Y along it (+Y = front), Z up, Z = 0 at rail top.
All sizes in mm. Edit the PARAMETERS block and re-run.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from boxcad import Part, check_manifold, write_stl  # noqa: E402

# ---------------- PARAMETERS ----------------------------------------------
RAIL_CENTRE = 85.0      # rails at X = +/-85 (170 mm centre distance)
RAIL_SLOT_Y = 55.0      # rail screws at Y = +/-55 (rails are 144 long)
RAIL_SCREW = 4.0        # M4 drop-in T-nuts
BANK_L, BANK_W, BANK_T = 160.0, 81.0, 27.0
BANK_CLR_X = 1.0        # side clearance each side
BANK_CLR_Y = 1.0        # end clearance each end
BANK_CLR_Z = 1.0        # gap under the lid
WALL = 3.0
BASE_T = 4.0
BASE_HX = 96.0          # half-width of the base plate (covers the rails)
LID_T = 5.0
LID_HX = 76.0
BOSS = 9.0
BOSS_X = 68.0
BOSS_Y_REAR, BOSS_Y_FRONT = -42.0, 42.0   # lid bosses
CASE_Y = 0.0            # case centred on the bank
LID_Y0, LID_Y1 = -50.0, 50.0
# The bank's display and button are on its LONG SIDE face: display ~13-28 mm and
# button ~36-47 mm from the port end, at mid-height. Both side walls get a window there.
SIDE_WINDOW_Y1 = -22.0  # window runs from the rear end of the wall to here (58 mm)
SIDE_WINDOW_Z0 = 8.0    # keep a 4 mm stub at the bottom of the wall
BANK_BUTTON_FAR_EDGE = -80.0 + 48.0
BOSS_HOLE = 2.6         # self-tapping M3 (use 4.0 for M3 heat-set inserts)
BOSS_HOLE_DEPTH = 14.0
CASE_HOLE_PITCH = 65.0  # measured ~65 mm; slots give +/-2.5 mm
CASE_SCREW = 3.0
CASE_SLOT_LEN = 9.0
CASE_POCKET_W, CASE_POCKET_L, CASE_POCKET_D = 7.0, 13.0, 2.5
CASE_W, CASE_D = 122.0, 95.0  # for the clearance check only
# --------------------------------------------------------------------------

cav_hx = BANK_W / 2 + BANK_CLR_X            # 41.5
wall_ox = cav_hx + WALL                     # 44.5
bank_hy = BANK_L / 2                        # 80
front_wall_y0 = bank_hy + BANK_CLR_Y        # 81
base_hy = front_wall_y0 + WALL              # 84
z_bank0 = BASE_T                            # 4
z_lid0 = z_bank0 + BANK_T + BANK_CLR_Z      # 32
z_lid1 = z_lid0 + LID_T                     # 37


def build_tray() -> Part:
    p = Part("tray")
    # base plate across both rails
    p.add(-BASE_HX, BASE_HX, -base_hy, base_hy, 0, BASE_T)
    # lightening / airflow window under the bank (also clears the 40-pin header)
    # (two openings, leaving a cross bar at Y 20..28 that supports the bank's middle)
    p.cut(-35, 35, -58, 20, 0, BASE_T)
    p.cut(-35, 35, 28, 58, 0, BASE_T)
    # rail screw slots (6 mm long in X to absorb rail-spacing error)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cut_c(sx * RAIL_CENTRE, sy * RAIL_SLOT_Y, 6.0, RAIL_SCREW + 0.6, 0, BASE_T)
    # side walls, full length, up to the lid
    for sx in (-1, 1):
        p.add(sx * cav_hx, sx * wall_ox, -base_hy, base_hy, BASE_T, z_lid0)
        # window at the rear end so the bank's side display and button stay visible/reachable
        p.cut(sx * cav_hx, sx * wall_ox, -base_hy, SIDE_WINDOW_Y1, SIDE_WINDOW_Z0, z_lid0)
    # front end wall (closed) and rear lip (low, leaves the ports free)
    p.add(-wall_ox, wall_ox, front_wall_y0, base_hy, BASE_T, 20.0)
    p.add(-wall_ox, wall_ox, -base_hy, -front_wall_y0, BASE_T, z_bank0 + 6.0)
    # stiffening bars along the ears (continue the end walls outward)
    for sx in (-1, 1):
        p.add(sx * wall_ox, sx * BASE_HX, front_wall_y0, base_hy, BASE_T, 12.0)
        p.add(sx * wall_ox, sx * BASE_HX, -base_hy, -front_wall_y0, BASE_T, 10.0)
    # four lid bosses with blind screw holes
    for sx in (-1, 1):
        for by in (BOSS_Y_REAR, BOSS_Y_FRONT):
            p.add_c(sx * BOSS_X, by, BOSS, BOSS, BASE_T, z_lid0)
            p.cut_c(sx * BOSS_X, by, BOSS_HOLE, BOSS_HOLE, z_lid0 - BOSS_HOLE_DEPTH, z_lid0)
    return p


def build_lid() -> Part:
    p = Part("lid")
    p.add(-LID_HX, LID_HX, LID_Y0, LID_Y1, z_lid0, z_lid1)
    # corner screw holes down into the bosses
    for sx in (-1, 1):
        for by in (BOSS_Y_REAR, BOSS_Y_FRONT):
            p.cut_c(sx * BOSS_X, by, CASE_SCREW + 0.4, CASE_SCREW + 0.4, z_lid0, z_lid1)
    # case screws: slots on the centre line, pockets underneath for the heads
    for sy in (-1, 1):
        y = CASE_Y + sy * CASE_HOLE_PITCH / 2
        p.cut_c(0, y, CASE_SCREW + 0.4, CASE_SLOT_LEN, z_lid0, z_lid1)
        p.cut_c(0, y, CASE_POCKET_W, CASE_POCKET_L, z_lid0, z_lid0 + CASE_POCKET_D)
    # airflow window between the bank and the case
    p.cut(-30, 30, CASE_Y - 15, CASE_Y + 15, z_lid0, z_lid1)
    return p


def checks() -> dict:
    head_r = 3.0  # pan-head M3 radius
    return {
        "bank_cavity_x": 2 * cav_hx,
        "bank_cavity_y_open_ends": True,
        "rail_clearance_between_walls_and_rail_edge": (RAIL_CENTRE - 5) - wall_ox,
        "ear_extends_past_rail_outer_edge": BASE_HX - (RAIL_CENTRE + 5),
        "case_footprint_vs_boss_screw_heads": (BOSS_X - head_r) - CASE_W / 2,
        "case_rear_edge_vs_lid_rear_edge": (CASE_Y - CASE_D / 2) - LID_Y0,
        "case_front_edge_vs_lid_front_edge": LID_Y1 - (CASE_Y + CASE_D / 2),
        "side_window_length_from_port_end_mm": SIDE_WINDOW_Y1 - (-BANK_L / 2),
        "side_window_clears_button_by_mm": SIDE_WINDOW_Y1 - BANK_BUTTON_FAR_EDGE,
        "side_window_outside_lid": SIDE_WINDOW_Y1 <= LID_Y0,
        "wall_length_remaining_for_lateral_hold_mm": base_hy - SIDE_WINDOW_Y1,
        "lid_underside_above_bank_top": z_lid0 - (z_bank0 + BANK_T),
        "case_bottom_above_rail_top": z_lid1,
        "tray_footprint": (2 * BASE_HX, 2 * base_hy),
        "lid_footprint": (2 * LID_HX, LID_Y1 - LID_Y0),
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__)
    report = {"checks": checks()}
    for build in (build_tray, build_lid):
        part = build()
        tris = part.triangles()
        m = check_manifold(tris)
        write_stl(os.path.join(out, f"{part.name}.stl"), tris, part.name)
        report[part.name] = {
            **m,
            "volume_cm3": round(part.volume_mm3() / 1000, 1),
            "bounds": part.bounds(),
        }
    print(json.dumps(report, indent=1))
