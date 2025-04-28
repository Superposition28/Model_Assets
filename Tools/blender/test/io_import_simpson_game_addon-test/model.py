
import bpy
import bmesh
import os
import struct
import re
import io
import math
import mathutils
import numpy as np
import string

from .helpers import log_to_blender


def sanitize_uvs(uv_layer: bpy.types.MeshUVLoopLayer) -> None:
    """Checks for and sanitizes non-finite UV coordinates in a UV layer."""
    # log_to_blender(f"[Sanitize] Checking UV layer: {uv_layer.name}", to_blender_editor=False) # Console only - too chatty

    # Check if uv_layer.data is accessible and has elements
    if not uv_layer.data:
        log_to_blender(f"[Sanitize] Warning: UV layer '{uv_layer.name}' has no data.", to_blender_editor=True, print_to_console=True, log_as_metadata=False, metadata_target="")
        return

    # Note: Sanitize is now mostly done during assignment in the main loop for performance,
    # but this could catch any remaining issues or be a fallback.
    sanitized_count = 0
    for uv_loop in uv_layer.data:
        # Check for NaN or infinity
        if not all(math.isfinite(c) for c in uv_loop.uv):
            # log_to_blender(f"[Sanitize] Non-finite UV replaced with (0.0, 0.0): {uv_loop.uv[:]}") # Too chatty for console
            uv_loop.uv.x = 0.0
            uv_loop.uv.y = 0.0
            sanitized_count += 1
    if sanitized_count > 0:
        log_to_blender(f"[Sanitize] Sanitized {sanitized_count} non-finite UV coordinates in layer '{uv_layer.name}'.", to_blender_editor=True, print_to_console=True, log_as_metadata=False, metadata_target="")


def strip2face(strip: list) -> list:
    """Converts a triangle strip into a list of triangle faces."""
    # log_to_blender(f"[Strip2Face] Converting strip of length {len(strip)} to faces", to_blender_editor=False) # Console only - too chatty
    flipped = False
    tmpTable = []
    # Need at least 3 indices to form a triangle strip
    if len(strip) < 3:
        # log_to_blender(f"[Strip2Face] Strip too short ({len(strip)}) to form faces. Skipping.", to_blender_editor=False) # Console only - too chatty
        return []

    for x in range(len(strip)-2):
        v1 = strip[x]
        v2 = strip[x+1]
        v3 = strip[x+2]
        # Check for degenerate triangles (indices are the same)
        if v1 == v2 or v1 == v3 or v2 == v3:
            # log_to_blender(f"[Strip2Face] Skipping degenerate face in strip at index {x} with indices ({v1}, {v2}, {v3})", to_blender_editor=False) # Console only - too chatty
            # Even if degenerate, the 'flipped' state still needs to toggle for the next potential face
            flipped = not flipped # Still flip for correct winding of subsequent faces
            continue # Skip this specific face

        if flipped:
            tmpTable.append((v3, v2, v1)) # Reversed winding for flipped faces
        else:
            tmpTable.append((v2, v3, v1)) # Standard winding
        flipped = not flipped # Toggle flipped state for the next iteration

    # log_to_blender(f"[Strip2Face] Generated {len(tmpTable)} faces from strip.", to_blender_editor=False) # Console only - too chatty
    return tmpTable

