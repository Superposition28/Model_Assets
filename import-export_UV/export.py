import bpy
import json
import os

# Set the export file path
export_path = bpy.path.abspath("//uv_export.json")

data = {}

for obj in bpy.context.selected_objects:
    if obj.type != 'MESH':
        continue

    mesh = obj.data
    uv_layer = mesh.uv_layers.active

    if uv_layer is None:
        continue

    uv_data = [loop.uv[:]
               for loop in uv_layer.data]

    data[obj.name] = uv_data

# Save to JSON
with open(export_path, 'w') as f:
    json.dump(data, f, indent=2)

print(f"UV data exported to {export_path}")
