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
FACEPLATE_LIB_NAME = "Faceplate"
MOUNTING_HOLE_FOOTPRINT = "MountingHole_M3_Oval"
