import json
import csv
import bpy
import os
import hashlib
import sys # Import the sys module

def calculate_sha256_hash(filepath):
    """
    Calculates the SHA256 hash of the file.

    Args:
        filepath (str): The path to the file.

    Returns:
        str: The SHA256 hash of the file, or None if the file does not exist or an error occurs.
    """
    if not os.path.exists(filepath):
        print(f"[WARN] File not found: {filepath}")
        return None

    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096)  # Read in 4KB chunks
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception as e:
        print(f"[ERROR] Error reading file: {filepath} - {e}")
        return None
    return hasher.hexdigest()

# Set the export directory
export_dir = bpy.path.abspath("//uv_map_extract")  # Create a folder named "uv_map_extract" in the blend file's directory

# Check if the directory exists, create it if it doesn't
if not os.path.exists(export_dir):
    try:
        os.makedirs(export_dir)
        print(f"📁 Created directory: {export_dir}")
    except OSError as e:
        print(f"❌ Error creating directory {export_dir}: {e}")
        # If directory creation fails, stop the script.  Important.
        print("Script stopped: Unable to create export directory.")
        raise Exception(f"Failed to create directory: {export_dir}")

# Set the export file paths
csv_export_path = os.path.join(export_dir, "uv_export.csv")
json_export_path = os.path.join(export_dir, "uv_export.json")
metadata_export_path = os.path.join(export_dir, "blend_metadata.json") # Path for metadata

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

# Gather and save metadata
blend_filepath = bpy.data.filepath
blend_filename = os.path.basename(blend_filepath)
blend_file_hash = calculate_sha256_hash(blend_filepath)

metadata = {
    "blend_filepath": blend_filepath,
    "blend_filename": blend_filename,
    "blend_file_hash": blend_file_hash,
    "blender_version": bpy.app.version_string,
    "python_version": sys.version, # Use sys.version
    "scene_name": bpy.context.scene.name,
    "object_count": len(bpy.context.scene.objects),
}

with open(metadata_export_path, 'w') as metadata_file:
    json.dump(metadata, metadata_file, indent=2)
print(f"\n✅ Metadata exported to JSON: {metadata_export_path}")

# Export Text Data
for text_block in bpy.data.texts:
    text_filename = os.path.join(export_dir, f"{text_block.name}.txt")
    try:
        with open(text_filename, 'w', encoding='utf-8') as text_file:
            text_file.write(text_block.as_string())
        print(f"✅ Text block '{text_block.name}' exported to: {text_filename}")
    except Exception as e:
        print(f"❌ Error exporting text block '{text_block.name}': {e}")

