import os
import networkx as nx
import config

def find_edges_from_mono_nodes(G):
    edges_from_mono_nodes = []

    # Iterate over all nodes to find nodes of type 'mono'
    for node_id, properties in G.nodes(data=True):
        if properties.get('type') == 'Mono_Component':
            # Find all edges where this node is the source
            for target_id, edge_data in G[node_id].items():
                edges_from_mono_nodes.append((node_id, target_id, edge_data))

    return edges_from_mono_nodes

def create_exp_settings(G, mono_lis, scene_settings):
    csharp_script_note = "```"

    for mono_id, gobj_id, type in mono_lis:
        #print(G.nodes[gobj_id].get('properties', {}))
        mono_script_ids = []
        transform_ids = None
        for target_id, edge_data in G[gobj_id].items():
            if edge_data["type"] == "Has_Mono_Comp":
                mono_script_ids.append(target_id)
            else:
                if edge_data["type"] == "Has_Other_Comp":
                    transform_ids = target_id

        gobj_properties = G.nodes[gobj_id].get('properties', {})
        for property in gobj_properties:
            if 'm_Name' in property:
                gobj_name = property['m_Name']
        
        script_code_header = config.prompt_source_code_header + csharp_script_note
        script_code = script_code_header
        for mono_script in mono_script_ids:
            source_file_properties = None
            for target_id, edge_data in G[mono_script].items():
                if edge_data["type"] == "Source_Code_File":
                    source_file_properties = G.nodes[target_id].get('properties', {})

                    source_file_path = source_file_properties["file_path"].split('.meta')[0]
                    with open(source_file_path, 'r') as f1:
                        script_code = script_code + "\n" + f1.read() + "\n" + csharp_script_note

            if source_file_properties:
                exp_dir = './experiment/' + gobj_id + "_" + gobj_name + "_" + mono_script
                exp_prompt = "prompt.txt"
                prompt_headers = "Imagine you are helping software test engineers to create comprehensive test plans without delving into the specifics of the code." \
                    "Test engineers want to test the App. One game object we want to test in the scene of " + scene_settings["scene_name"] + " is " + gobj_name + ".\n"
                prompt_instruct = "The current scene is " + scene_settings["scene_name"] + ". One of the gameobjects called " + gobj_name + ".\n" +config.prompt_instruct_format
                prompt_source_code = script_code + "\n"
                scene_setting = config.prompt_meta_format + config.prompt_meta_header + "[GameObject]\n" + str(gobj_properties) + "\n" + "[MonoBehaviour Component]\n" + str(source_file_properties) + "\n" + "[Transform Component]\n" + str(G.nodes[transform_ids].get('properties', {}))
                if not os.path.exists(exp_dir):
                    os.mkdir(exp_dir)
                with open(os.path.join(exp_dir, exp_prompt), 'w') as f:
                    f.write(prompt_headers)
                    f.write(prompt_instruct)
                    f.write(prompt_source_code)
                    f.write(scene_setting)
                    f.close()



def main():
    result_dir = 'Results_Game/scene_detailed_info/mainResults'
    
    # List to store the loaded graphs
    graphs = []

    # Iterate over all files in the directory
    for filename in os.listdir(result_dir):
        # Check if the file ends with '.gml'
        if filename.endswith('.gml'):
            scene_settings = {}
            file_path = os.path.join(result_dir, filename)
            print(f"Loading graph from {file_path}")

            all_mono_edge = []
            
            # Load the graph from the GML file
            graph = nx.read_gml(file_path)

            #find all edges from monos
            all_mono_edge = find_edges_from_mono_nodes(graph)
            scene_settings["scene_name"] = filename.split('.unity')[0] + '.unity'

            create_exp_settings(graph, all_mono_edge, scene_settings)
            
            # Add the loaded graph to the list
            graphs.append(graph)
    
    # You can now work with the list of graphs
    print(f"Loaded {len(graphs)} graphs.")

    # Example: Print basic information about each graph
    for i, graph in enumerate(graphs):
        print(f"Graph {i+1}:")
        print(f"  Nodes: {graph.number_of_nodes()}")
        print(f"  Edges: {graph.number_of_edges()}")

if __name__ == "__main__":
    main()
