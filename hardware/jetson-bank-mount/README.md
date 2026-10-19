# Jetson case + power bank mount for the UGV01

Two printed parts that stack the UGREEN PB205 power bank and the Waveshare
Jetson case (JETSON-ORIN-CASE-A) on the UGV01's two 1020 rails. Nothing
touches the deck, so the 40-pin header and screw heads underneath are cleared,
and the case can face any direction (ports to the rear as built).

```
          [ Jetson case 122 x 95 x 45 ]   <- 2 x M3 into the case's bottom holes
          [ lid.stl  152 x 100 x 5    ]   <- 4 x M3 down into the tray bosses
   [ tray.stl 192 x 168, walls 28 tall ]  holds the bank 160 x 81 x 27, ports at the rear
   ===rail===                 ===rail===  <- 4 x M4 + drop-in T-nuts, rails 170 mm apart
```

The bank's display and button are on its long side face, next to the port
end (display ~13-28 mm from the end, button ~36-47 mm). Both side walls have a
window over the rear 58 mm, down to a 4 mm stub, so they stay visible and
reachable from the side of the robot. The walls still hold the bank sideways
over the remaining 106 mm, plus the front wall, rear lip and lid.

Stack height above the rail tops: 37 mm to the case bottom, 82 mm to the case top.

## Hardware

| Where | Parts |
| --- | --- |
| Tray to rails | 4 x M4 drop-in T-nuts (20-series, 6 mm slot) + 4 x M4 x 8 screws |
| Lid to tray | 4 x M3 x 10 or 12, self-tapping into the 2.6 mm boss holes (or set `BOSS_HOLE = 4.0` and use M3 heat-set inserts) |
| Case to lid | 2 x M3 x 6 (up to 8), pan or countersunk, from below; the heads sit in pockets |

## Printing

- PETG preferred (the bank gets warm, and the robot will sit in sunlight); PLA works indoors.
- 0.2 mm layers, 4 perimeters, 30 % infill, no supports.
- `tray.stl` prints as is (flat side down). Footprint 192 x 168 mm: check your bed.
- `lid.stl` prints flipped (pocket side up) so the pockets and slots need no support.

## Assembly

1. Drop four T-nuts into the rail slots and bolt the tray down (slots are 6 mm long across the rail to absorb spacing error).
2. Case upside down; put the lid on it with the pockets facing the case, and drive the two M3 screws through the slots into the case's threaded holes. The slots allow 60-70 mm hole spacing.
3. Put the power bank in the tray, ports toward the rear (the low lip); the display and button stay reachable behind the lid.
   Optional: a strip of 1-2 mm foam tape on the lid's underside, or on the floor, takes up the 1 mm play so nothing rattles.
4. Lower lid + case onto the four bosses and fit the four M3 screws.
5. Barrel-jack cable from the bank's rear ports up to the DC jack on the case's rear face.

## Changing it

All dimensions are parameters at the top of `mount.py`. Re-run
`python3 mount.py` to regenerate the STLs and `python3 render_iso.py` for the
pictures. `boxcad.py` is a small pure-Python box-union modeller: holes are
square, which is fine for printed parts.

Sources for the dimensions: Waveshare case drawing (122 x 95 x 45), UGV01
drawing (rails 170 mm centres, 144 mm long), UGREEN PB205 spec (160 x 80.8 x 26.7),
and the case's bottom holes measured at ~65 mm.

## As built (19 October 2026)

- Tray bolted to the rails with the UGV01 kit's own drop-in T-nuts and screws.
- The lid printed pocket side up; fitted pocket side down, which is correct.
- Some of the suggested screw sizes were too big in practice; only M3 worked.
- The two case screws are only hand-snug: the case's bottom holes are open
  through to the board, so a too-long screw can touch it. Before tightening,
  measure how deep the hole goes and use a screw that ends short of that, or
  add a washer under the head.
