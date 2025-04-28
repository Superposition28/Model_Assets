
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

# --- Configuration for String Detection ---
# Fixed Signatures to check (often indicate block headers)
# You need to determine the correct signature bytes (as bytes)
# and the relative offset (in bytes) from the SIGNATURE START to the STRING START.
# Use your previous script's output and a hex editor to find these.
FIXED_SIGNATURES_TO_CHECK = [
    {'signature': bytes.fromhex('0211010002000000'), 'relative_string_offset': 16, 'description': 'String Block Header (General, 8 bytes)'},
    {'signature': bytes.fromhex('0211010002000000140000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype A, 16 bytes)'},
    {'signature': bytes.fromhex('0211010002000000180000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype B, 16 bytes) - Hypothesized'},
    {'signature': bytes.fromhex('905920010000803f0000803f0000803f'), 'relative_string_offset': 16, 'description': 'Another Block Type Header (16 bytes, Common Float Pattern)'} # Corrected based on common 803f pattern, PLACEHOLDER: Verify exact bytes and offset
]

# Analysis Settings for String Detection
MAX_POTENTIAL_STRING_LENGTH = 64
MIN_EXTRACTED_STRING_LENGTH = 4
CONTEXT_SIZE = 16 # Bytes around the SIGNATURE / START marker to show (still useful in the return data, just not logged to editor)
STRING_CONTEXT_SIZE = 5 # Bytes around the STRING to show (still useful in the return data, just not logged to editor)


class SimpGameImport(bpy.types.Operator, ImportHelper):
    bl_idname = "custom_import_scene.simpgame"
    bl_label = "Import"
    bl_options = {'PRESET', 'UNDO'}
    filter_glob: StringProperty(
        default="*.preinstanced",
        options={'HIDDEN'},
    )
    filepath: StringProperty(subtype='FILE_PATH',)
    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def draw(self, context: bpy.types.Context) -> None:
        pass

    def execute(self, context: bpy.types.Context) -> set:
        log_block_name = "SimpGame_Importer_Log" # Define the log block name
        log_to_blender("== The Simpsons Game Import Log ==", block_name=log_block_name, to_blender_editor=True) # Log header to editor
        log_to_blender(f"[File] Importing file: {self.filepath}", block_name=log_block_name, to_blender_editor=True) # Log file path to editor
        log_to_blender(f"[File] File size: {os.path.getsize(self.filepath)} bytes", block_name=log_block_name, to_blender_editor=False) # Console only
        log_to_blender(f"[File] File name: {os.path.basename(self.filepath)}", block_name=log_block_name, to_blender_editor=False) # Console only
        log_to_blender(f"[File] Output file: {os.path.splitext(os.path.basename(self.filepath))[0]}.blend", block_name=log_block_name, to_blender_editor=False) # Console only

        try:
            with open(self.filepath, "rb") as cur_file:
                tmpRead = cur_file.read()
        except FileNotFoundError:
            log_to_blender(f"[Error] File not found: {self.filepath}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
            return {'CANCELLED'}
        except Exception as e:
            log_to_blender(f"[Error] Failed to read file {self.filepath}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
            return {'CANCELLED'}


        # --- Perform String Detection ---
        log_to_blender("\n--- Found Embedded Strings ---", block_name=log_block_name, to_blender_editor=True) # Log header to editor
        string_results = find_strings_by_signature_in_data(
            tmpRead,
            FIXED_SIGNATURES_TO_CHECK,
            MAX_POTENTIAL_STRING_LENGTH,
            MIN_EXTRACTED_STRING_LENGTH,
            CONTEXT_SIZE,
            STRING_CONTEXT_SIZE
        )

        found_string_count = 0
        for item in string_results:
            if item['type'] == 'fixed_signature_string' and item['string_found']:
                found_string_count += 1
                # Simplified logging: File path, string offset, and the string itself
                log_to_blender(f"{os.path.basename(self.filepath)} +{item['string_offset']:08X}: {item['string']}", block_name=log_block_name, to_blender_editor=True)

        if found_string_count == 0:
            log_to_blender("[String Found] No valid strings found for configured signatures.", block_name=log_block_name, to_blender_editor=True)
        else:
            log_to_blender(f"[String Found] Total {found_string_count} valid strings found.", block_name=log_block_name, to_blender_editor=True)


        log_to_blender("\n--- Mesh Import Process ---", block_name=log_block_name, to_blender_editor=True) # Log header to editor


        # --- Start Mesh Import (Existing Logic) ---
        cur_collection = bpy.data.collections.new("New Mesh")
        bpy.context.scene.collection.children.link(cur_collection)

        # Using re.compile on the full data bytes is fine for finding chunk starts
        mshBytes = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)
        mesh_iter = 0

        # Use io.BytesIO to treat the byte data like a file for seeking/reading
        data_io = io.BytesIO(tmpRead)

        for x in mshBytes.finditer(tmpRead):
            data_io.seek(x.end() + 4) # Use data_io for seeking/reading within the matched chunk
            try: # Added error handling for reading initial chunk data
                FaceDataOff = int.from_bytes(data_io.read(4), byteorder='little')
                MeshDataSize = int.from_bytes(data_io.read(4), byteorder='little')
                MeshChunkStart = data_io.tell() # Use data_io.tell()
                data_io.seek(0x14, 1) # Use data_io.seek()
                mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
                mDataSubCount = int.from_bytes(data_io.read(4), byteorder='big')
                log_to_blender(f"[Mesh {mesh_iter}] Found chunk at {x.start():08X}. FaceDataOff: {FaceDataOff}, MeshDataSize: {MeshDataSize}, mDataTableCount: {mDataTableCount}, mDataSubCount: {mDataSubCount}", block_name=log_block_name, to_blender_editor=False) # Log chunk info to console

            except Exception as e:
                log_to_blender(f"[Error] Failed to read mesh chunk header data at {x.start():08X}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                continue # Skip this chunk and try to find the next one

            for i in range(mDataTableCount):
                data_io.seek(4, 1) # Use data_io
                data_io.read(4) # Reading and discarding 4 bytes using data_io

            mDataSubStart = data_io.tell() # Use data_io.tell()

            for i in range(mDataSubCount):
                try: # Added error handling for reading sub-mesh data
                    data_io.seek(mDataSubStart + i * 0xC + 8) # Use data_io
                    offset = int.from_bytes(data_io.read(4), byteorder='big') # Use data_io
                    data_io.seek(offset + MeshChunkStart + 0xC) # Use data_io
                    VertCountDataOff = int.from_bytes(data_io.read(4), byteorder='big') + MeshChunkStart # Use data_io
                    data_io.seek(VertCountDataOff) # Use data_io
                    VertChunkTotalSize = int.from_bytes(data_io.read(4), byteorder='big') # Use data_io
                    VertChunkSize = int.from_bytes(data_io.read(4), byteorder='big') # Use data_io
                    if VertChunkSize <= 0:
                        log_to_blender(f"[Mesh {mesh_iter}_{i}] Warning: VertChunkSize is non-positive ({VertChunkSize}). Skipping mesh part.", block_name=log_block_name, to_blender_editor=True)
                        continue
                    VertCount = int(VertChunkTotalSize / VertChunkSize)
                    data_io.seek(8, 1) # Skipping 8 bytes (possibly normals offset and size) using data_io
                    VertexStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart # Use data_io
                    data_io.seek(0x14, 1) # Skipping 0x14 bytes using data_io
                    # Ensure enough bytes are available before reading FaceCount
                    face_count_bytes_offset = data_io.tell()
                    if face_count_bytes_offset + 4 > len(tmpRead):
                        log_to_blender(f"[Mesh {mesh_iter}_{i}] Error: Insufficient data to read FaceCount at offset {face_count_bytes_offset:08X}. Skipping mesh part.", block_name=log_block_name, to_blender_editor=True)
                        continue
                    FaceCount = int(int.from_bytes(data_io.read(4), byteorder='big') / 2) # FaceCount seems to be num_indices / 2, use data_io
                    data_io.seek(4, 1) # Skipping 4 bytes (possibly material index offset) using data_io
                    FaceStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart # Use data_io

                    log_to_blender(f"[MeshPart {mesh_iter}_{i}] Reading data. VertCount: {VertCount}, FaceCount: {FaceCount}, VertexStart: {VertexStart:08X}, FaceStart: {FaceStart:08X}", block_name=log_block_name, to_blender_editor=False) # Console only

                except Exception as e:
                    log_to_blender(f"[Error] Failed to read sub-mesh header data for part {mesh_iter}_{i}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                    continue # Continue to the next sub-mesh if data reading fails

                # Read Face Indices
                data_io.seek(FaceStart) # Use data_io
                StripList = []
                tmpList = []
                try: # Added error handling for reading face indices
                    # Check if FaceStart is within bounds to prevent excessive reading attempts
                    if FaceStart < 0 or FaceStart >= len(tmpRead):
                        log_to_blender(f"[MeshPart {mesh_iter}_{i}] Error: FaceStart offset {FaceStart:08X} is out of bounds. Skipping face data read.", block_name=log_block_name, to_blender_editor=True)
                        FaceCount = 0 # Effectively skip face processing
                    else:
                        data_io.seek(FaceStart) # Reset seek in case bounds check changed it
                        # Ensure enough data is available for FaceCount indices (each 2 bytes)
                        if FaceStart + FaceCount * 2 > len(tmpRead):
                             log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Predicted face data size ({FaceCount * 2} bytes) exceeds file bounds from FaceStart {FaceStart:08X}. Reading available data.", block_name=log_block_name, to_blender_editor=True)
                            # Adjust FaceCount based on available data
                             FaceCount = (len(tmpRead) - FaceStart) // 2
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Adjusted FaceCount to {FaceCount} based on available data.", block_name=log_block_name, to_blender_editor=True)


                    for f in range(FaceCount):
                        # Ensure enough data is available for the next index
                        if data_io.tell() + 2 > len(tmpRead):
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading face index {f}. Stopping face index read.", block_name=log_block_name, to_blender_editor=True)
                            break # Stop reading indices if not enough data
                        Indice = int.from_bytes(data_io.read(2), byteorder='big') # Use data_io
                        if Indice == 65535:
                            if tmpList: # Only append if tmpList is not empty
                                StripList.append(tmpList.copy())
                            tmpList.clear()
                        else:
                            tmpList.append(Indice)
                    if tmpList: # Append the last strip if it doesn't end with 65535
                        StripList.append(tmpList.copy())
                except Exception as e:
                    log_to_blender(f"[Error] Failed to read face indices for mesh part {mesh_iter}_{i}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                    # Decide whether to continue processing this mesh part without faces or skip
                    continue # Skipping this mesh part if face indices can't be read

                FaceTable = []
                for f in StripList:
                    FaceTable.extend(strip2face(f)) # Use extend to add faces from strip2face

                VertTable = []
                UVTable = []
                CMTable = []
                try: # Added error handling for reading vertex data
                    # Check if VertexStart is within bounds
                    if VertexStart < 0 or VertexStart >= len(tmpRead):
                        log_to_blender(f"[MeshPart {mesh_iter}_{i}] Error: VertexStart offset {VertexStart:08X} is out of bounds. Skipping vertex data read.", block_name=log_block_name, to_blender_editor=True)
                        VertCount = 0 # Effectively skip vertex processing

                    for v in range(VertCount):
                        vert_data_start = VertexStart + v * VertChunkSize
                        # Check if there's enough data for this vertex chunk
                        if vert_data_start + VertChunkSize > len(tmpRead):
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading vertex {v}. Stopping vertex read.", block_name=log_block_name, to_blender_editor=True)
                            # Adjust VertCount for subsequent loops if necessary, although breaking works for current loop
                            break

                        data_io.seek(vert_data_start) # Use data_io

                        # Ensure enough data for vertex coords
                        if data_io.tell() + 12 > len(tmpRead): # 4 bytes/float * 3 floats = 12 bytes
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for vertex coords at {data_io.tell():08X} for vertex {v}. Skipping.", block_name=log_block_name, to_blender_editor=True)
                            continue # Skip this vertex

                        TempVert = struct.unpack('>fff', data_io.read(4 * 3)) # Use data_io
                        VertTable.append(TempVert)

                        # Ensure enough data for UVs
                        uv_offset = vert_data_start + VertChunkSize - 16
                        if uv_offset < 0 or uv_offset + 8 > len(tmpRead): # 4 bytes/float * 2 floats = 8 bytes
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for UV coords at {uv_offset:08X} for vertex {v}. Skipping UV.", block_name=log_block_name, to_blender_editor=True)
                            TempUV = (0.0, 0.0) # Assign default UVs
                        else:
                            data_io.seek(uv_offset) # Use data_io
                            TempUV = struct.unpack('>ff', data_io.read(4 * 2)) # Use data_io
                        UVTable.append((TempUV[0], 1 - TempUV[1])) # Keep original UVs, apply V inversion

                        # Ensure enough data for CMs
                        cm_offset = vert_data_start + VertChunkSize - 8
                        if cm_offset < 0 or cm_offset + 8 > len(tmpRead): # 4 bytes/float * 2 floats = 8 bytes
                            log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for CM coords at {cm_offset:08X} for vertex {v}. Skipping CM.", block_name=log_block_name, to_blender_editor=True)
                            TempCM = (0.0, 0.0) # Assign default CMs
                        else:
                            data_io.seek(cm_offset) # Use data_io
                            TempCM = struct.unpack('>ff', data_io.read(4 * 2)) # Use data_io
                        CMTable.append((TempCM[0], 1 - TempCM[1])) # Keep original CMs, apply V inversion


                    log_to_blender(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs.", block_name=log_block_name, to_blender_editor=False) # Console only

                except Exception as e:
                    log_to_blender(f"[Error] Failed to read vertex data for mesh part {mesh_iter}_{i}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                    continue # Skipping this mesh part if vertex data can't be read

                # Check if we have data to create a mesh
                if not VertTable or not FaceTable:
                    log_to_blender(f"[MeshPart {mesh_iter}_{i}] Warning: No valid vertices or faces read for mesh part. Skipping mesh creation.", block_name=log_block_name, to_blender_editor=True)
                    continue # Skip creating mesh if no data

                mesh1 = bpy.data.meshes.new(f"Mesh_{mesh_iter}_{i}") # Name mesh data block
                mesh1.use_auto_smooth = True
                obj = bpy.data.objects.new(f"Mesh_{mesh_iter}_{i}", mesh1) # Name object
                cur_collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mesh = bpy.context.object.data
                bm = bmesh.new()

                # Add vertices to BMesh
                for v_co in VertTable:
                    bm.verts.new(v_co)
                bm.verts.ensure_lookup_table()
                log_to_blender(f"[MeshPart {mesh_iter}_{i}] Added {len(bm.verts)} vertices to BMesh.", block_name=log_block_name, to_blender_editor=False)

                # Create faces in BMesh
                faces_created_count = 0
                for f_indices in FaceTable:
                    try:
                        # Ensure indices are within the valid range
                        valid_face = True
                        face_verts = []
                        for idx in f_indices:
                            if idx < 0 or idx >= len(bm.verts):
                                log_to_blender(f"[FaceError] Invalid vertex index {idx} in face {f_indices}. Skipping face.", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                                valid_face = False
                                break
                            face_verts.append(bm.verts[idx])

                        if valid_face:
                            try:
                                # Only add if it doesn't cause errors (e.g., non-planar, duplicate edge)
                                bm.faces.new(face_verts)
                                faces_created_count += 1
                            except ValueError as e:
                                # Catch cases where face creation fails (e.g., non-manifold, duplicate)
                                log_to_blender(f"[FaceWarning] Failed to create face {f_indices} ({len(face_verts)} verts): {e}. Skipping.", block_name=log_block_name, to_blender_editor=True)
                            except Exception as e:
                                log_to_blender(f"[FaceError] Unexpected error creating face {f_indices}: {e}. Skipping.", block_name=log_block_name, to_blender_editor=True)


                    except Exception as e:
                        log_to_blender(f"[FaceError] Unhandled error processing face indices {f_indices}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                        continue

                log_to_blender(f"[MeshPart {mesh_iter}_{i}] Attempted to create {len(FaceTable)} faces, successfully created {faces_created_count}.", block_name=log_block_name, to_blender_editor=False)

                # Validate bmesh before accessing layers and assigning UVs
                if not bm.faces:
                    log_to_blender(f"[BMeshWarning] No faces created for mesh {mesh_iter}_{i}. Skipping UV assignment and further processing for this mesh part.", block_name=log_block_name, to_blender_editor=True) # Log warning to editor
                    bm.free()
                    # Ensure object and mesh data are cleaned up if no faces were created
                    if mesh1: # Check if mesh data was created
                        if mesh1.users == 1: # Check if only this object uses it
                            bpy.data.meshes.remove(mesh1)
                            # log_to_blender(f"[BMeshWarning] Removed unused mesh data block '{mesh1.name}'.", block_name=log_block_name, to_blender_editor=True) # Too chatty
                    if obj: # Check if object was created
                        if obj.users == 1: # Check if only the collection links it
                            # Remove from collection and delete
                            for col in bpy.data.collections:
                                if obj.name in col.objects:
                                    col.objects.unlink(obj)
                            bpy.data.objects.remove(obj)
                            # log_to_blender(f"[BMeshWarning] Removed unused object '{obj.name}'.", block_name=log_block_name, to_blender_editor=True) # Too chatty

                    continue # Skip to the next mesh part

                # Ensure UV layers exist before accessing them
                # Check if the layers already exist first to avoid errors if run multiple times
                uv_layer = bm.loops.layers.uv.get("uvmap") # Get default UV layer or None
                if uv_layer is None:
                    uv_layer = bm.loops.layers.uv.new("uvmap") # Create if it doesn't exist
                    log_to_blender("[Info] Created new 'uvmap' layer.", block_name=log_block_name, to_blender_editor=False) # Console only
                else:
                    # Clear existing data if layer already existed? Not strictly needed for new bmesh.
                    pass

                cm_layer = bm.loops.layers.uv.get("CM_uv") # Get CM UV layer or None
                if cm_layer is None:
                    cm_layer = bm.loops.layers.uv.new("CM_uv") # Create if it doesn't exist
                    log_to_blender("[Info] Created new 'CM_uv' layer.", block_name=log_block_name, to_blender_editor=False) # Console only
                else:
                    # Clear existing data if layer already existed?
                    pass


                uv_layer_name = uv_layer.name
                cm_layer_name = cm_layer.name


                # Assign UVs to loops and perform basic sanitization during assignment
                # This is done per loop, so it handles shared vertices correctly
                uv_assigned_count = 0
                cm_assigned_count = 0
                for f in bm.faces:
                    f.smooth = True # Set face to smooth shading
                    for l in f.loops:
                        vert_index = l.vert.index
                        if vert_index >= len(UVTable) or vert_index >= len(CMTable):
                            log_to_blender(f"[UVError] Vertex index {vert_index} out of range for UV/CM tables ({len(UVTable)}/{len(CMTable)}) during assignment for mesh part {mesh_iter}_{i}. Skipping UV assignment for this loop.", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                            # Assign default (0,0) UVs to avoid errors with missing data
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue

                        try:
                            # Assign main UVs
                            uv_coords = UVTable[vert_index]
                            # Sanitize main UVs during assignment
                            if all(math.isfinite(c) for c in uv_coords):
                                l[uv_layer].uv = uv_coords
                                uv_assigned_count += 1
                            else:
                                # log_to_blender(f"[Sanitize] Non-finite main UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", block_name=log_block_name, to_blender_editor=False) # Too chatty
                                l[uv_layer].uv = (0.0, 0.0)
                                uv_assigned_count += 1 # Count even if sanitized to default

                            # Assign CM UVs
                            cm_coords = CMTable[vert_index]
                            # Sanitize CM UVs during assignment
                            if all(math.isfinite(c) for c in cm_coords):
                                l[cm_layer].uv = cm_coords
                                cm_assigned_count += 1
                            else:
                                # log_to_blender(f"[Sanitize] Non-finite CM UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", block_name=log_block_name, to_blender_editor=False) # Too chatty
                                l[cm_layer].uv = (0.0, 0.0)
                                cm_assigned_count += 1 # Count even if sanitized to default

                        except Exception as e:
                            log_to_blender(f"[UVError] Failed to assign UV/CM for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}: {e}", block_name=log_block_name, to_blender_editor=True) # Log error to editor
                            # Assign default (0,0) UVs to prevent potential issues even on error
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue # Continue to the next loop


                log_to_blender(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops.", block_name=log_block_name, to_blender_editor=False) # Console only


                # Finish BMesh and assign to mesh data
                bm.to_mesh(mesh)
                bm.free() # Free the bmesh as it's no longer needed
                log_to_blender(f"[MeshPart {mesh_iter}_{i}] BMesh converted to mesh data.", block_name=log_block_name, to_blender_editor=False)


                # Perform a final sanitize check on the created UV layers in mesh data
                # Note: The assignment loop already sanitizes, so this is a fallback/verification
                if uv_layer_name in mesh.uv_layers:
                    # Don't pass to_blender_editor=True here, sanitize_uvs logs its own findings to editor
                    sanitize_uvs(mesh.uv_layers[uv_layer_name])
                else:
                    log_to_blender(f"[Sanitize] Warning: Main UV layer '{uv_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.", block_name=log_block_name, to_blender_editor=True) # Log warning to editor

                if cm_layer_name in mesh.uv_layers:
                    # Don't pass to_blender_editor=True here
                    sanitize_uvs(mesh.uv_layers[cm_layer_name])
                else:
                    log_to_blender(f"[Sanitize] Warning: CM UV layer '{cm_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.", block_name=log_block_name, to_blender_editor=True) # Log warning to editor


                # Apply rotation
                obj.rotation_euler = (1.5707963705062866, 0, 0) # Rotate 90 degrees around X (pi/2)
                log_to_blender(f"[MeshPart {mesh_iter}_{i}] Object created '{obj.name}' and rotated.", block_name=log_block_name, to_blender_editor=False) # Console only

            mesh_iter += 1

        # data_io is automatically closed when the function exits or garbage collected
        # cur_file is also implicitly closed by the 'with open' block

        log_to_blender("== Import Complete ==", block_name=log_block_name, to_blender_editor=True) # Log completion to editor
        return {'FINISHED'}


