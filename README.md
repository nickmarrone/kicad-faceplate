# Eurorack Faceplate Generator for KiCad 10

A KiCad 10 action plugin that turns a circuit PCB into a matching Eurorack faceplate PCB in one click.

## What it does

When invoked from `Tools → External Plugins → Generate Eurorack Faceplate`, the plugin:

1. Reminds you to save the PCB if you haven't (it reads from disk).
2. Asks where to save the output PCB.
3. Copies the saved-on-disk PCB to that path. The original file is never written.
4. On the copy, finds every footprint with a custom `Faceplate` field and replaces it with a panel-hole footprint (jacks become Ø6 mm holes, pots become Ø7 mm holes, etc.) at the same X/Y and rotation.
5. If a footprint also has a `FaceplateName` field, draws that text centered above the hole on F.SilkS.
6. Strips out tracks, zones, drawings, and any non-panel footprints.
7. Replaces the edge cut with a Eurorack-spec rectangle: `(N × 5.08 − 0.3) mm` wide × `128.5 mm` tall, where `N` is the HP detected from the source board's edge cuts (rounded to the nearest integer HP).
8. Adds M3 oval mounting slots (5.5 × 3.2 mm, horizontal) at the canonical Doepfer positions: 7.45 mm in from each side, 3 mm from top and bottom. Two diagonal slots for ≤ 8 HP, four corners for > 8 HP.

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
3. *(Optional)* Add a second custom field `FaceplateName` with whatever short label you want printed above the hole on the panel (e.g. `IN`, `CV`, `RATE`).
4. **Save the PCB** (`Ctrl+S`). The plugin reads from disk — unsaved edits are ignored.
5. Run the plugin. It asks where to save the faceplate, then generates it.

The HP is detected from your source PCB's edge cuts; make sure the outline is roughly the width you want.

### Custom fields, recap

| Field name | Required? | Value | Effect |
| --- | --- | --- | --- |
| `Faceplate` | Yes | `Faceplate:<FootprintName>` | Marks the part as panel-facing and tells the plugin which hole footprint to drop in its place. |
| `FaceplateName` | No | Free text | Drawn on F.SilkS centered above the hole. Always reads horizontally even if the part is rotated. |

## Bundled footprints

| Field value | Hole | Use |
| --- | --- | --- |
| `Faceplate:Jack_3.5mm_Thonkiconn` | Ø6 mm | 3.5 mm mono / stereo jack (Thonkiconn, PJ-301M, Lumberg) |
| `Faceplate:Pot_9mm_Alpha` | Ø7 mm | 9 mm Alpha pot |
| `Faceplate:Pot_16mm_Alpha` | Ø7 mm | 16 mm Alpha pot |
| `Faceplate:LED_3mm_Bezel` | Ø6 mm | 3 mm LED with bezel |
| `Faceplate:LED_5mm_Bezel` | Ø8 mm | 5 mm LED with bezel |
| `Faceplate:LED_0603_LightPipe` | Ø2.5 mm window (no hole) | 0603 LED on a behind-panel PCB shining through bare FR4 |
| `Faceplate:Encoder_EC11` | Ø7 mm | EC11 rotary encoder |
| `Faceplate:Switch_Toggle_SubMini` | Ø4.95 mm with anti-rotation flat (4.55 mm chord on top) | Sub-mini SPDT/DPDT toggle. Rotate the source footprint 90° if you want the flat on the side. |
| `Faceplate:Switch_Tactile_Panel` | Ø7 mm | Panel-mount tactile switch |
| `Faceplate:Switch_Tactile_6x6mm` | Ø6.5 mm | 6×6 mm tactile push button with 6 mm round actuator (0.25 mm side clearance) |
| `Faceplate:MountingHole_M3_Oval` | 5.5 × 3.2 mm slot | M3 mounting slot (auto-added by the plugin) |

All circular hole footprints draw a 0.8 mm wide exposed-copper band on F.Cu just outside the cutout, with matching soldermask opening. This adds a metallic accent ring around each panel cutout once the board is fabricated.

To add your own panel hole, drop a new `.kicad_mod` into `Faceplate.pretty/` and reference it by name in your `Faceplate` field.

### Making `LED_0603_LightPipe` actually transmit light

`LED_0603_LightPipe` is the only footprint that draws **no hole**. It relies on bare FR4 being translucent enough for a behind-panel LED to shine through. To make this work in practice you have to set up the faceplate PCB *and* the circuit PCB carefully — most "it doesn't glow" failures trace back to one of the items below.

**1. Order the faceplate PCB without copper pours over the LED windows.**
The plugin output starts with no copper anywhere, which is what you want. If you later add a ground pour or fill on the faceplate (e.g. for shielding), it will fill the LED window and block the light. Two ways to handle it:
- *Easiest:* don't pour copper on the faceplate at all. Eurorack panels rarely need it.
- *If you must pour:* draw a `Keepout Area` (`Place → Add Keepout Area`) on both `F.Cu` and `B.Cu` covering each LED window. Disable copper-fill in keepouts. Re-pour. Verify in 3D view that the window areas are bare.

**2. Pick a soldermask color that lets light through.**
The plugin already opens soldermask front *and* back over the LED window so bare FR4 is exposed — but elsewhere on the panel, soldermask still affects the look. From most to least translucent:
- **No soldermask / ENIG with bare FR4** — most light, yellowy-green tint.
- **White soldermask** — diffuses light a little; clean appearance.
- **Yellow / clear** — readable glow.
- **Green** — dim glow at best.
- **Black, blue, red** — opaque; light pipe will look dead.
The window itself is bare FR4 regardless of color choice.

**3. Use a high-brightness LED.**
Standard indicator LEDs (~50–200 mcd) are too dim. Pick something rated **≥ 1500 mcd** at 20 mA. For diffuse output, 0603 reverse-mount LEDs (which emit through the body bottom) work especially well in light-pipe configurations.

**4. Keep the LED close to the faceplate.**
Air gaps + FR4 thickness both attenuate. Aim for ≤ 11 mm between the LED's emitting face and the faceplate front. With a circuit-PCB-behind-faceplate sandwich, this is naturally achieved with 11 mm board-to-board headers / standoffs and the LED on the *front* side of the rear PCB.

**5. Test before ordering 10 of them.**
In KiCad: `File → Plot` to gerbers, then drop the gerbers into a viewer (KiCad's gerber viewer or an online one). Confirm the F.Mask and B.Mask layers each show a 2.5 mm circular *opening* at every LED location. If the openings aren't there, the manufacturer will leave soldermask in place and the light pipe won't work.

**6. Drive the LED at a reasonable current.**
You'll lose ~50–80% of brightness through FR4 and soldermask. Run the LED at the upper end of its safe range — but not beyond. Add a series resistor sized for ~15–20 mA.

If you check all six and it's still dim, switch to a `LED_3mm_Bezel` or `LED_5mm_Bezel` cutout and accept the visible bezel — those bypass FR4 entirely.

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
- **The plugin reads the source PCB from disk.** Save your PCB before running — unsaved in-editor edits are not visible to the plugin. The plugin copies the file at the filesystem level (`shutil.copyfile`) and refuses to write to the source path, so the original PCB is never modified.
- The bundled `Faceplate` library is registered as a *global* library by `install.sh`'s instructions. If you'd rather scope it per-project, add it under `Project Specific Libraries` instead.
