# Eurorack Faceplate Generator for KiCad 10

A KiCad 10 action plugin that turns a circuit PCB into a matching Eurorack faceplate PCB in one click.

## What it does

When invoked from `Tools → External Plugins → Generate Eurorack Faceplate`, the plugin:

1. Asks where to save the output PCB.
2. Copies the current PCB to that path.
3. On the copy, finds every footprint with a custom `Faceplate` field and replaces it with a panel-hole footprint (jacks become Ø6 mm holes, pots become Ø7 mm holes, etc.) at the same X/Y and rotation.
4. Strips out tracks, zones, drawings, and any non-panel footprints.
5. Replaces the edge cut with a Eurorack-spec rectangle: `(N × 5.08 − 0.3) mm` wide × `128.5 mm` tall, where `N` is the HP detected from the source board's edge cuts (rounded to the nearest integer HP).
6. Adds M3 oval mounting slots (5.5 × 3.2 mm, horizontal) at the canonical Doepfer positions: 7.45 mm in from each side, 3 mm from top and bottom. Two diagonal slots for ≤ 8 HP, four corners for > 8 HP.

The original PCB is never modified.

## Install

```sh
./install.sh
```

Then, in KiCad: `Preferences → Manage Footprint Libraries → Global Libraries → +`

| Field | Value |
| --- | --- |
| Nickname | `Faceplate` |
| Library Path | `<repo>/Faceplate.pretty` |
| Plugin Type | KiCad |

Restart KiCad (or `Tools → External Plugins → Refresh Plugins` inside pcbnew) and the plugin appears under `Tools → External Plugins`.

## Usage in your circuit PCB

1. Lay out the circuit so panel-facing parts (jacks, pots, switches, LEDs) sit at the X/Y you want them on the faceplate.
2. For each panel-facing footprint, add a custom field:
    - **Field name:** `Faceplate`
    - **Field value:** `Faceplate:<FootprintName>` — for example `Faceplate:Jack_3.5mm_Thonkiconn`.
3. Run the plugin. Done.

The HP is detected from your source PCB's edge cuts; make sure the outline is roughly the width you want.

## Bundled footprints

| Field value | Hole | Use |
| --- | --- | --- |
| `Faceplate:Jack_3.5mm_Thonkiconn` | Ø6 mm | 3.5 mm mono / stereo jack (Thonkiconn, PJ-301M, Lumberg) |
| `Faceplate:Pot_9mm_Alpha` | Ø7 mm | 9 mm Alpha pot |
| `Faceplate:Pot_16mm_Alpha` | Ø7 mm | 16 mm Alpha pot |
| `Faceplate:LED_3mm_Bezel` | Ø6 mm | 3 mm LED with bezel |
| `Faceplate:LED_5mm_Bezel` | Ø8 mm | 5 mm LED with bezel |
| `Faceplate:Encoder_EC11` | Ø7 mm | EC11 rotary encoder |
| `Faceplate:Switch_Toggle_SubMini` | Ø6.35 mm | Sub-mini SPDT/DPDT toggle (Salecom T8011) |
| `Faceplate:Switch_Tactile_Panel` | Ø7 mm | Panel-mount tactile switch |
| `Faceplate:MountingHole_M3_Oval` | 5.5 × 3.2 mm slot | M3 mounting slot (auto-added by the plugin) |

To add your own panel hole, drop a new `.kicad_mod` into `Faceplate.pretty/` and reference it by name in your `Faceplate` field.

## Constants

`faceplate_plugin/constants.py` holds the dimensions:

```
FACEPLATE_HEIGHT_MM       = 128.5
HP_MM                     = 5.08
HP_KERF_MM                = 0.3      # so adjacent modules don't bind
MOUNT_HOLE_INSET_X_MM     = 7.45     # centerline from each side edge
MOUNT_HOLE_INSET_Y_MM     = 3.0      # centerline from top/bottom
MOUNT_HOLE_HP_THRESHOLD   = 8        # > this HP: 4 holes; ≤ this: 2 diagonal
```

## Sources

- Doepfer A-100 mechanical specs — <https://doepfer.de/a100_man/a100m_e.htm>
- Exploding Shed: Standards of Eurorack — <https://www.exploding-shed.com/synth-diy-guides/standards-of-eurorack/eurorack-dimensions/>
- N8 Synthesizers panel-mounting guides — <https://www.n8synth.co.uk/guides/>

## Caveats

- KiCad 10's SWIG-based `pcbnew` Python API is officially deprecated (slated for removal in v11). This plugin works on v10; future migration to KiCad's IPC API would be a separate effort.
- The plugin never mutates your live board. It copies the source PCB at the filesystem level and operates on the copy — sidestepping the known v10 issue where `SaveBoard()` on the open board can corrupt internal state.
- The bundled `Faceplate` library is registered as a *global* library by `install.sh`'s instructions. If you'd rather scope it per-project, add it under `Project Specific Libraries` instead.
