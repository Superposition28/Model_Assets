import bpy
import os
import csv
import json
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

# ------------------------
# Function to import UV and collection data
# ------------------------

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


# ------------------------
# Operator to open file dialog and process CSV
# ------------------------

class ImportCSVOperator(Operator, ImportHelper):
    """Import UVs and Collections from CSV"""
    bl_idname = "import_scene.csv_uv"  # Unique ID for the operator
    bl_label = "Import UV CSV"          # Display name
    filename_ext = ".csv"               # Filter file types

    filter_glob: bpy.props.StringProperty(
        default="*.csv",
        options={'HIDDEN'},
    )

    def execute(self, context):
        csv_import_path = self.filepath
        print(f"✅ Selected file: {csv_import_path}")

        # Check if file exists
        if not os.path.exists(csv_import_path):
            self.report({'ERROR'}, f"File not found: {csv_import_path}")
            return {'CANCELLED'}

        # Read CSV
        csv_data = {}
        with open(csv_import_path, 'r', newline='') as csvfile:
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

        print(f"✅ Loaded {len(csv_data)} meshes from CSV.")

        # Import UV and collections
        for mesh_name, mesh_data in csv_data.items():
            import_uv_and_collections(mesh_name, mesh_data)

        print("🔄 UV and collection import completed.")

        return {'FINISHED'}


# ------------------------
# Register and launch
# ------------------------

def register():
    bpy.utils.register_class(ImportCSVOperator)

def unregister():
    bpy.utils.unregister_class(ImportCSVOperator)

if __name__ == "__main__":
    register()
    bpy.ops.import_scene.csv_uv('INVOKE_DEFAULT')  # Launch file selector
