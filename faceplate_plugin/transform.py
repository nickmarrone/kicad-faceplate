"""Pure transform that turns a circuit PCB into a Eurorack faceplate PCB.

Operates on a freshly-loaded `pcbnew.BOARD` (never the live `pcbnew.GetBoard()`).
"""

import os

import pcbnew

from .constants import (
    EDGE_CUT_LINE_WIDTH_MM,
    FACEPLATE_FIELD_NAME,
    FACEPLATE_HEIGHT_MM,
    HP_KERF_MM,
    HP_MM,
    MOUNT_HOLE_HP_THRESHOLD,
    MOUNT_HOLE_INSET_X_MM,
    MOUNT_HOLE_INSET_Y_MM,
    MOUNTING_HOLE_FOOTPRINT,
)

# realpath so the symlinked install at ~/.config/kicad/.../scripting/plugins/
# resolves back to the repo's Faceplate.pretty.
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
FACEPLATE_LIB_PATH = os.path.join(PLUGIN_DIR, "Faceplate.pretty")


def build_faceplate(board):
    """Mutate `board` into a Eurorack faceplate. Returns the HP detected."""
    src_bbox = _edge_cuts_bbox(board)
    src_x_mm = pcbnew.ToMM(src_bbox.GetX())
    src_y_mm = pcbnew.ToMM(src_bbox.GetY())
    src_w_mm = pcbnew.ToMM(src_bbox.GetWidth())
    src_h_mm = pcbnew.ToMM(src_bbox.GetHeight())

    hp = _round_to_hp(src_w_mm)
    panel_w_mm = hp * HP_MM - HP_KERF_MM

    panel_specs = _snapshot_panel_footprints(board)

    dx_mm = -src_x_mm
    dy_mm = -src_y_mm + (FACEPLATE_HEIGHT_MM - src_h_mm) / 2.0

    _strip_board(board)

    for spec in panel_specs:
        new_fp = _load_faceplate_footprint(spec["name"])
        new_fp.SetPosition(_point_mm(spec["x_mm"] + dx_mm, spec["y_mm"] + dy_mm))
        new_fp.SetOrientationDegrees(spec["rot_deg"])
        new_fp.SetReference(spec["reference"])
        board.Add(new_fp)

    _add_edge_rect(board, 0.0, 0.0, panel_w_mm, FACEPLATE_HEIGHT_MM)
    _add_mounting_holes(board, hp, panel_w_mm)

    return hp


def _edge_cuts_bbox(board):
    bbox = None
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            shape_bbox = drawing.GetBoundingBox()
            if bbox is None:
                bbox = shape_bbox
            else:
                bbox.Merge(shape_bbox)
    if bbox is None:
        raise RuntimeError(
            "No Edge.Cuts drawings found on the source PCB. "
            "Draw the circuit board outline before running the plugin."
        )
    return bbox


def _round_to_hp(width_mm):
    hp = int(round((width_mm + HP_KERF_MM) / HP_MM))
    return max(1, hp)


def _snapshot_panel_footprints(board):
    specs = []
    for fp in board.GetFootprints():
        field_value = _get_field_value(fp, FACEPLATE_FIELD_NAME)
        if not field_value:
            continue
        pos = fp.GetPosition()
        specs.append({
            "name": _resolve_footprint_name(field_value),
            "x_mm": pcbnew.ToMM(pos.x),
            "y_mm": pcbnew.ToMM(pos.y),
            "rot_deg": fp.GetOrientationDegrees(),
            "reference": fp.GetReference(),
        })
    return specs


def _get_field_value(footprint, name):
    """Read a custom field from a footprint. KiCad 9/10 removed GetFieldByName."""
    try:
        for field in footprint.GetFields():
            if field.GetName() == name:
                value = field.GetText()
                return value or None
    except AttributeError:
        pass
    try:
        props = footprint.GetProperties()
        if name in props:
            return props[name] or None
    except (AttributeError, TypeError):
        pass
    return None


def _resolve_footprint_name(field_value):
    """`Lib:Name` -> `Name`. Plain `Name` passes through."""
    return field_value.split(":", 1)[1] if ":" in field_value else field_value


_io_plugin_cache = None


def _kicad_io_plugin():
    """Return the KiCad sexp PCB IO plugin. Cached so we only look it up once.

    `pcbnew.FootprintLoad` is a wrapper that guesses the plugin type from the
    library path; on a missing/empty path it returns None, leading to confusing
    `NoneType` errors. Using PCB_IO_MGR directly is more reliable.
    """
    global _io_plugin_cache
    if _io_plugin_cache is None:
        _io_plugin_cache = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
        if _io_plugin_cache is None:
            raise RuntimeError("KiCad sexp PCB IO plugin is unavailable.")
    return _io_plugin_cache


def _load_faceplate_footprint(name):
    if not os.path.isdir(FACEPLATE_LIB_PATH):
        raise RuntimeError(
            f"Faceplate library directory not found:\n  {FACEPLATE_LIB_PATH}\n"
            f"Make sure Faceplate.pretty/ sits next to faceplate_plugin/ in the repo, "
            f"and that the plugin install is a symlink (so realpath resolves correctly)."
        )
    io = _kicad_io_plugin()
    fp = io.FootprintLoad(FACEPLATE_LIB_PATH, name)
    if fp is None:
        raise RuntimeError(
            f"Could not load footprint '{name}' from {FACEPLATE_LIB_PATH}. "
            f"Confirm {name}.kicad_mod exists in Faceplate.pretty/."
        )
    return fp


def _strip_board(board):
    for track in list(board.GetTracks()):
        board.RemoveNative(track)
    for zone in list(_get_zones(board)):
        board.RemoveNative(zone)
    for drawing in list(board.GetDrawings()):
        board.RemoveNative(drawing)
    for fp in list(board.GetFootprints()):
        board.RemoveNative(fp)


def _get_zones(board):
    if hasattr(board, "Zones"):
        return board.Zones()
    return board.GetZones()


def _add_edge_rect(board, x0, y0, x1, y1):
    edges = [
        (x0, y0, x1, y0),
        (x1, y0, x1, y1),
        (x1, y1, x0, y1),
        (x0, y1, x0, y0),
    ]
    for ax, ay, bx, by in edges:
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(_point_mm(ax, ay))
        seg.SetEnd(_point_mm(bx, by))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(EDGE_CUT_LINE_WIDTH_MM))
        board.Add(seg)


def _add_mounting_holes(board, hp, panel_w_mm):
    inset_x = MOUNT_HOLE_INSET_X_MM
    inset_y_top = MOUNT_HOLE_INSET_Y_MM
    inset_y_bot = FACEPLATE_HEIGHT_MM - MOUNT_HOLE_INSET_Y_MM

    if hp <= MOUNT_HOLE_HP_THRESHOLD:
        positions = [
            (inset_x, inset_y_top),
            (panel_w_mm - inset_x, inset_y_bot),
        ]
    else:
        positions = [
            (inset_x, inset_y_top),
            (panel_w_mm - inset_x, inset_y_top),
            (inset_x, inset_y_bot),
            (panel_w_mm - inset_x, inset_y_bot),
        ]

    for i, (x, y) in enumerate(positions, start=1):
        hole = _load_faceplate_footprint(MOUNTING_HOLE_FOOTPRINT)
        hole.SetPosition(_point_mm(x, y))
        hole.SetReference(f"H{i}")
        board.Add(hole)


def _point_mm(x_mm, y_mm):
    """Build a position in KiCad internal units. Tries v10's VECTOR2I, falls back to wxPoint."""
    nm_x = pcbnew.FromMM(x_mm)
    nm_y = pcbnew.FromMM(y_mm)
    if hasattr(pcbnew, "VECTOR2I"):
        return pcbnew.VECTOR2I(nm_x, nm_y)
    return pcbnew.wxPoint(nm_x, nm_y)
