import json
import csv
import bpy
import os

# Set the export file paths
csv_export_path = bpy.path.abspath("//uv_export.csv")
json_export_path = bpy.path.abspath("//uv_export.json")

# Prepare data storage
csv_lines = []
json_data = {}

# Choose objects
objects = bpy.context.scene.objects

for obj in objects:
    if obj.type != 'MESH':
        continue

    mesh = obj.data

    # Make sure we are in object mode to avoid stale data
    bpy.context.view_layer.objects.active = obj
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    uv_layer = mesh.uv_layers.active

    if uv_layer is None:
        print(f"[WARN] Object '{obj.name}' has NO UV map.")
        continue

    if len(mesh.loops) == 0:
        print(f"[WARN] Object '{obj.name}' has NO faces (no loops).")
        continue

    if len(uv_layer.data) == 0:
        print(f"[WARN] Object '{obj.name}' has UV map but NO UV data.")
        continue

    # Collect collection groupings
    collections = [col.name for col in obj.users_collection]

    # Collect UV data for each loop, with face and loop context
    for poly_index, poly in enumerate(mesh.polygons):
        for loop_index in poly.loop_indices:
            uv = uv_layer.data[loop_index].uv  # Get the UV for this loop
            # For CSV: Add mesh name, face index, loop index, UV coordinates, and collection groupings
            csv_lines.append([obj.name, f"Face_{poly_index}", f"Loop_{loop_index}", f"{uv[0]:.6f}", f"{uv[1]:.6f}", ', '.join(collections)])
            
            # For JSON: Store UV data with face, loop, and collection context
            loop_key = f"Face_{poly_index}_Loop_{loop_index}"
            if obj.name not in json_data:
                json_data[obj.name] = {}
            json_data[obj.name][loop_key] = {
                'uv': [uv[0], uv[1]],
                'collections': collections
            }

            print(f"[INFO] UVs exported for '{obj.name}', Face {poly_index}, Loop {loop_index} with UV ({uv[0]:.6f}, {uv[1]:.6f}), Collections: {', '.join(collections)}")

# Save to CSV
if csv_lines:
    with open(csv_export_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['MeshName', 'Face', 'Loop', 'U', 'V', 'Collections'])  # Write header
        writer.writerows(csv_lines)
    print(f"\n✅ UV data exported to CSV: {csv_export_path}")
else:
    print("\n⚠️ No UV data found to export to CSV.")

# Save data as JSON
if json_data:
    with open(json_export_path, 'w') as jsonfile:
        json.dump(json_data, jsonfile, indent=2)
    print(f"\n✅ UV data exported to JSON: {json_export_path}")

