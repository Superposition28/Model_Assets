import json
import os
import hashlib
import bpy
import sys
import io
import csv

def calculate_sha256_hash_from_image(image):
    """
    Calculates the SHA256 hash of an image stored inside the Blender file.

    Args:
        image (bpy.types.Image): The Blender image object.

    Returns:
        str: The SHA256 hash of the image, or None if an error occurs.
    """
    if image is None:
        return None

    # Check if the image is packed in the blend file
    if image.packed_file:  # Correct check for packed image
        try:
            # Save the image to a temporary buffer to calculate the hash
            with io.BytesIO() as buffer:
                image.save_render(buffer, scene=bpy.context.scene)
                buffer.seek(0)  # Go to the beginning of the buffer
                image_data = buffer.read()  # Read the image data from the buffer
                return hashlib.sha256(image_data).hexdigest()
        except Exception as e:
            print(f"[ERROR] Failed to calculate hash for packed image: {e}")
            return None
    else:
        print(f"[WARN] Image '{image.name}' is not packed, skipping hash calculation.")
        return None


def calculate_sha256_hash(filepath):
    """
    Calculates the SHA256 hash of a file on disk.

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
export_dir = bpy.path.abspath("//texture_map_extract")  # Create a folder named "texture_map_extract" in the blend file's directory

# Check if the directory exists, create it if it doesn't
if not os.path.exists(export_dir):
    try:
        os.makedirs(export_dir)
        print(f"📁 Created directory: {export_dir}")
    except OSError as e:
        print(f"❌ Error creating directory {export_dir}: {e}")
        # If directory creation fails, stop the script. Important.
        print("Script stopped: Unable to create export directory.")
        raise Exception(f"Failed to create directory: {export_dir}")

# Set the export file paths
csv_export_path = os.path.join(export_dir, "texture_export.csv")
json_export_path = os.path.join(export_dir, "texture_export.json")
metadata_export_path = os.path.join(export_dir, "blend_metadata.json")  # Path for metadata

# Prepare data storage
csv_lines = []
json_data = {}
unused_materials = []
unused_textures = []

# Choose objects
objects = bpy.context.scene.objects

# Track used materials and textures
used_materials = set()
used_textures = set()

for obj in objects:
    if obj.type != 'MESH':
        continue

    mesh = obj.data

    # Make sure we are in object mode to avoid stale data
    bpy.context.view_layer.objects.active = obj
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Collect collection groupings
    collections = [col.name for col in obj.users_collection]

    # Loop through materials and textures
    for mat in obj.data.materials:
        if mat is None:
            continue

        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                # Get texture image
                texture_image = node.image
                if texture_image:
                    texture_filename = texture_image.name
                    texture_file = texture_image.filepath
                    texture_file_hash = None
                    blender_dir = bpy.path.abspath("//")  # Blender directory
                    print(f"\nblender_dir:                     {blender_dir}")

                    blender_dir = blender_dir.rstrip(os.sep)  # Remove the trailing separator
                    print(f"blender_dir:                     {blender_dir}")

                    # Check if the texture path starts with "//", and handle accordingly
                    if texture_file.startswith("//"):
                        texture_file = texture_file[2:]  # Remove the leading "//"
                        print(f"texture_file:                     {texture_file}")
                
                    texture_filepath = os.path.join(blender_dir, texture_file)
                    print(f"texture_filepath:                {texture_filepath}\n")

                    texture_file_hash_internal = calculate_sha256_hash_from_image(texture_image)
                    print(f"texture_file_hash_internal:       {texture_file_hash_internal}")
                    texture_file_hash = calculate_sha256_hash(texture_filepath)
                    print(f"texture_file_hash:               {texture_file_hash}")

                    # For CSV: Add mesh name, material name, texture filename, and texture file path
                    csv_lines.append([obj.name, mat.name, texture_filename, texture_filepath, texture_file_hash, texture_file_hash_internal, ', '.join(collections)])

                    # For JSON: Store texture data with material and collection context
                    if obj.name not in json_data:
                        json_data[obj.name] = {}

                    if mat.name not in json_data[obj.name]:
                        json_data[obj.name][mat.name] = []

                    json_data[obj.name][mat.name].append({
                        "texture_filename": texture_filename,
                        "texture_filepath": texture_filepath,
                        "texture_file_hash": texture_file_hash,
                        "texture_file_hash_internal": texture_file_hash_internal,
                        "collections": collections
                    })

                    # Add to used materials and textures
                    used_materials.add(mat.name)
                    used_textures.add(texture_filename)

                    print(f"[INFO] Texture '{texture_filename}' exported for '{obj.name}' with material '{mat.name}', Filepath: {texture_filepath}, Hash: {texture_file_hash}, Collections: {', '.join(collections)}")

# Loop through all materials in the scene and check if they're used
for mat in bpy.data.materials:
    if mat.name not in used_materials:
        unused_materials.append(mat.name)

# Loop through all images in the scene and check if they're used
for image in bpy.data.images:
    if image.name not in used_textures:
        unused_textures.append(image.name)

# Save CSV with mesh, material, texture info
with open(csv_export_path, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Mesh Name', 'Material Name', 'Texture Filename', 'Texture Filepath', 'Texture File Hash', 'Texture File Hash Internal', 'Collections'])
    writer.writerows(csv_lines)
    print(f"✅ Texture export data exported to CSV: {csv_export_path}")

# Save data as JSON
if json_data:
    with open(json_export_path, 'w') as jsonfile:
        json.dump(json_data, jsonfile, indent=2)
    print(f"\n✅ Texture data exported to JSON: {json_export_path}")

# Save unused materials and textures data to JSON
unused_data = {
    "unused_materials": unused_materials,
    "unused_textures": unused_textures
}

with open(json_export_path, 'a') as jsonfile:
    json.dump(unused_data, jsonfile, indent=2)
    print(f"\n✅ Unused materials and textures data exported to JSON: {json_export_path}")

# Collect collection names and associated mesh names
collections_data = {}
for collection in bpy.data.collections:
    collection_meshes = [obj.name for obj in collection.objects if obj.type == 'MESH']
    if collection_meshes:
        collections_data[collection.name] = collection_meshes


# Save metadata (same as before)
blend_filepath = bpy.data.filepath
blend_filename = os.path.basename(blend_filepath)
blend_file_hash = calculate_sha256_hash(blend_filepath)

metadata = {
    "blend_filepath": blend_filepath,
    "blend_filename": blend_filename,
    "blend_file_hash": blend_file_hash,
    "blender_version": bpy.app.version_string,
    "python_version": sys.version,  # Use sys.version
    "scene_name": bpy.context.scene.name,
    "object_count": len(bpy.context.scene.objects),
    "collections": collections_data
}

with open(metadata_export_path, 'w') as metadata_file:
    json.dump(metadata, metadata_file, indent=2)
print(f"\n✅ Metadata exported to JSON: {metadata_export_path}")
