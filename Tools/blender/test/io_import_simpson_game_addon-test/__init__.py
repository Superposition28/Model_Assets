"""Blender addon for importing The Simpsons Game 3D assets."""

bl_info = {
    "name": "The Simpsons Game 3d Asset Importer",
    "author": "Turk & Mister_Nebula & Samarixum",
    "version": (1, 0, 6), # Incremented version
    "blender": (4, 0, 0), # highest supportable version, 2.8 and above
    "location": "File > Import-Export",
    "description": "Import .rws.preinstanced, .dff.preinstanced mesh files from The Simpsons Game (PS3) and detect embedded strings.", # Updated description
    "warning": "",
    "category": "Import-Export",
}

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

from bpy.props import (
    StringProperty,
    CollectionProperty
)
from bpy_extras.io_utils import ImportHelper

from .utils import find_strings_by_signature_in_data
from .helpers import log_to_blender
from .model import sanitize_uvs, strip2face
from .importer import SimpGameImport



def utils_set_mode(mode: str) -> None:
    """Safely sets the object mode."""
    # log_to_blender(f"[SetMode] Setting mode to {mode}", to_blender_editor=False) # Console only - too chatty
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

class MyAddonPreferences(bpy.types.AddonPreferences):
    """Defines preferences for the addon."""
    bl_idname = __name__

    debugmode: bpy.props.BoolProperty(
        name="Debug Mode",
        description="Enable or disable debug mode",
        default=False
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "debugmode")

def menu_func_import(self: bpy.types.Menu, context: bpy.types.Context) -> None:
    """Adds the import option to the Blender file import menu."""
    # log_to_blender("[MenuFunc] Adding import option to menu", to_blender_editor=False) # Console only - too chatty
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

def register() -> None:
    """Registers the addon classes and menu functions."""
    log_to_blender("[Register] Registering import operator and menu function", to_blender_editor=False) # Console only
    bpy.utils.register_class(SimpGameImport)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister() -> None:
    """Unregisters the addon classes and menu functions."""
    log_to_blender("[Unregister] Unregistering import operator and menu function", to_blender_editor=False) # Console only
    try:
        bpy.utils.unregister_class(SimpGameImport)
    except RuntimeError as e:
        log_to_blender(f"[Unregister] Warning: {e}", to_blender_editor=True) # Log warning to editor
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception as e:
        log_to_blender(f"[Unregister] Warning: {e}", to_blender_editor=True) # Log warning to editor

# This allows the script to be run directly in Blender's text editor
if __name__ == "__main__":
    log_to_blender("[Main] Running as main script. Registering.", to_blender_editor=False) # Console only
    register()
