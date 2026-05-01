# Eurorack Faceplate Generator — KiCad 10 Action Plugin

## Context

You are designing Eurorack modules in KiCad 10. After laying out the circuit PCB, you want a one-click way to generate a matching faceplate PCB: same X/Y for panel-facing parts (pots, jacks, switches, LEDs), but with the correct hole sizes drawn on `Edge.Cuts`, the canonical 128.5 mm Eurorack height, M3 mounting holes in the corners, and everything else (tracks, zones, non-panel parts) stripped out. This plan describes a self-contained KiCad 10 action plugin plus a small footprint library that ships with it.

Confirmed design choices (from clarifying questions):
- Invocation: KiCad action plugin (Tools → External Plugins).
- Width: auto-calculated from the source PCB's existing `Edge.Cuts` bounding box, snapped to the nearest HP.
- Mapping: each circuit footprint that should appear on the panel carries a custom field `Faceplate` whose value is `LibraryNickname:FootprintName`.
- Library: ships with the plugin as `Faceplate.pretty/`.

## Eurorack constants used by the plugin

| Quantity | Value |
| --- | --- |
| Faceplate height | 128.5 mm |
| Width per HP | 5.08 mm |
| Width formula | `HP × 5.08 − 0.3 mm` |
| Mounting hole | Horizontal oval slot, 3.2 mm tall × 5.5 mm wide, M3 |
| Mounting hole inset (vertical) | 3.0 mm from top and bottom (centerline) |
| Mounting hole inset (horizontal) | 7.45 mm from each side edge (centerline) |
| Mounting hole count | 2 diagonally (≤8 HP) or 4 (>8 HP) — configurable constant |

The oval is oriented horizontally — long axis along X — so the module can shift laterally on the rails to absorb rack tolerance, per Doepfer.

Sources are documented in the README the plugin will ship with.

## Repository layout

```
kicad-faceplate/
├── README.md                      # install + usage
├── install.sh                     # symlinks plugin and library into KiCad config dirs
├── faceplate_plugin/
│   ├── __init__.py                # registers ActionPlugin on import
│   ├── plugin.py                  # ActionPlugin class + wxPython save dialog
│   ├── transform.py               # pure transform functions (testable)
│   └── constants.py               # Eurorack dimensions, layer names
└── Faceplate.pretty/              # KiCad footprint library
    ├── Jack_3.5mm_Thonkiconn.kicad_mod   # Ø6 mm
    ├── Pot_9mm_Alpha.kicad_mod           # Ø7 mm
    ├── Pot_16mm_Alpha.kicad_mod          # Ø7 mm
    ├── MountingHole_M3_Oval.kicad_mod     # 3.2 × 5.5 mm horizontal oval NPTH
    ├── LED_3mm_Bezel.kicad_mod           # Ø6 mm
    ├── LED_5mm_Bezel.kicad_mod           # Ø8 mm
    ├── Encoder_EC11.kicad_mod            # Ø7 mm
    ├── Switch_Toggle_SubMini.kicad_mod   # Ø6.35 mm
    └── Switch_Tactile_Panel.kicad_mod    # Ø7 mm
```

Each `.kicad_mod` is a small s-expression file that draws an `fp_circle` on `Edge.Cuts` at the hole diameter, an `fp_text reference REF**` on `F.SilkS`, and `attr (exclude_from_pos_files exclude_from_bom)`. Mounting holes additionally include an NPTH pad. The files are written by hand from a template — no library generator needed.

## Plugin algorithm (`faceplate_plugin/plugin.py` + `transform.py`)

The action plugin's `Run()`:

1. `board = pcbnew.GetBoard()` — get the currently open PCB. If unsaved, abort with a `wx.MessageBox` asking the user to save first.
2. Open a `wx.FileDialog` (save mode, default name `<original>_faceplate.kicad_pcb`, default dir = same folder as the source).
3. `shutil.copy(src_path, dest_path)` — copy the PCB at the filesystem level. This sidesteps the known KiCad 10 issue where `SaveBoard()` from within an action plugin on the live board can corrupt internal state.
4. `dest_board = pcbnew.LoadBoard(dest_path)` — load the copy as a fresh `BOARD`. All subsequent mutations happen on this object, never on `GetBoard()`.
5. Hand off to `transform.build_faceplate(dest_board)` (the pure function — no GUI, fully unit-testable).
6. `pcbnew.SaveBoard(dest_path, dest_board)`.
7. Show a confirmation dialog with the output path and ask if the user wants to open it (re-open via `pcbnew.LoadBoard` returning to the GUI is awkward; just show the path and let the user open it manually).

`transform.build_faceplate(board)` does, in order:

1. **Measure HP.** Compute the bounding box of all `PCB_SHAPE` drawings whose layer is `Edge.Cuts`. Width in mm = `bbox.width / 1e6`. Solve for HP: `HP = round((width_mm + 0.3) / 5.08)`. Store `panel_width_mm = HP × 5.08 − 0.3`.
2. **Identify panel footprints.** Iterate `board.GetFootprints()`. A footprint is a panel part iff `footprint.GetProperties().get("Faceplate")` is non-empty. Read both the field value (`lib:name`) and the original `(x, y, rot, reference)` for each. Use `GetProperties()` rather than the deprecated `GetFieldByName` — the research notes this changed in v9/10.
3. **Compute the new origin.** Translate the whole panel so the source `Edge.Cuts` bbox top-left maps to `(0, 0)` on the destination, and the panel sits centered vertically within the 128.5 mm faceplate frame. `dy_center = (128.5 − bbox.height_mm) / 2`. Save `(dx, dy)` so panel footprints land at the right place.
4. **Strip non-panel content.**
   - Remove every track (`board.GetTracks()` — covers PCB_TRACK and PCB_VIA).
   - Remove every zone (`board.Zones()`).
   - Remove every drawing (`board.GetDrawings()`) regardless of layer (the new edge cut and any silk we want gets re-added in step 6).
   - Remove every footprint that is **not** a panel footprint.
   - Use `board.RemoveNative(item)` per the v10 notes from research.
5. **Replace panel footprints.** For each saved `(lib_name, x, y, rot, ref)`:
   - `new_fp = pcbnew.FootprintLoad(lib_path, name)` where `lib_path` resolves through KiCad's FP_LIB_TABLE. Resolve `lib:name` by first trying the global lib table; fall back to a path inside the plugin (`Faceplate.pretty/`) if the user hasn't registered it yet.
   - Apply `(dx, dy)` translation: `new_fp.SetPosition(pcbnew.wxPointMM(x_mm + dx, y_mm + dy))`.
   - `new_fp.SetOrientationDegrees(rot)`.
   - `new_fp.SetReference(ref)` (preserves designators so the user can correlate to schematic).
   - Remove the old footprint, then `board.Add(new_fp)`.
6. **Draw the new edge cut rectangle.** Four `PCB_SHAPE` segments forming a rectangle from `(0, 0)` to `(panel_width_mm, 128.5)` on `Edge.Cuts`, line width 0.05 mm.
7. **Add mounting holes.** Load `Faceplate:MountingHole_M3_Oval` from the bundled library. Place at:
   - `(7.45, 3.0)` and `(panel_width_mm − 7.45, 128.5 − 3.0)` for ≤8 HP (diagonal).
   - All four corners — `(7.45, 3.0)`, `(panel_width_mm − 7.45, 3.0)`, `(7.45, 125.5)`, `(panel_width_mm − 7.45, 125.5)` — for >8 HP.
8. Done — return the mutated board.

Coordinate conversions go through `pcbnew.FromMM` / `pcbnew.ToMM` / `pcbnew.wxPointMM`. Angles are in degrees via `SetOrientationDegrees` (the legacy tenths-of-a-degree API still works but is more error-prone).

## Library footprints — content sketch

Every panel hole footprint follows the same shape. Example for `Jack_3.5mm_Thonkiconn.kicad_mod`:

```
(footprint "Jack_3.5mm_Thonkiconn"
  (version 20240108)
  (generator "kicad-faceplate")
  (layer "F.Cu")
  (descr "Eurorack panel hole for 3.5mm jack (Thonkiconn / PJ-301M)")
  (attr exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
  (fp_text reference "J**" (at 0 -4) (layer "F.SilkS"))
  (fp_text value "Jack_3.5mm_Thonkiconn" (at 0 4) (layer "F.Fab") hide)
  (fp_circle (center 0 0) (end 3 0) (stroke (width 0.05) (type default)) (layer "Edge.Cuts"))
)
```

`MountingHole_M3_Oval.kicad_mod` uses an oval NPTH pad — long axis along X, no Edge.Cuts circle (KiCad mills the slot from the pad's drill geometry):

```
(pad "" np_thru_hole oval (at 0 0) (size 5.5 3.2) (drill oval 5.5 3.2) (layers "*.Cu" "*.Mask"))
```

Hole diameters per the research:

| Footprint | Edge.Cuts circle radius |
| --- | --- |
| `Jack_3.5mm_Thonkiconn` | 3.0 mm (Ø6) |
| `Pot_9mm_Alpha`, `Pot_16mm_Alpha`, `Switch_Tactile_Panel`, `Encoder_EC11` | 3.5 mm (Ø7) |
| `Switch_Toggle_SubMini` | 3.175 mm (Ø6.35) |
| `LED_3mm_Bezel` | 3.0 mm (Ø6) |
| `LED_5mm_Bezel` | 4.0 mm (Ø8) |
| `MountingHole_M3_Oval` | 5.5 × 3.2 mm oval slot (no Edge.Cuts circle — slot rendered from oval NPTH pad drill) |

## install.sh

Symlinks `faceplate_plugin/` into `~/.config/kicad/10.0/scripting/plugins/faceplate_plugin/` and `Faceplate.pretty/` into `~/.config/kicad/10.0/Faceplate.pretty/` (or `~/.local/share/kicad/10.0/footprints/Faceplate.pretty/`). Prints a reminder to add `Faceplate` to the global FP_LIB_TABLE via Preferences → Manage Footprint Libraries (or appends it programmatically if the file exists). Idempotent — re-running is safe.

## Verification plan

1. **Smoke test the library files.** Open KiCad 10 footprint editor → load `Faceplate:Jack_3.5mm_Thonkiconn`. Confirm the circle sits on `Edge.Cuts` at Ø6 mm and there's no copper, courtyard warnings, or DRC errors.
2. **Build a synthetic 4 HP test PCB.** Create a fresh `.kicad_pcb` with a small rectangular `Edge.Cuts` (e.g., 20.02 mm × 60 mm), three footprints — one Thonkiconn jack, one 9 mm pot, one 3 mm LED — each with the `Faceplate` field set (`Faceplate:Jack_3.5mm_Thonkiconn`, etc). Add a couple of dummy tracks and a copper zone to confirm cleanup.
3. **Run the plugin.** Tools → External Plugins → "Generate Eurorack Faceplate". Save to `test_4hp_faceplate.kicad_pcb`.
4. **Verify the output:**
   - Open the result. Edge cut is a rectangle exactly 20.02 mm × 128.5 mm (HP=4, so width = 4 × 5.08 − 0.3 = 20.02).
   - Original tracks, zones, and non-panel footprints are gone.
   - The three panel footprints kept their X positions and original references; they are vertically centered.
   - Two M3 oval mounting slots (5.5 × 3.2 mm, horizontal) at `(7.45, 3.0)` and `(12.57, 125.5)` (diagonal placement, since 4 HP ≤ 8 HP).
   - DRC passes with no errors.
5. **Wide-module test.** Repeat with a 14 HP source PCB; confirm 4 mounting holes appear at all corners and the calculated width is `14 × 5.08 − 0.3 = 70.82` mm.
6. **HP rounding sanity check.** Build a source PCB with edge cuts that don't quite match an integer HP (e.g., 19.5 mm wide) — confirm the plugin snaps to 4 HP.
7. **Manual print check (optional).** Export the resulting faceplate as PDF at 1:1 scale; verify with calipers that hole spacing matches.

## Critical files / functions to reuse

Nothing exists in the repo yet (it's an empty git init). Everything in this plan creates new files. External pieces being relied on:

- `pcbnew.ActionPlugin`, `pcbnew.GetBoard`, `pcbnew.LoadBoard`, `pcbnew.SaveBoard`, `pcbnew.FootprintLoad`, `pcbnew.PCB_SHAPE`, `pcbnew.wxPointMM`, `pcbnew.FromMM`, `pcbnew.ToMM` — all from KiCad 10's bundled `pcbnew` module.
- KiCad's FP_LIB_TABLE for resolving `Faceplate:*` library references (the install script registers it; the plugin falls back to bundled path if absent).

## Known caveats noted during research

- `SaveBoard()` called on the live `GetBoard()` inside an action plugin can corrupt board state in v10 (see KiCad gitlab issue 11323). Mitigation: we never mutate `GetBoard()`; we copy the file at the OS level, `LoadBoard` the copy, and save that.
- `GetFieldByName()` was removed in v9. Use `footprint.GetProperties()` (returns a dict-like object). The plugin will use `.get("Faceplate")` and treat missing/empty as "not a panel part".
- The SWIG-based `pcbnew` module is deprecated in v9 and slated for removal in v11; this plugin targets v10's still-working SWIG API. A future migration to KiCad's IPC API would be a separate effort.
