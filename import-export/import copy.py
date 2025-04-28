import json
import csv
import bpy
import os

# Set the import file paths (adjust as needed)
csv_import_path = bpy.path.abspath("//uv_export.csv")
#json_import_path = bpy.path.abspath("//uv_export.json")

# Check if CSV file exists
if not os.path.exists(csv_import_path):
    print(f"⚠️ CSV file not found: {csv_import_path}")
else:
    print(f"✅ CSV file found: {csv_import_path}")

# Check if JSON file exists
#if not os.path.exists(json_import_path):
#    print(f"⚠️ JSON file not found: {json_import_path}")
#else:
#    print(f"✅ JSON file found: {json_import_path}")

# Read the CSV data
csv_data = {}
if os.path.exists(csv_import_path):
    with open(csv_import_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            mesh_name = row['MeshName']
            face = row['Face']
            loop = row['Loop']
            u = float(row['U'])
            v = float(row['V'])
            collections = row['Collections'].split(', ') if row['Collections'] else []

            if mesh_name not in csv_data:
                csv_data[mesh_name] = []

            csv_data[mesh_name].append({
                'face': face,
                'loop': loop,
                'uv': (u, v),
                'collections': collections
            })
        print(f"✅ CSV data loaded: {len(csv_data)} meshes found.")

# Read the JSON data
#json_data = {}
#if os.path.exists(json_import_path):
#    with open(json_import_path, 'r') as jsonfile:
#        json_data = json.load(jsonfile)
#    print(f"✅ JSON data loaded: {len(json_data)} meshes found.")

# Function to import UV and collection data
def import_uv_and_collections(mesh_name: str, mesh_data: dict):
    # Check if the object exists
    obj = bpy.context.scene.objects.get(mesh_name)
    if obj is None:
        print(f"⚠️ Mesh '{mesh_name}' not found.")
        return

    # Make sure in OBJECT mode
    bpy.context.view_layer.objects.active = obj
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Access UV layer
    uv_layer = obj.data.uv_layers.active
    if uv_layer is None:
        print(f"⚠️ Mesh '{mesh_name}' has no UV map.")
        return

    # 🔥 Differentiate: JSON (dict) vs CSV (list)
    if isinstance(mesh_data, dict):
        # JSON case
        uv_entries = []
        for loop_key, loop_data in mesh_data.items():
            face_index = int(loop_key.split('_')[1])
            loop_index = int(loop_key.split('_')[3])
            uv = loop_data['uv']
            collections = loop_data.get('collections', [])
            uv_entries.append({'face': f"Face_{face_index}", 'loop': f"Loop_{loop_index}", 'uv': uv, 'collections': collections})
    else:
        # CSV case
        uv_entries = mesh_data

    # Now common code:
    for uv_entry in uv_entries:
        face_index = int(uv_entry['face'].split('_')[1])
        loop_index = int(uv_entry['loop'].split('_')[1])
        uv = uv_entry['uv']

        uv_layer.data[loop_index].uv = uv
        print(f"✅ UV applied for {mesh_name}, Face {face_index}, Loop {loop_index} with UV ({uv[0]}, {uv[1]})")

    # Optional: assign collections
    if uv_entries:
        collections = uv_entries[0].get('collections', [])
        for collection_name in collections:
            if collection_name not in [col.name for col in obj.users_collection]:
                collection = bpy.data.collections.get(collection_name)
                if collection:
                    collection.objects.link(obj)
                    print(f"✅ Mesh '{mesh_name}' added to collection '{collection_name}'.")


# Import UV data from CSV or JSON
for mesh_name, mesh_data in csv_data.items():
    import_uv_and_collections(mesh_name, mesh_data)

# Import UV data from JSON (if available)
#for mesh_name, mesh_data in json_data.items():
#    import_uv_and_collections(mesh_name, mesh_data)

print("🔄 UV and collection import process completed.")
