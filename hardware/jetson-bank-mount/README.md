# Jetson case + power bank mount for the UGV01

Two printed parts stack the UGREEN PB205 power bank and the Waveshare Jetson case
(JETSON-ORIN-CASE-A) on the UGV01's two 1020 rails. Nothing touches the deck, so the
deck's 40-pin header and screw heads stay clear.

```
          [ Jetson case 122 x 95 x 45 ]   <- 2 x M3 into the case's bottom holes
          [ lid.stl  152 x 100 x 5    ]   <- 4 x M3 down into the tray bosses
   [ tray.stl 192 x 168, walls 28 tall ]  holds the bank 160 x 81 x 27, ports at the rear
   ===rail===                 ===rail===  <- 4 x M4 + drop-in T-nuts, rails 170 mm apart
```

The bank's display (~13-28 mm from the port end) and button (~36-47 mm) are on a long
side (measured on 13 October, the button ends ~40 mm from the port end).
Side-wall windows over the rear 58 mm (4 mm stub) keep them reachable; the walls hold
the other 106 mm. Height above the rails: 37 mm to case bottom, 82 mm to case top.

## Hardware

| Where | Parts |
| --- | --- |
| Tray to rails | 4 x M4 drop-in T-nuts (20-series, 6 mm slot) + 4 x M4 x 8 screws |
| Lid to tray | 4 x M3 x 10 or 12, self-tapping into the 2.6 mm boss holes (or `BOSS_HOLE = 4.0` and M3 heat-set inserts) |
| Case to lid | 2 x M3 x 6 (up to 8), pan or countersunk, from below; heads sit in pockets |

## Printing and assembly

PETG (a warm bank, sunlight; PLA works indoors): 0.2 mm layers, 4 perimeters, 30 %
infill, no supports. `tray.stl` prints flat side down (192 x 168 mm: check your bed),
`lid.stl` flipped, pocket side up. The tray's rail slots are 6 mm long to absorb
spacing error, and the lid's case slots fit 60-70 mm hole spacing; 1-2 mm foam tape
takes up the bank's 1 mm play. A barrel-jack cable runs from the bank's rear ports to
the DC jack on the case's rear face.

## Changing it

Dimensions are parameters at the top of `mount.py`. Run `python3 mount.py` for the STLs,
`python3 render_iso.py` for pictures. `boxcad.py` is a small box-union modeller, so holes
are square. Sources: Waveshare case drawing (122 x 95 x 45), UGV01 drawing (rails 170 mm
centres, 144 mm long), PB205 spec (160 x 80.8 x 26.7), case holes measured at ~65 mm.

## As built (19 October 2026)

Tray bolted on with the UGV01 kit's own T-nuts and screws. Lid fitted pocket side down.
Case ports face the rear. Some suggested screw sizes were too big; only M3 worked. The
two case screws are only hand-snug: the bottom holes are open through to the board.
