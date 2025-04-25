import bpy
import json
import os

# Set the import file path (same as export)
import_path = bpy.path.abspath("//uv_export.json")

# Load JSON data
with open(import_path, 'r') as f:
    data = json.load(f)

for obj_name, uvs in data.items():
    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != 'MESH':
        continue

    mesh = obj.data

    if not mesh.uv_layers:
        mesh.uv_layers.new(name="ImportedUV")

    uv_layer = mesh.uv_layers.active

    if len(uv_layer.data) != len(uvs):
        print(f"UV count mismatch on {obj_name}, skipping.")
        continue

    for i, uv in enumerate(uvs):
        uv_layer.data[i].uv = uv

print("UV data imported.")
