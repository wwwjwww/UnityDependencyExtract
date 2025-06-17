import os
import json
import subprocess
import argparse
import config
import networkx as nx
import matplotlib.pyplot as plt

def get_editor_build_settings_path(project_path):
    """Find the EditorBuildSettings.asset file within the given Unity project path."""
    asset_path = os.path.join(project_path, 'ProjectSettings', 'EditorBuildSettings.asset')
    if not os.path.exists(asset_path):
        raise FileNotFoundError(f"EditorBuildSettings.asset not found at {asset_path}")
    return asset_path

def analyze_asset(asset_path, asset_results_dir):
    """Execute UnityDataAnalyzer to analyze the specified asset file."""
    if not os.path.exists(config.unity_analyzer_path):
        raise FileNotFoundError(f"UnityDataAnalyzer.exe not found at {config.unity_analyzer_path}")

    if not os.path.exists(asset_results_dir):
        os.makedirs(asset_results_dir)

    command = f'"{config.unity_analyzer_path}" -a "{asset_path}" -r "{asset_results_dir}"'
    print(f"Executing command: {command}")

    subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

def analyze_script(script_path, script_results_dir):
    if not os.path.exists(config.csharp_analyzer_path):
        raise FileNotFoundError(f"csharp_analyzer_path.exe not found at {config.csharp_analyzer_path}")

    script_analysis_dir = os.path.join(script_results_dir, 'script_detailed_info', 'mainResults')

    command = f'"{config.csharp_analyzer_path}" -p "{script_path}" -r "{script_analysis_dir}"'
    print(f"Executing command: {command}")

    subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

def analyze_structure_script(script_results_dir):
    if not os.path.exists(config.structure_analyzer_path):
        raise FileNotFoundError(f"structure_analyzer_path.exe not found at {config.structure_analyzer_path}")

    analyze_file = os.path.join(script_results_dir, 'script_detailed_info', 'mainResults', 'CodeAnalysis.json')
    script_analysis_dir = os.path.join(script_results_dir, 'script_detailed_info', 'mainResults')

    command = f'"{config.structure_analyzer_path}" -d "{analyze_file}" -r "{script_analysis_dir}"'
    print(f"Executing command: {command}")

    subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

def find_relation_in_source_code(mono_name, script_results_dir):
    if not os.path.exists(config.csharp_analyzer_path):
        raise FileNotFoundError(f"csharp_analyzer_path.exe not found at {config.csharp_analyzer_path}")

    script_analysis_dir = os.path.join(script_results_dir, 'script_detailed_info', 'mainResults')

    with open(os.path.join(script_analysis_dir, "CodeAnalysis.json"), 'r') as f:
        codeAnalysis = json.load(f)
        mono_file_lis = codeAnalysis["Project"]
        for mono_file in mono_file_lis:
            if mono_file["Name"] == mono_name:
                class_lis = mono_file["Classes"]

def extract_scene_paths_from_json(json_file_path):
    """Extract scene paths from the JSON file produced by UnityDataAnalyzer."""
    with open(json_file_path, 'r') as json_file:
        data = json.load(json_file)
        scenes = data.get("COMPONENTS", [])[0].get("EditorBuildSettings", [])[2].get("m_Scenes", [])
        scene_paths = [scene.get("path") for scene in scenes if "path" in scene]
    return scene_paths

def analyze_scenes(project_path, scene_paths, results_dir):
    """Analyze each scene file using UnityDataAnalyzer."""
    scene_results_dir = os.path.join(results_dir, 'scene_detailed_info')
    if not os.path.exists(scene_results_dir):
        os.makedirs(scene_results_dir)

    for scene_path in scene_paths:
        full_scene_path = os.path.join(project_path, scene_path)
        if not os.path.exists(full_scene_path):
            print(f"Scene file not found: {full_scene_path}")
            continue

        command = f'"{config.unity_analyzer_path}" -a "{full_scene_path}" -r "{scene_results_dir}"'
        print(f"Analyzing scene: {full_scene_path}")

        subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)


def sanitize_keys(set):
    string_to_clean = json.dumps(set)
    if '"- ' in string_to_clean or '" ' in string_to_clean:
        string_to_clean = string_to_clean.replace('"- ', '"').replace('" ', '"')

    return json.loads(string_to_clean)

def extract_scene_settings(scene_json_path):
    """Extract GameObject information from the scene JSON file."""
    with open(scene_json_path, 'r') as json_file:
        data = json.load(json_file)

    all_scene_json = {
        "GameObjects": [],
        "MonoBehaviours": [],
        "Other_Comps": []
    }

    # Iterate over each component in the JSON data
    for component in data.get("COMPONENTS", []):
        if "GameObject" in component:
            game_object = {
                "id": component.get("id", ""),
                "GameObject": []
            }

            # Extract GameObject properties
            for key, value in component.items():
                if key == "GameObject":
                    for set in value:
                        for key_child, val_child in set.items():
                            if key_child == 'm_Component':
                                m_component = {"m_Component": []}
                                for comp in val_child:
                                    m_component["m_Component"].append({
                                        "component":  # Changed key to a valid GML key
                                            [{
                                                "fileID": comp['- component'][0].get("fileID", "")
                                            }]
                                    })
                                game_object["GameObject"].append(m_component)
                            else:
                                game_object["GameObject"].append(set)

            all_scene_json["GameObjects"].append(game_object)

        else:
            if "MonoBehaviour" in component:
                mono_behavior = {
                    "id": component.get("id", ""),
                    "MonoBehaviour": []
                }
                for key, value in component.items():
                    if key == "MonoBehaviour":
                        for set in value:
                            set_store = sanitize_keys(set)
                            mono_behavior["MonoBehaviour"].append(set_store)

                all_scene_json["MonoBehaviours"].append(mono_behavior)

            else:
                other_comp = {}
                for key, value in component.items():
                    if key == 'id':
                        other_comp[key] = value
                    else:
                        for set in value:
                            set_store = sanitize_keys(set)
                            if key in other_comp:
                                other_comp[key].append(set_store)
                            else:
                                other_comp[key] = []
                                other_comp[key].append(set_store)

                all_scene_json["Other_Comps"].append(other_comp)

    return all_scene_json

def analyze_csharp_meta(asset_paths, results_dir):
    script_results_dir = os.path.join(results_dir, 'script_detailed_info')

    for root, dirs, files in os.walk(asset_paths):
        for file in files:
            if "cs.meta" in file:
                analyze_asset(os.path.join(root, file), script_results_dir)

    script_lis = []
    for root, dirs, files in os.walk(os.path.join(script_results_dir, 'metaResults')):
        for file in files:
            with open(os.path.join(root, file), 'r') as f:
                script_dic = json.load(f)
                script_lis.append(script_dic)
    return script_lis

def AddGobjRelation(G, results_dir):
    codeStructure_json = os.path.join(results_dir, 'script_detailed_info', 'mainResults', 'CodeStructure.json')

    with open(codeStructure_json, 'r') as f:
        read_json = json.load(f)
        structure_lis = read_json["StructureList"]
        edges_to_add = []
        for struct in structure_lis:
            if struct["Name"] == "AllInstantiate":
                detail_struct = struct["Structure"]
                for detail in detail_struct:
                    script_path = detail["Script"]
                    gobj = detail["Arguments"][0]["Argument"]
                    script_id = None
                    source_id = None
                    for node_id, properties in G.nodes(data=True):
                        if properties['type'] == "script_file":
                            for prop, value in properties.items():
                                if prop == "properties":
                                    if value["file_path"] == script_path + ".meta":
                                        script_id = node_id
                    if script_id:
                        for source, target, edge_data in G.edges(data=True):
                        # Check if the current edge matches the target_id and edge_type
                            if target == script_id and edge_data.get('type') == "Source_Code_File":
                                source_id = source
                        
                        if source_id:
                            for node_id, properties in G.nodes(data=True):
                                if node_id == source_id:
                                    for prop, value in properties.items():
                                        if prop == "properties":
                                            mono_lis = value["MonoBehaviour"]
                                            for mono in mono_lis:
                                                if gobj in mono.keys():
                                                    gobj_id = mono[gobj][0]['fileID']
                                                    edges_to_add.append((source_id, gobj_id, "Mono_Comp_Attached_Gobj"))
                        
                        # Add collected edges
                        for source_id, gobj_id, edge_type in edges_to_add:
                            G.add_edge(source_id, gobj_id, type=edge_type)

                                    

def create_scene_database(scene_paths, project_path, results_dir, script_lis):
    """Create a database in JSON format for each scene file."""
    scene_db_dir = os.path.join(results_dir, 'scene_detailed_info', 'mainResults')
    
    for scene_path in scene_paths:
        print(f"Creating scene database for {scene_path}")
        scene_json_path = os.path.join(scene_db_dir, os.path.basename(scene_path))
        if not os.path.exists(scene_json_path):
            print(f"Scene JSON file not found: {scene_json_path}")
            continue

        # Extract GameObject information
        scene_settings = extract_scene_settings(scene_json_path)
        # Create a graph using networkx
        G = nx.Graph()

        # Save the extracted data in a new JSON file
        db_file_path = os.path.join(scene_db_dir, os.path.basename(scene_path) + '_database.json')
        with open(db_file_path, 'w') as db_file:
            json.dump(scene_settings, db_file, indent=2)

        game_objects = scene_settings["GameObjects"]
        mono_behaviours = scene_settings["MonoBehaviours"]
        other_comps = scene_settings["Other_Comps"]

        for gobjs in game_objects:
            fileid_lis = []
            gobj_set = gobjs["GameObject"]
            gobj_id = gobjs["id"]
            G.add_node(gobj_id, type="GameObject", properties=gobj_set)
            for set in gobj_set:
                if "m_Component" in set:
                    comp_lis = set["m_Component"]
                    for comp in comp_lis:
                        file_id = comp["component"][0].get("fileID")
                        fileid_lis.append(file_id)

                    for monos in mono_behaviours:
                        mono_id = monos["id"]
                        for mono_set in monos["MonoBehaviour"]:
                            if "m_Script" in mono_set.keys():
                                mono_guid_set = mono_set["m_Script"]
                                for guid_set in mono_guid_set:
                                    if "guid" in guid_set.keys():
                                        mono_guid = guid_set["guid"]


                        if mono_id in fileid_lis:
                            G.add_node(mono_id, type="Mono_Component", properties=monos)
                            G.add_edge(mono_id, gobj_id, type="Has_Mono_Comp")

                            for script in script_lis:
                                for key, value in script.items():
                                    if value ==  None:
                                        script[key] = ""

                                if mono_guid == script["guid"]:
                                    G.add_node(mono_guid, type="script_file", properties=script)
                                    G.add_edge(mono_id, mono_guid, type="Source_Code_File")

                                    mono_name = script["name"].split(".")[0]
                                    find_relation_in_source_code(mono_name, results_dir)

                    for other in other_comps:
                        other_id = other["id"]
                        if other_id in fileid_lis:
                            comp_name = ''
                            for key in other.keys():
                                if key != 'id':
                                    comp_name = key
                            if 'Transform' in comp_name:
                                G.add_node(other_id, type=comp_name, properties=other)
                                G.add_edge(other_id, gobj_id, type="Has_Other_Comp")
        
        AddGobjRelation(G, results_dir)

        # Save the graph in a file
        graph_file_path = os.path.join(scene_db_dir, os.path.basename(scene_path) + '_graph.gml')
        nx.write_gml(G, graph_file_path)
        print(f"Scene database created: {db_file_path}")

        #fig, ax = plt.subplots()
        #nx.draw(G, with_labels=True, ax=ax)
        #plt.show()


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Analyze Unity project settings.")
    parser.add_argument('-p', '--project-path', required=True, help='Path to the Unity project.')
    parser.add_argument('-r', '--results-dir', required=True, help='Path to the results directory.')

    args = parser.parse_args()

    if True:
        # Find the EditorBuildSettings.asset
        asset_path = get_editor_build_settings_path(args.project_path)
        
        # Analyze the asset
        analyze_asset(asset_path, os.path.join(args.results_dir, "BuildAsset_info"))
        
        # Determine the correct results directory
        asset_name = os.path.basename(asset_path)
        results_subdir = 'mainResults' if not asset_name.endswith('.meta') else 'metaResults'
        json_file_path = os.path.join(args.results_dir, 'BuildAsset_info', results_subdir, f'{asset_name}.json')

        # Extract scene paths from the JSON file
        if os.path.exists(json_file_path):
            scene_paths = extract_scene_paths_from_json(json_file_path)
            print("Extracted Scene Paths:")
            analyze_scenes(args.project_path, scene_paths, args.results_dir)
        else:
            raise FileNotFoundError(f"Analysis result JSON file not found at {json_file_path}")

        print("Analyzing Script Meta File:")
        script_lis = analyze_csharp_meta(os.path.join(args.project_path, 'Assets'), args.results_dir)

        print("Analyzing Script CSharp File:")
        analyze_script(os.path.join(args.project_path, 'Assets'), args.results_dir)

        print("Analyzing script structure File:")
        analyze_structure_script(args.results_dir)

        print("Creating Scene Database:")
        # Determine the scene JSON files path
        scene_db_dir = os.path.join(args.results_dir, 'scene_detailed_info', 'mainResults')
        scene_json_files = [f for f in os.listdir(scene_db_dir) if f.endswith('.unity.json')]

        # Create databases for each scene
        create_scene_database(scene_json_files, args.project_path, args.results_dir, script_lis)

if __name__ == "__main__":
    main()
