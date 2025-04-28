
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


# --- Logging Function ---
def log_to_blender(
    text: str,
    block_name: str = "SimpGame_Importer_Log",
    to_blender_editor: bool = False,
    print_to_console: bool = True,   # Flag to print log to the console
    require_debug_mode: bool = True, # Flag to require debug mode
    log_as_metadata: bool = False,   # Flag to store the log as metadata
    metadata_target: str = "scene"   # Specify whether to store metadata in 'scene', 'collection', or 'object'
) -> None:
    """Appends a message to a text block in Blender's text editor if requested,
    and optionally prints to console. Optionally stores log as metadata."""

    # Get the debug mode value from the addon preferences
    debug_mode = bpy.context.preferences.addons[__name__].preferences.debugmode

    if require_debug_mode and debug_mode:
        # Print to the console for immediate feedback, based on the flag
        if print_to_console:
            print(text)

        # Store log as metadata if the flag is set to True
        if log_as_metadata:
            if metadata_target == "scene":
                bpy.context.scene["log_metadata"] = text
            elif metadata_target == "collection":
                collection = bpy.context.view_layer.active_layer_collection.collection
                collection["log_metadata"] = text
            elif metadata_target == "object" and bpy.context.active_object:
                bpy.context.active_object["log_metadata"] = text
            else:
                print(f"Invalid metadata target: {metadata_target}. Log not stored as metadata.")

        # Only try to write to Blender's text editor if requested and bpy.data has 'texts'
        if to_blender_editor and hasattr(bpy.data, "texts"):
            if block_name not in bpy.data.texts:
                text_block = bpy.data.texts.new(block_name)
                log_to_blender(f"[Log] Created new text block: '{block_name}'", to_blender_editor=False, print_to_console=False)  # Log creation to console
            else:
                text_block = bpy.data.texts[block_name]
            text_block.write(text + "\n")
    #else:
        # If not in debug mode, print a message indicating that debug mode is disabled
        # print(f"[Log] Logging is disabled. Set debug_mode to True to enable logging.")


# example:
# log_to_blender("msg", to_blender_editor=True, print_to_console=True, log_as_metadata=False, metadata_target="")

# --- End Logging Function ---