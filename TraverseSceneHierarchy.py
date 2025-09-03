import os
import json
import networkx as nx
import argparse
from typing import List, Dict, Any

def GenerateTestPlan(G, results_dir):
    """
    生成测试计划，筛选出所有需要进行测试的GameObject列表
    
    Args:
        G: NetworkX图对象，包含所有节点和边
        results_dir: 结果目录路径
    
    Returns:
        List[Dict]: 包含测试对象的字典列表
    """
    
    # 存储测试对象的列表
    test_objects = []
    processed_nodes = set()  # 用于跟踪已处理的节点
    
    # 加载 gobj_tag.json 文件
    gobj_tag_file = os.path.join(results_dir, 'gobj_tag.json')
    gobj_tag_data = {}
    if os.path.exists(gobj_tag_file):
        try:
            with open(gobj_tag_file, 'r', encoding='utf-8') as f:
                gobj_tag_data = json.load(f)
            print(f"成功加载 gobj_tag.json 文件")
        except Exception as e:
            print(f"加载 gobj_tag.json 文件失败: {e}")
    
    def get_tag_info_from_gobj_tag(node_id):
        """
        从 gobj_tag.json 中获取指定节点ID的tag信息
        
        Args:
            node_id: 节点ID
        
        Returns:
            str: tag名称，如果未找到则返回None
        """
        if not gobj_tag_data:
            return None
        
        # 检查 gobj_tag.json 的数据结构
        # 如果第一个元素是字典且包含 'id' 字段，说明是旧格式
        # 如果第一个元素是字符串，说明是新格式（tag名称 -> GameObject ID列表）
        first_key = next(iter(gobj_tag_data), None)
        if first_key and isinstance(gobj_tag_data[first_key], list):
            first_item = gobj_tag_data[first_key][0] if gobj_tag_data[first_key] else None
            
            if isinstance(first_item, dict) and 'id' in first_item:
                # 旧格式：场景文件 -> GameObject列表
                for scene_file, gameobjects in gobj_tag_data.items():
                    if isinstance(gameobjects, list):
                        for gobj_info in gameobjects:
                            if isinstance(gobj_info, dict) and gobj_info.get('id') == node_id:
                                tag_name = gobj_info.get('tag')
                                if tag_name:  # 只返回非空的tag名称
                                    return tag_name
            else:
                # 新格式：tag名称 -> GameObject ID列表
                for tag_name, gameobject_ids in gobj_tag_data.items():
                    if isinstance(gameobject_ids, list) and node_id in gameobject_ids:
                        return tag_name
        
        return None
    
    def collect_all_descendant_mono_info(node_id, current_depth):
        """
        递归收集指定节点的所有后代节点的Mono组件信息
        
        Args:
            node_id: 起始节点ID
            current_depth: 当前深度
        
        Returns:
            List[Dict]: 包含所有后代节点Mono组件信息的列表
        """
        descendant_mono_info = []
        
        # 查找该节点的所有子节点
        child_edges = [(s, t) for s, t, d in G.edges(data=True) 
                       if s == node_id and d.get('type') == 'Has_Child']
        
        for source, child_id in child_edges:
            if child_id in G.nodes:
                child_node_data = G.nodes[child_id]
                
                # 检查子节点是否有Mono组件
                child_mono_edges = [(s, t) for s, t, d in G.edges(data=True) 
                                   if s == child_id and d.get('type') == 'Has_Mono_Comp']
                
                # 收集所有有效的Mono组件target节点
                valid_mono_targets = []
                for source, target in child_mono_edges:
                    # 检查target节点是否包含Source_Code_File关系（且为source）
                    has_source_code_file = False
                    for s, t, edge_data in G.edges(data=True):
                        if s == target and edge_data.get('type') == 'Source_Code_File':
                            has_source_code_file = True
                            break
                    
                    # 只有当target节点包含Source_Code_File关系时才添加到有效列表
                    if has_source_code_file:
                        valid_mono_targets.append(target)
                
                # 如果有有效的Mono组件target节点，则记录信息
                if valid_mono_targets:
                    # 查找母节点信息
                    parent_info = None
                    for s, t, edge_data in G.edges(data=True):
                        if t == child_id and edge_data.get('type') == 'Has_Child':
                            if s in G.nodes:
                                parent_node_data = G.nodes[s]
                                parent_info = {
                                    'parent_id': s,
                                    'parent_name': get_gameobject_name_with_prefab_check(s, parent_node_data, G)
                                }
                            break
                    
                    # 检查是否有 Tag_Logic_Relation 关系
                    tag_logic_info_list = []
                    tag_logic_edges = [(s, t) for s, t, d in G.edges(data=True) 
                                      if s == child_id and d.get('type') == 'Tag_Logic_Relation']
                    if tag_logic_edges:
                        for source, target in tag_logic_edges:
                            tag_name = get_tag_info_from_gobj_tag(target)
                            if tag_name:
                                tag_logic_info_list.append({
                                    'id': target,
                                    'gameobject_name': get_gameobject_name_with_prefab_check(target, G.nodes[target], G),
                                    'tag_name': tag_name
                                })
                    
                    descendant_mono_info.append({
                        'child_id': child_id,
                        'child_name': get_gameobject_name_with_prefab_check(child_id, child_node_data, G),
                        'mono_comp_targets': [{
                            'source': child_id,
                            'target': target,
                            'edge_type': 'Has_Mono_Comp',
                            'mono_property': G.nodes[target].get('properties', {}) if target in G.nodes else {}
                        } for target in valid_mono_targets],
                        'depth': current_depth + 1,
                        'parent_info': parent_info,
                        'tag_logic_info': tag_logic_info_list
                    })
                
                # 递归检查子节点的子节点
                child_descendant_info = collect_all_descendant_mono_info(child_id, current_depth + 1)
                if child_descendant_info:
                    descendant_mono_info.extend(child_descendant_info)
        
        return descendant_mono_info
    
    def process_gameobject_node(node_id, node_data, parent_id=None, depth=0):
        """
        递归处理GameObject节点及其子节点，支持多层递归查询Mono组件
        
        Args:
            node_id: 节点ID
            node_data: 节点数据
            parent_id: 父节点ID（如果有的话）
            depth: 当前递归深度
        """
        # 如果节点已经处理过，直接返回
        if node_id in processed_nodes:
            return None
        
        # 检查节点类型是否为GameObject相关
        if node_data.get('type') not in ['GameObject', 'Prefab GameObject', 'PrefabInstance']:
            return None
        
        # 查找该节点的Has_Mono_Comp关系
        mono_comp_relations = []
        for source, target, edge_data in G.edges(data=True):
            if source == node_id and edge_data.get('type') == 'Has_Mono_Comp':
                # 检查target节点是否包含Source_Code_File关系（且为source）
                has_source_code_file = False
                for s, t, edge_data2 in G.edges(data=True):
                    if s == target and edge_data2.get('type') == 'Source_Code_File':
                        has_source_code_file = True
                        break
                
                # 只有当target节点包含Source_Code_File关系时才添加
                if has_source_code_file:
                    # 从图中获取source节点的属性
                    target_properties = {}
                    if target in G.nodes:
                        target_node_data = G.nodes[target]
                        target_properties = target_node_data.get('properties', {})
                    
                    mono_comp_relations.append({
                        'source': source,
                        'target': target,
                        'edge_type': 'Has_Mono_Comp',
                        'mono_property': target_properties
                    })
        
        # 查找该节点的Has_Child关系
        child_relations = []
        for source, target, edge_data in G.edges(data=True):
            if source == node_id and edge_data.get('type') == 'Has_Child':
                child_relations.append({
                    'source': source,
                    'target': target,
                    'edge_type': 'Has_Child'
                })
        
        # 检查是否有 Tag_Logic_Relation 关系
        tag_logic_info_list = []
        tag_logic_edges = [(s, t) for s, t, d in G.edges(data=True) 
                          if s == node_id and d.get('type') == 'Tag_Logic_Relation']
        if tag_logic_edges:
            for source, target in tag_logic_edges:
                tag_name = get_tag_info_from_gobj_tag(target)
                if tag_name:
                    tag_logic_info_list.append({
                        'id': target,
                        'gameobject_name': get_gameobject_name_with_prefab_check(target, G.nodes[target], G),
                        'tag_name': tag_name
                    })
        
        # 如果该节点有Has_Mono_Comp关系，则添加到测试对象列表
        if mono_comp_relations:
            test_object = {
                'gameobject_id': node_id,
                'gameobject_type': node_data.get('type', 'Unknown'),
                'gameobject_name': get_gameobject_name_with_prefab_check(node_id, node_data, G),
                'mono_comp_relations': mono_comp_relations,
                'child_relations': child_relations,
                'child_mono_comp_info': [],
                'parent_id': parent_id,
                'depth': depth,
                'tag_logic_info': tag_logic_info_list
            }
            
            # 标记节点为已处理
            processed_nodes.add(node_id)
            
            # 递归处理子节点
            for child_rel in child_relations:
                child_id = child_rel['target']
                if child_id in G.nodes():
                    child_node_data = G.nodes[child_id]
                    # 递归处理子节点
                    child_result = process_gameobject_node(child_id, child_node_data, node_id, depth + 1)
                    
                    # 如果子节点有Mono组件，收集其信息
                    if child_result:
                        child_mono_comp_info = []
                        
                        # 首先收集子节点的Mono组件信息（避免重复查找）
                        child_mono_targets = []
                        for source, target, edge_data in G.edges(data=True):
                            if source == child_id and edge_data.get('type') == 'Has_Mono_Comp':
                                # 检查target节点是否包含Source_Code_File关系（且为source）
                                has_source_code_file = False
                                for s, t, edge_data2 in G.edges(data=True):
                                    if s == target and edge_data2.get('type') == 'Source_Code_File':
                                        has_source_code_file = True
                                        break
                                
                                # 只有当target节点包含Source_Code_File关系时才添加
                                if has_source_code_file:
                                    child_mono_targets.append(target)
                        
                        # 如果有有效的Mono组件target节点，则记录信息
                        if child_mono_targets:
                            # 查找母节点信息
                            parent_info = None
                            for s, t, edge_data2 in G.edges(data=True):
                                if t == child_id and edge_data2.get('type') == 'Has_Child':
                                    if s in G.nodes:
                                        parent_node_data = G.nodes[s]
                                        parent_info = {
                                            'parent_id': s,
                                            'parent_name': get_gameobject_name_with_prefab_check(s, parent_node_data, G)
                                        }
                                    break
                            
                            # 检查子节点是否有 Tag_Logic_Relation 关系
                            child_tag_logic_info_list = []
                            child_tag_logic_edges = [(s, t) for s, t, d in G.edges(data=True) 
                                                   if s == child_id and d.get('type') == 'Tag_Logic_Relation']
                            if child_tag_logic_edges:
                                for source, target in child_tag_logic_edges:
                                    tag_name = get_tag_info_from_gobj_tag(target)
                                    if tag_name:
                                        child_tag_logic_info_list.append({
                                            'id': target,
                                            'gameobject_name': get_gameobject_name_with_prefab_check(target, G.nodes[target], G),
                                            'tag_name': tag_name
                                        })
                            
                            child_mono_comp_info.append({
                                'child_id': child_id,
                                'child_name': get_gameobject_name_with_prefab_check(child_id, child_node_data, G),
                                'mono_comp_targets': [{
                                    'source': child_id,
                                    'target': mono_target,
                                    'edge_type': 'Has_Mono_Comp',
                                    'mono_property': G.nodes[mono_target].get('properties', {}) if mono_target in G.nodes else {}
                                } for mono_target in child_mono_targets],
                                'depth': depth + 1,
                                'parent_info': parent_info,
                                'tag_logic_info': child_tag_logic_info_list
                            })
                        
                        if child_mono_comp_info:
                            test_object['child_mono_comp_info'].extend(child_mono_comp_info)
                        
                        # 递归收集子节点的子节点（孙节点）的Mono组件信息
                        child_child_mono_info = collect_all_descendant_mono_info(child_id, depth + 1)
                        if child_child_mono_info:
                            test_object['child_mono_comp_info'].extend(child_child_mono_info)
            
            return test_object
        
        # 如果该节点没有Has_Mono_Comp关系，但子节点可能有
        # 递归处理子节点，看是否有子节点包含Mono组件（支持多层递归）
        has_child_with_mono = False
        child_mono_comp_info = []
        
        for child_rel in child_relations:
            child_id = child_rel['target']
            if child_id in G.nodes():
                child_node_data = G.nodes[child_id]
                # 递归处理子节点
                child_result = process_gameobject_node(child_id, child_node_data, node_id, depth + 1)
                
                if child_result:
                    has_child_with_mono = True
                    # 收集子节点的Mono组件信息
                    child_mono_targets = []
                    for source, target, edge_data in G.edges(data=True):
                        if source == child_id and edge_data.get('type') == 'Has_Mono_Comp':
                            # 检查target节点是否包含Source_Code_File关系（且为source）
                            has_source_code_file = False
                            for s, t, edge_data2 in G.edges(data=True):
                                if s == target and edge_data2.get('type') == 'Source_Code_File':
                                    has_source_code_file = True
                                    break
                            
                            # 只有当target节点包含Source_Code_File关系时才添加到有效列表
                            if has_source_code_file:
                                child_mono_targets.append(target)
                    
                    # 如果有有效的Mono组件target节点，则记录信息
                    if child_mono_targets:
                        # 查找母节点信息
                        parent_info = None
                        for s, t, edge_data2 in G.edges(data=True):
                            if t == child_id and edge_data2.get('type') == 'Has_Child':
                                if s in G.nodes:
                                    parent_node_data = G.nodes[s]
                                    parent_info = {
                                        'parent_id': s,
                                        'parent_name': get_gameobject_name_with_prefab_check(s, parent_node_data, G)
                                    }
                                break
                        
                        # 检查子节点是否有 Tag_Logic_Relation 关系
                        child_tag_logic_info_list = []
                        child_tag_logic_edges = [(s, t) for s, t, d in G.edges(data=True) 
                                               if s == child_id and d.get('type') == 'Tag_Logic_Relation']
                        if child_tag_logic_edges:
                            for source, target in child_tag_logic_edges:
                                tag_name = get_tag_info_from_gobj_tag(target)
                                if tag_name:
                                    child_tag_logic_info_list.append({
                                        'id': target,
                                        'gameobject_name': get_gameobject_name_with_prefab_check(target, G.nodes[target], G),
                                        'tag_name': tag_name
                                    })
                        
                        child_mono_comp_info.append({
                            'child_id': child_id,
                            'child_name': get_gameobject_name_with_prefab_check(child_id, child_node_data, G),
                            'mono_comp_targets': [{
                                'source': child_id,
                                'target': target,
                                'edge_type': 'Has_Mono_Comp',
                                'mono_property': G.nodes[target].get('properties', {}) if target in G.nodes else {}
                            } for target in child_mono_targets],
                            'depth': depth + 1,
                            'parent_info': parent_info,
                            'tag_logic_info': child_tag_logic_info_list
                        })
                    
                    # 递归收集子节点的子节点（孙节点）的Mono组件信息
                    child_child_mono_info = collect_all_descendant_mono_info(child_id, depth + 1)
                    if child_child_mono_info:
                        child_mono_comp_info.extend(child_child_mono_info)
        
        # 如果子节点中有Mono组件，也将该节点加入列表
        if has_child_with_mono:
            test_object = {
                'gameobject_id': node_id,
                'gameobject_type': node_data.get('type', 'Unknown'),
                'gameobject_name': get_gameobject_name_with_prefab_check(node_id, node_data, G),
                'mono_comp_relations': [],
                'child_relations': child_relations,
                'child_mono_comp_info': child_mono_comp_info,
                'parent_id': parent_id,
                'note': 'Added because child nodes contain Mono components',
                'depth': depth,
                'tag_logic_info': tag_logic_info_list
            }
            
            # 标记节点为已处理
            processed_nodes.add(node_id)
            return test_object
        
        return None
    
    # 首先找到所有根节点（没有父节点的节点）
    root_nodes = []
    for node_id, node_data in G.nodes(data=True):
        if node_data.get('type') in ['GameObject', 'Prefab GameObject', 'PrefabInstance']:
            # 检查是否有其他节点指向这个节点作为子节点
            has_parent = False
            for source, target, edge_data in G.edges(data=True):
                if target == node_id and edge_data.get('type') == 'Has_Child':
                    has_parent = True
                    break
            
            if not has_parent:
                root_nodes.append((node_id, node_data))
    
    # 按层次顺序处理节点：从根节点开始，然后是子节点
    def process_nodes_in_order():
        """按层次顺序处理节点"""
        ordered_results = []
        
        # 处理根节点
        for root_id, root_data in root_nodes:
            if root_id not in processed_nodes:
                result = process_gameobject_node(root_id, root_data, depth=0)
                if result:
                    ordered_results.append(result)
        
        # 处理其他节点（按层次顺序）
        while True:
            new_nodes_added = False
            for node_id, node_data in G.nodes(data=True):
                if (node_id not in processed_nodes and 
                    node_data.get('type') in ['GameObject', 'Prefab GameObject', 'PrefabInstance']):
                    
                    # 检查是否所有父节点都已经处理过
                    all_parents_processed = True
                    for source, target, edge_data in G.edges(data=True):
                        if target == node_id and edge_data.get('type') == 'Has_Child':
                            if source not in processed_nodes:
                                all_parents_processed = False
                                break
                    
                    if all_parents_processed:
                        result = process_gameobject_node(node_id, node_data, depth=0)
                        if result:
                            ordered_results.append(result)
                            new_nodes_added = True
            
            # 如果没有新节点被添加，说明所有节点都已处理
            if not new_nodes_added:
                break
        
        return ordered_results
    
    # 按层次顺序处理节点
    test_objects = process_nodes_in_order()
    
    # 输出测试对象列表
    print(f"找到 {len(test_objects)} 个需要测试的GameObject（按层次顺序排列）:")
    print("=" * 80)
    
    # 创建层次显示信息
    def get_hierarchy_level(obj):
        """获取对象的层次级别"""
        level = 0
        current_parent = obj.get('parent_id')
        while current_parent:
            level += 1
            # 查找当前父节点的父节点
            for test_obj in test_objects:
                if test_obj['gameobject_id'] == current_parent:
                    current_parent = test_obj.get('parent_id')
                    break
            else:
                break
        return level
    
    for i, obj in enumerate(test_objects, 1):
        hierarchy_level = get_hierarchy_level(obj)
        indent = "  " * hierarchy_level
        
        print(f"\n{i}. {indent}GameObject ID: {obj['gameobject_id']}")
        print(f"{indent}   名称: {obj['gameobject_name']}")
        print(f"{indent}   类型: {obj['gameobject_type']}")
        print(f"{indent}   层次级别: {hierarchy_level}")
        
        # 显示父节点信息（如果有）
        if obj.get('parent_id'):
            print(f"{indent}   父节点ID: {obj['parent_id']}")
        
        # 显示备注信息（如果有）
        if obj.get('note'):
            print(f"{indent}   备注: {obj['note']}")
        
        print(f"{indent}   Mono组件关系数量: {len(obj['mono_comp_relations'])}")
        print(f"{indent}   子对象关系数量: {len(obj['child_relations'])}")
        print(f"{indent}   子对象Mono组件信息数量: {len(obj['child_mono_comp_info'])}")
        
        # 输出Mono组件关系详情
        if obj['mono_comp_relations']:
            print(f"{indent}   Mono组件关系:")
            for rel in obj['mono_comp_relations']:
                print(f"{indent}     - {rel['source']} -> {rel['target']} ({rel['edge_type']})")
        
        # 输出Tag_Logic_Relation信息（如果有）
        if obj.get('tag_logic_info') and len(obj['tag_logic_info']) > 0:
            print(f"{indent}   Tag_Logic_Relation:")
            for i, tag_info in enumerate(obj['tag_logic_info']):
                print(f"{indent}     {i+1}. ID: {tag_info['id']}")
                print(f"{indent}        Tag名称: {tag_info['tag_name']}")
                if i < len(obj['tag_logic_info']) - 1:  # 不是最后一个元素时添加空行
                    print()
        
        # 输出子对象关系详情
        if obj['child_relations']:
            print(f"{indent}   子对象关系:")
            for rel in obj['child_relations']:
                print(f"{indent}     - {rel['source']} -> {rel['target']} ({rel['edge_type']})")
        
        # 输出子对象Mono组件信息详情
        if obj['child_mono_comp_info']:
            print(f"{indent}   子对象Mono组件信息:")
            for info in obj['child_mono_comp_info']:
                print(f"{indent}     - 子对象: {info['child_name']} (ID: {info['child_id']})")
                print(f"{indent}       Mono组件:")
                for target_info in info['mono_comp_targets']:
                    print(f"{indent}         - {target_info['source']} -> {target_info['target']} ({target_info['edge_type']})")
                
                # 输出Tag_Logic_Relation信息（如果有）
                if info.get('tag_logic_info') and len(info['tag_logic_info']) > 0:
                    print(f"{indent}       Tag_Logic_Relation:")
                    for i, tag_info in enumerate(info['tag_logic_info']):
                        print(f"{indent}       {i+1}. ID: {tag_info['id']}")
                        print(f"{indent}          Tag名称: {tag_info['tag_name']}")
                        if i < len(info['tag_logic_info']) - 1:  # 不是最后一个元素时添加空行
                            print()
    
    # 保存测试计划到JSON文件
    test_plan_file = os.path.join(results_dir, 'gobj_hierarchy.json')
    with open(test_plan_file, 'w', encoding='utf-8') as f:
        json.dump(test_objects, f, indent=2, ensure_ascii=False)
    
    print(f"\n测试计划已保存到: {test_plan_file}")
    
    return test_objects

def get_gameobject_name(node_data: Dict[str, Any]) -> str:
    """
    从节点数据中提取GameObject名称
    
    Args:
        node_data: 节点数据字典
    
    Returns:
        str: GameObject名称，如果未找到则返回"Unknown"
    """
    # 首先检查是否有直接的m_Name字段
    if 'properties' in node_data:
        for prop_set in node_data['properties']:
            if isinstance(prop_set, dict) and 'm_Name' in prop_set:
                return prop_set['m_Name']
    
    # 如果没有直接的m_Name字段，检查m_Modifications中的m_Name
    if 'properties' in node_data:
        prop_set = node_data['properties']
        if isinstance(prop_set, dict):
            if node_data['type'] == 'PrefabInstance':
                prop_set_lis = prop_set['PrefabInstance']
                for prop_set_child in prop_set_lis:
                    if 'm_Modification' in prop_set_child:
                        mod_prefab_set = prop_set_child['m_Modification']
                        for mod_set in mod_prefab_set:
                            if 'm_Modifications' in mod_set:
                                for i in range(len(mod_set['m_Modifications'])):
                                    mod_set_child = mod_set['m_Modifications'][i]
                                    if 'propertyPath' in mod_set_child:
                                        if mod_set_child['propertyPath'] == 'm_Name':
                                            # 找到m_Name修改，下一个元素包含值
                                            if i + 1 < len(mod_set['m_Modifications']):
                                                m_name_value = mod_set['m_Modifications'][i+1]['value']
                                                if isinstance(m_name_value, str):
                                                    return m_name_value.strip()
        elif isinstance(prop_set, list):
            for prop_set_child in prop_set:
                if 'm_Modification' in prop_set_child:
                    mod_prefab_set = prop_set_child['m_Modification']
                    for mod_set in mod_prefab_set:
                        if 'm_Modifications' in mod_set:
                            for i in range(len(mod_set['m_Modifications'])):
                                mod_set_child = mod_set['m_Modifications'][i]
                                if 'propertyPath' in mod_set_child:
                                    if mod_set_child['propertyPath'] == 'm_Name':
                                        # 找到m_Name修改，下一个元素包含值
                                        if i + 1 < len(mod_set['m_Modifications']):
                                            m_name_value = mod_set['m_Modifications'][i+1]['value']
                                            if isinstance(m_name_value, str):
                                                return m_name_value.strip()
    
    return "Unknown"

def get_gameobject_name_with_prefab_check(node_id: str, node_data: Dict[str, Any], G: nx.Graph) -> str:
    """
    从节点数据中提取GameObject名称，对包含"stripped"字段的节点特殊处理
    
    Args:
        node_id: 节点ID
        node_data: 节点数据字典
        G: NetworkX图对象
    
    Returns:
        str: GameObject名称，如果未找到则返回"Unknown"
    """
    # 如果节点ID包含"stripped"字段，查找PrefabInstance_INFO关系
    if "stripped" in node_id:
        # 查找该节点是否有"PrefabInstance_INFO"关系
        prefab_info_edges = [(s, t) for s, t, d in G.edges(data=True) 
                            if s == node_id and d.get('type') == 'PrefabInstance_INFO']
        
        if prefab_info_edges:
            # 找到PrefabInstance_INFO关系，使用target节点的名称
            for source, target in prefab_info_edges:
                if target in G.nodes:
                    target_node_data = G.nodes[target]
                    target_name = get_gameobject_name(target_node_data)
                    if target_name != "Unknown":
                        return target_name
    
    # 如果上述条件不满足，使用原来的逻辑
    return get_gameobject_name(node_data)

def load_graph_from_gml(gml_file_path: str) -> nx.Graph:
    """
    从GML文件加载图
    
    Args:
        gml_file_path: GML文件路径
    
    Returns:
        nx.Graph: 加载的图对象
    """
    if not os.path.exists(gml_file_path):
        raise FileNotFoundError(f"GML文件未找到: {gml_file_path}")
    
    try:
        graph = nx.read_gml(gml_file_path)
        print(f"成功加载图: {gml_file_path}")
        print(f"节点数量: {graph.number_of_nodes()}")
        print(f"边数量: {graph.number_of_edges()}")
        return graph
    except Exception as e:
        raise Exception(f"加载GML文件失败: {e}")

def find_gml_files(results_dir: str) -> List[str]:
    """
    在结果目录中查找所有GML文件
    
    Args:
        results_dir: 结果目录路径
    
    Returns:
        List[str]: GML文件路径列表
    """
    gml_files = []
    
    # 遍历目录查找GML文件
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            if file.endswith('.gml'):
                gml_files.append(os.path.join(root, file))
    
    return gml_files

def main():
    """
    主函数：查找GML文件并生成测试计划
    """
    # 设置参数解析
    parser = argparse.ArgumentParser(description="生成Unity场景依赖图的测试计划")
    parser.add_argument('-r', '--results-dir', required=True, 
                       help='结果目录路径，包含GML文件')
    
    args = parser.parse_args()
    results_dir = args.results_dir
    
    # 查找所有GML文件
    gml_files = find_gml_files(results_dir)
    
    if not gml_files:
        print("未找到任何GML文件")
        return
    
    print(f"找到 {len(gml_files)} 个GML文件:")
    for gml_file in gml_files:
        print(f"  - {gml_file}")
    
    # 处理每个GML文件
    for gml_file in gml_files:
        print(f"\n处理文件: {gml_file}")
        print("-" * 60)
        
        try:
            # 加载图
            graph = load_graph_from_gml(gml_file)
            
            # 生成测试计划
            test_objects = GenerateTestPlan(graph, results_dir)
            
            print(f"文件 {gml_file} 处理完成，找到 {len(test_objects)} 个测试对象")
            
        except Exception as e:
            print(f"处理文件 {gml_file} 时出错: {e}")
            continue

if __name__ == "__main__":
    main()