bl_info = {
    "name": "The Simpsons Game Mesh Importer",
    "author": "Turk & Mister_Nebula",
    "version": (1, 0, 1),
    "blender": (4, 0, 0),
    "location": "File > Import-Export",
    "description": "Import .rws.preinstanced, .dff.preinstanced mesh files from The Simpsons Game (PS3)",
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

from bpy.props import (
    BoolProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty
)
from bpy_extras.io_utils import ImportHelper

def sanitize_uvs(uv_layer: bpy.types.MeshUVLoopLayer) -> None:
    print(f"[Sanitize] Checking UV layer: {uv_layer.name}")
    for i, uv in enumerate(uv_layer.data):
        if any([uv.uv.x != uv.uv.x, uv.uv.y != uv.uv.y]):  # NaN check
            print(f"[Sanitize] NaN UV at index {i} replaced with (0.0, 0.0)")
            uv.uv.x = 0.0
            uv.uv.y = 0.0

def normalize_uvs(uv_list):
    min_u = min(uv[0] for uv in uv_list)
    max_u = max(uv[0] for uv in uv_list)
    min_v = min(uv[1] for uv in uv_list)
    max_v = max(uv[1] for uv in uv_list)

    range_u = max_u - min_u
    range_v = max_v - min_v

    if range_u == 0: range_u = 1.0
    if range_v == 0: range_v = 1.0

    return [((u - min_u) / range_u, (v - min_v) / range_v) for u, v in uv_list]

def utils_set_mode(mode: str) -> None:
    print(f"[SetMode] Setting mode to {mode}")
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

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
        cur_file = open(self.filepath, "rb")
        print("== The Simpsons Game Import Log ==")

        cur_collection = bpy.data.collections.new("New Mesh")
        bpy.context.scene.collection.children.link(cur_collection)

        tmpRead = cur_file.read()
        mshBytes = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)
        mesh_iter = 0

        for x in mshBytes.finditer(tmpRead):
            cur_file.seek(x.end() + 4)
            FaceDataOff = int.from_bytes(cur_file.read(4), byteorder='little')
            MeshDataSize = int.from_bytes(cur_file.read(4), byteorder='little')
            MeshChunkStart = cur_file.tell()
            cur_file.seek(0x14, 1)
            mDataTableCount = int.from_bytes(cur_file.read(4), byteorder='big')
            mDataSubCount = int.from_bytes(cur_file.read(4), byteorder='big')

            for i in range(mDataTableCount):
                cur_file.seek(4, 1)
                cur_file.read(4)

            mDataSubStart = cur_file.tell()

            for i in range(mDataSubCount):
                cur_file.seek(mDataSubStart + i * 0xC + 8)
                offset = int.from_bytes(cur_file.read(4), byteorder='big')
                cur_file.seek(offset + MeshChunkStart + 0xC)
                VertCountDataOff = int.from_bytes(cur_file.read(4), byteorder='big') + MeshChunkStart
                cur_file.seek(VertCountDataOff)
                VertChunkTotalSize = int.from_bytes(cur_file.read(4), byteorder='big')
                VertChunkSize = int.from_bytes(cur_file.read(4), byteorder='big')
                VertCount = int(VertChunkTotalSize / VertChunkSize)
                cur_file.seek(8, 1)
                VertexStart = int.from_bytes(cur_file.read(4), byteorder='big') + FaceDataOff + MeshChunkStart
                cur_file.seek(0x14, 1)
                FaceCount = int(int.from_bytes(cur_file.read(4), byteorder='big') / 2)
                cur_file.seek(4, 1)
                FaceStart = int.from_bytes(cur_file.read(4), byteorder='big') + FaceDataOff + MeshChunkStart

                cur_file.seek(FaceStart)
                StripList = []
                tmpList = []
                for f in range(FaceCount):
                    Indice = int.from_bytes(cur_file.read(2), byteorder='big')
                    if Indice == 65535:
                        StripList.append(tmpList.copy())
                        tmpList.clear()
                    else:
                        tmpList.append(Indice)

                FaceTable = []
                for f in StripList:
                    for f2 in strip2face(f):
                        FaceTable.append(f2)

                VertTable = []
                UVTable = []
                CMTable = []
                for v in range(VertCount):
                    cur_file.seek(VertexStart + v * VertChunkSize)
                    TempVert = struct.unpack('>fff', cur_file.read(4 * 3))
                    VertTable.append(TempVert)

                    cur_file.seek(VertexStart + v * VertChunkSize + VertChunkSize - 16)
                    TempUV = struct.unpack('>ff', cur_file.read(4 * 2))
                    UVTable.append((TempUV[0], 1 - TempUV[1]))

                    cur_file.seek(VertexStart + v * VertChunkSize + VertChunkSize - 8)
                    TempCM = struct.unpack('>ff', cur_file.read(4 * 2))
                    CMTable.append((TempCM[0], 1 - TempCM[1]))

                mesh1 = bpy.data.meshes.new("Mesh")
                mesh1.use_auto_smooth = True
                obj = bpy.data.objects.new("Mesh_" + str(mesh_iter) + "_" + str(i), mesh1)
                cur_collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mesh = bpy.context.object.data
                bm = bmesh.new()

                for v in VertTable:
                    bm.verts.new((v[0], v[1], v[2]))
                bm.verts.ensure_lookup_table()

                for f in FaceTable:
                    try:
                        bm.faces.new((bm.verts[f[0]], bm.verts[f[1]], bm.verts[f[2]]))
                    except Exception as e:
                        print(f"[FaceError] Failed to create face {f}: {e}")
                        continue

                uv_layer = bm.loops.layers.uv.verify()
                cm_layer = bm.loops.layers.uv.new()
                uv_layer_name = uv_layer.name
                cm_layer_name = cm_layer.name

                for f in bm.faces:
                    f.smooth = True
                    for l in f.loops:
                        try:
                            l[uv_layer].uv = UVTable[l.vert.index]
                            l[cm_layer].uv = CMTable[l.vert.index]
                        except Exception as e:
                            print(f"[UVError] Failed to assign UV for vert {l.vert.index}: {e}")
                            continue

                UVTable = normalize_uvs(UVTable)

                bm.to_mesh(mesh)
                bm.free()

                utils_set_mode("EDIT")
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
                utils_set_mode("OBJECT")

                if uv_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[uv_layer_name])
                else:
                    print(f"[Sanitize] Warning: UV layer '{uv_layer_name}' not found.")

                if cm_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[cm_layer_name])
                else:
                    print(f"[Sanitize] Warning: CM layer '{cm_layer_name}' not found.")

                # --- Smart UV Project unwrap test ---
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                utils_set_mode('EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.03)
                utils_set_mode('OBJECT')

                obj.rotation_euler = (1.5707963705062866, 0, 0)

            mesh_iter += 1

        cur_file.close()
        print("== Import Complete ==")
        return {'FINISHED'}

def strip2face(strip: list) -> list:
    print(f"[Strip2Face] Converting strip of length {len(strip)} to faces")
    flipped = False
    tmpTable = []
    for x in range(len(strip)-2):
        if flipped:
            tmpTable.append((strip[x+2], strip[x+1], strip[x]))
        else:
            tmpTable.append((strip[x+1], strip[x+2], strip[x]))
        flipped = not flipped
    return tmpTable

def menu_func_import(self, context: bpy.types.Context) -> None:
    print("[MenuFunc] Adding import option to menu")
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

def register() -> None:
    print("[Register] Registering import operator and menu function")
    bpy.utils.register_class(SimpGameImport)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister() -> None:
    print("[Unregister] Unregistering import operator and menu function")
    bpy.utils.unregister_class(SimpGameImport)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    print("[Main] Running as main script")
    register()
