"""Pure transform that turns a circuit PCB into a Eurorack faceplate PCB.

Operates on a freshly-loaded `pcbnew.BOARD` (never the live `pcbnew.GetBoard()`).
"""

import os

import pcbnew

from .constants import (
    EDGE_CUT_LINE_WIDTH_MM,
    FACEPLATE_FIELD_NAME,
    FACEPLATE_HEIGHT_MM,
    FACEPLATE_ORIGIN_X_MM,
    FACEPLATE_ORIGIN_Y_MM,
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
    """Mutate `board` into a Eurorack faceplate. Returns (hp, panel_count, diag)."""
    src_bbox = _edge_cuts_bbox(board)
    src_x_mm = pcbnew.ToMM(src_bbox.GetX())
    src_y_mm = pcbnew.ToMM(src_bbox.GetY())
    src_w_mm = pcbnew.ToMM(src_bbox.GetWidth())
    src_h_mm = pcbnew.ToMM(src_bbox.GetHeight())

    hp = _round_to_hp(src_w_mm)
    panel_w_mm = hp * HP_MM - HP_KERF_MM

    panel_specs, diag = _snapshot_panel_footprints(board)

    # Translate from the source PCB's coordinate space into the destination
    # faceplate space: source bbox top-left -> faceplate origin, with the
    # source content centered vertically inside the 128.5 mm faceplate.
    dx_mm = FACEPLATE_ORIGIN_X_MM - src_x_mm
    dy_mm = FACEPLATE_ORIGIN_Y_MM - src_y_mm + (FACEPLATE_HEIGHT_MM - src_h_mm) / 2.0

    _strip_board(board)

    for spec in panel_specs:
        new_fp = _load_faceplate_footprint(spec["name"])
        new_fp.SetPosition(_point_mm(spec["x_mm"] + dx_mm, spec["y_mm"] + dy_mm))
        new_fp.SetOrientationDegrees(spec["rot_deg"])
        new_fp.SetReference(spec["reference"])
        board.Add(new_fp)

    _add_edge_rect(
        board,
        FACEPLATE_ORIGIN_X_MM,
        FACEPLATE_ORIGIN_Y_MM,
        FACEPLATE_ORIGIN_X_MM + panel_w_mm,
        FACEPLATE_ORIGIN_Y_MM + FACEPLATE_HEIGHT_MM,
    )
    _add_mounting_holes(board, hp, panel_w_mm)

    return hp, len(panel_specs), diag


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
    """Return (specs, diag). `diag` lists every footprint and its field/property keys
    so we can show useful feedback if no panel footprints are detected."""
    specs = []
    diag_lines = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        field_value = _get_field_value(fp, FACEPLATE_FIELD_NAME)
        keys = _all_field_keys(fp)
        diag_lines.append(f"  {ref}: keys={sorted(keys) or '<none>'}")
        if not field_value:
            continue
        pos = fp.GetPosition()
        specs.append({
            "name": _resolve_footprint_name(field_value),
            "x_mm": pcbnew.ToMM(pos.x),
            "y_mm": pcbnew.ToMM(pos.y),
            "rot_deg": fp.GetOrientationDegrees(),
            "reference": ref,
        })
    return specs, "\n".join(diag_lines)


def _all_field_keys(footprint):
    """Best-effort enumeration of every field/property name on a footprint, for diagnostics."""
    keys = set()
    try:
        for field in footprint.GetFields():
            try:
                keys.add(field.GetName())
            except Exception:
                pass
            try:
                keys.add(field.GetCanonicalName())
            except Exception:
                pass
    except Exception:
        pass
    try:
        props = footprint.GetProperties()
        try:
            keys.update(list(props.keys()))
        except (AttributeError, TypeError):
            try:
                for k in props:
                    keys.add(k)
            except TypeError:
                pass
    except (AttributeError, TypeError):
        pass
    keys.discard("")
    return keys


def _get_field_value(footprint, name):
    """Read a custom field from a footprint. Tries every API KiCad 10 exposes."""
    # Canonical v10: FOOTPRINT.HasField/GetField (string-keyed).
    try:
        if footprint.HasField(name):
            field = footprint.GetField(name)
            if field is not None:
                value = field.GetText()
                if value:
                    return value
    except (AttributeError, TypeError):
        pass

    # Fallback 1: iterate PCB_FIELDS, matching either GetName() or GetCanonicalName().
    try:
        for field in footprint.GetFields():
            try:
                names = (field.GetName(), field.GetCanonicalName())
            except AttributeError:
                names = (field.GetName(),)
            if name in names:
                value = field.GetText()
                if value:
                    return value
    except (AttributeError, TypeError):
        pass

    # Fallback 2: GetProperties() dict (used for footprint-level metadata).
    try:
        props = footprint.GetProperties()
        if hasattr(props, "__contains__") and name in props:
            value = props[name]
            if value:
                return value
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
    left = FACEPLATE_ORIGIN_X_MM + MOUNT_HOLE_INSET_X_MM
    right = FACEPLATE_ORIGIN_X_MM + panel_w_mm - MOUNT_HOLE_INSET_X_MM
    top = FACEPLATE_ORIGIN_Y_MM + MOUNT_HOLE_INSET_Y_MM
    bottom = FACEPLATE_ORIGIN_Y_MM + FACEPLATE_HEIGHT_MM - MOUNT_HOLE_INSET_Y_MM

    if hp <= MOUNT_HOLE_HP_THRESHOLD:
        positions = [(left, top), (right, bottom)]
    else:
        positions = [(left, top), (right, top), (left, bottom), (right, bottom)]

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
