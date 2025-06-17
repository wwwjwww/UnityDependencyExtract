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


def analyze_asset(asset_path, results_dir):
    """Execute UnityDataAnalyzer to analyze the specified asset file."""
    if not os.path.exists(config.unity_analyzer_path):
        raise FileNotFoundError(f"UnityDataAnalyzer.exe not found at {config.unity_analyzer_path}")

    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    asset_results_dir = os.path.join(results_dir, 'BuildAsset_info')
    if not os.path.exists(asset_results_dir):
        os.makedirs(asset_results_dir)

    command = f'"{config.unity_analyzer_path}" -a "{asset_path}" -r "{asset_results_dir}"'
    print(f"Executing command: {command}")

    subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)


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

        scene_result_path = os.path.join(scene_results_dir, os.path.basename(scene_path) + '.json')
        command = f'"{config.unity_analyzer_path}" -a "{full_scene_path}" -r "{scene_results_dir}"'
        print(f"Analyzing scene: {full_scene_path}")

        subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)


def extract_game_objects(scene_json_path):
    """Extract GameObject information from the scene JSON file."""
    with open(scene_json_path, 'r') as json_file:
        data = json.load(json_file)

    game_objects = []

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

            game_objects.append(game_object)

    return game_objects

def sanitize_key(key):
    """Sanitize the key to ensure it's valid for GML format."""
    return key.replace("- ", "")

def create_scene_graph(scene_paths, project_path, results_dir):
    """Create a graph structure for each scene file."""
    scene_db_dir = os.path.join(results_dir, 'scene_detailed_info', 'mainResults')

    for scene_path in scene_paths:
        scene_json_path = os.path.join(scene_db_dir, os.path.basename(scene_path))
        if not os.path.exists(scene_json_path):
            print(f"Scene JSON file not found: {scene_json_path}")
            continue

        # Extract GameObject information
        game_objects = extract_game_objects(scene_json_path)

        # Create a graph using networkx
        G = nx.Graph()

        # Add nodes and edges to the graph
        for game_object in game_objects:
            node_id = game_object["id"]
            # Sanitize node attributes
            G.add_node(node_id, type="GameObject", properties=game_object["GameObject"])

            # Add edges for components
            for component in game_object["GameObject"]:
                if "m_Component" in component:
                    for comp in component["m_Component"]:
                        sanitized_properties = {sanitize_key(k): v for k, v in comp.items()}
                        comp_id = sanitized_properties["component"][0]["fileID"]  # Changed key to match valid GML key
                        G.add_node(comp_id, type="Component")
                        G.add_edge(node_id, comp_id, type="component")

        # Save the graph in a file
        graph_file_path = os.path.join(scene_db_dir, os.path.basename(scene_path) + '_graph.gml')
        nx.write_gml(G, graph_file_path)
        #fig, ax = plt.subplots()
        #nx.draw(G, with_labels=False, ax=ax)
        #plt.show()

        print(f"Scene graph created: {graph_file_path}")


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Analyze Unity project settings and create scene graphs.")
    parser.add_argument('-p', '--project-path', required=True, help='Path to the Unity project.')
    parser.add_argument('-r', '--results-dir', required=True, help='Path to the results directory.')

    args = parser.parse_args()

    if True:
        # Find the EditorBuildSettings.asset
        asset_path = get_editor_build_settings_path(args.project_path)

        # Analyze the asset
        analyze_asset(asset_path, args.results_dir)

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

        print("Creating Scene Graphs:")
        # Determine the scene JSON files path
        scene_db_dir = os.path.join(args.results_dir, 'scene_detailed_info', 'mainResults')
        scene_json_files = [f for f in os.listdir(scene_db_dir) if f.endswith('.unity.json')]

        # Create graphs for each scene
        create_scene_graph(scene_json_files, args.project_path, args.results_dir)


if __name__ == "__main__":
    main()
