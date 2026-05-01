"""Eurorack mechanical constants used by the faceplate plugin.

Sources: Doepfer A-100 construction details, Exploding Shed Eurorack Dimensions.
"""

FACEPLATE_HEIGHT_MM = 128.5
HP_MM = 5.08
HP_KERF_MM = 0.3

# Top-left corner of the generated faceplate in the destination PCB's coordinate
# system. KiCad's drawing canvas starts at (0, 0) but a small inset is friendlier
# for plotting and keeps the board off the page edge.
FACEPLATE_ORIGIN_X_MM = 50.0
FACEPLATE_ORIGIN_Y_MM = 50.0

MOUNT_HOLE_INSET_X_MM = 7.45
MOUNT_HOLE_INSET_Y_MM = 3.0
MOUNT_HOLE_HP_THRESHOLD = 8

EDGE_CUT_LINE_WIDTH_MM = 0.05

FACEPLATE_FIELD_NAME = "Faceplate"
FACEPLATE_NAME_FIELD = "FaceplateName"
FACEPLATE_LIB_NAME = "Faceplate"
MOUNTING_HOLE_FOOTPRINT = "MountingHole_M3_Oval"

# Label rendered on F.SilkS above each panel hole when the source footprint
# carries a `FaceplateName` field. The anchor is `LABEL_OFFSET_MM` above the
# hole center, with the text bottom-aligned (so the text grows upward away
# from the hole). The offset is chosen to clear the largest panel hole
# (Ø8 LED bezel) with ~2 mm breathing room.
LABEL_OFFSET_MM = 6.0
LABEL_TEXT_HEIGHT_MM = 1.5
LABEL_TEXT_THICKNESS_MM = 0.25
