#!/usr/bin/env python3
"""
Tag Logic Preprocessor - 预处理tag_logic_info并生成sorted_target_logic_info

该模块的主要功能：
1. 首先循环处理所有含有tag_logic_info的信息，通过与LLM对话筛选
2. 将筛选后的结果以'sorted_target_logic_info'字段写入gobj_hierarchy.json
3. 重新循环新生成的文件，对LLM建立另一段对话
4. 在进行generate_test_plan_conversation函数时，直接查询sorted_target_logic_info字段
5. 使用TAG_LOGIC_CHILD_REQUEST_TEMPLATE模板向LLM提供tag相关的prompt信息
"""

import json
import os
import argparse
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import requests
import networkx as nx
from config import (
    TAG_LOGIC_CHILD_REQUEST_TEMPLATE,
    basicUrl_gpt35,
    OPENAI_API_KEY
)


class TagLogicPreprocessor:
    """Tag Logic预处理器"""
    
    def __init__(self, results_dir: str, scene_name: str = None, app_name: str = None):
        """
        初始化TagLogic预处理器
        
        Args:
            results_dir: 结果目录路径
            scene_name: 场景名称
            app_name: 应用名称
        """
        self.results_dir = results_dir
        self.scene_name = scene_name or "BatScene"
        self.app_name = app_name or "escapeVr"
        self.gobj_hierarchy_path = os.path.join(results_dir, "gobj_hierarchy.json")
        self.scene_data_dir = os.path.join(results_dir, "scene_detailed_info")
        self.script_data_dir = os.path.join(results_dir, "script_detailed_info")
        self.scene_meta_dir = os.path.join(results_dir, "scene_detailed_info", "mainResults")
        
        # 加载gobj_hierarchy.json
        self.gobj_hierarchy = self._load_gobj_hierarchy()
        
        # 加载场景图数据（用于查找Source_Code_File关系）
        self.scene_graphs = self._load_scene_graphs()
        
        # 加载场景元数据（GML文件）
        self.scene_meta_data = self._load_scene_meta_data()
        
        # 用于跟踪已经通过tag_logic_info处理过的对象ID
        self.processed_object_ids = set()
        
        # 存储筛选后的tag_logic_info
        self.sorted_target_logic_info = {}
    
    def _load_gobj_hierarchy(self) -> List[Dict[str, Any]]:
        """加载gobj_hierarchy.json文件"""
        try:
            with open(self.gobj_hierarchy_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载gobj_hierarchy.json失败: {e}")
            return []
    
    def _load_scene_graphs(self) -> Dict[str, nx.Graph]:
        """加载场景图数据（用于查找Source_Code_File关系）"""
        scene_graphs = {}
        
        if not os.path.exists(self.scene_meta_dir):
            print(f"警告: 场景元数据目录不存在: {self.scene_meta_dir}")
            return scene_graphs
        
        # 查找GML文件
        for file in os.listdir(self.scene_meta_dir):
            if file.endswith('.gml'):
                gml_file_path = os.path.join(self.scene_meta_dir, file)
                try:
                    # 加载GML文件
                    graph = nx.read_gml(gml_file_path)
                    scene_name = file.replace('.gml', '')
                    scene_graphs[scene_name] = graph
                    print(f"已加载场景图: {scene_name}")
                except Exception as e:
                    print(f"加载场景图 {file} 失败: {e}")
        
        return scene_graphs
    
    def _load_scene_meta_data(self) -> Dict[str, Any]:
        """加载场景元数据（从GML文件）"""
        scene_meta_data = {}
        
        if not os.path.exists(self.scene_meta_dir):
            print(f"警告: 场景元数据目录不存在: {self.scene_meta_dir}")
            return scene_meta_data
        
        # 查找GML文件
        for file in os.listdir(self.scene_meta_dir):
            if file.endswith('.gml'):
                gml_file_path = os.path.join(self.scene_meta_dir, file)
                try:
                    # 加载GML文件
                    graph = nx.read_gml(gml_file_path)
                    scene_name = file.split(".unity")[0]
                    scene_meta_data[scene_name] = graph
                    print(f"已加载场景GML文件: {scene_name}")
                except Exception as e:
                    print(f"加载GML文件 {file} 失败: {e}")
        
        return scene_meta_data
    
    def _save_gobj_hierarchy(self):
        """保存gobj_hierarchy.json文件"""
        try:
            with open(self.gobj_hierarchy_path, 'w', encoding='utf-8') as f:
                json.dump(self.gobj_hierarchy, f, indent=2, ensure_ascii=False)
            print(f"✅ 已保存gobj_hierarchy.json")
        except Exception as e:
            print(f"❌ 保存gobj_hierarchy.json失败: {e}")
    
    def _call_llm_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        调用LLM API获取响应 - 每次都是新的对话session
        
        Args:
            prompt: 请求内容
            max_retries: 最大重试次数
        
        Returns:
            str: LLM响应，如果失败则返回None
        """
        for attempt in range(max_retries):
            try:
                print(f"    🔄 正在调用LLM API (尝试 {attempt + 1}/{max_retries})...")
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                }
                
                # 每次调用都创建新的对话session，不包含历史对话
                data = {
                    "model": "gpt-5",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 1
                }
                
                response = requests.post(
                    f"{basicUrl_gpt35}chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result['choices'] and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        print("    ✅ LLM API调用成功")
                        return content
                    else:
                        print("    ❌ LLM响应为空")
                        return None
                else:
                    print(f"    ❌ LLM API调用失败: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"    ❌ LLM API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("    ⏳ 等待30秒后重试...")
                    time.sleep(30)
                else:
                    print("    ❌ 所有重试都失败了")
                    return None
        
        return None
            
    def _extract_script_source_code(self, mono_comp_id: str) -> Optional[str]:
        """
        从脚本数据中提取源代码
        
        Args:
            mono_comp_id: Mono组件ID
        
        Returns:
            str: 源代码，如果未找到则返回None
        """
        # 在所有场景图中查找Source_Code_File关系
        for scene_name, scene_graph in self.scene_graphs.items():
            # 查找所有以mono_comp_id为source的Source_Code_File关系
            for source, target, edge_data in scene_graph.edges(data=True):
                if (source == mono_comp_id and 
                    edge_data.get('type') == 'Source_Code_File'):
                    
                    # 从target节点的properties中获取file_path
                    if target in scene_graph.nodes:
                        target_node = scene_graph.nodes[target]
                        if 'properties' in target_node:
                            properties = target_node['properties']
                            
                            # 检查properties是字典还是列表
                            if isinstance(properties, dict):
                                # properties是字典，直接查找file_path
                                if 'file_path' in properties:
                                    file_path = properties['file_path']
                                    # 处理file_path字段，以'.meta'进行strip，截取.strip[0]的字段
                                    if file_path.endswith('.meta'):
                                        file_path = file_path[:-5]  # 移除.meta后缀
                                    
                                    # 尝试加载脚本文件
                                    script_content = self._load_script_file(file_path)
                                    if script_content:
                                        return script_content
                                        
                            elif isinstance(properties, list):
                                # properties是列表，遍历查找file_path
                                for prop in properties:
                                    if isinstance(prop, dict) and 'file_path' in prop:
                                        file_path = prop['file_path']
                                        # 处理file_path字段，以'.meta'进行strip，截取.strip[0]的字段
                                        if file_path.endswith('.meta'):
                                            file_path = file_path[:-5]  # 移除.meta后缀
                                        
                                        # 尝试加载脚本文件
                                        script_content = self._load_script_file(file_path)
                                        if script_content:
                                            return script_content
        
        return None
    
    def _load_script_file(self, file_path: str) -> Optional[str]:
        """
        加载脚本文件内容
        
        Args:
            file_path: 脚本文件路径
        
        Returns:
            str: 脚本文件内容，如果加载失败则返回None
        """
        try:
            # 尝试直接加载文件
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            # 如果直接路径不存在，尝试在脚本目录中查找
            script_filename = os.path.basename(file_path)
            for script_file in os.listdir(self.script_data_dir):
                if script_file == script_filename or script_file.endswith('.cs'):
                    script_file_path = os.path.join(self.script_data_dir, script_file)
                    try:
                        with open(script_file_path, 'r', encoding='utf-8') as f:
                            return f.read()
                    except Exception as e:
                        print(f"读取脚本文件 {script_file} 失败: {e}")
                        continue
            
            return None
        except Exception as e:
            print(f"加载脚本文件 {file_path} 失败: {e}")
            return None
    
    def _find_child_gameobject_info(self, child_id: str, scene_name: str, mono_comp_ids: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        查找子GameObject的信息
        
        Args:
            child_id: 子GameObject的ID
            scene_name: 场景名称
            mono_comp_ids: Mono组件信息列表
        
        Returns:
            Dict: 子GameObject信息，如果未找到则返回None
        """
        if scene_name not in self.scene_meta_data:
            return None
        
        scene_graph = self.scene_meta_data[scene_name]
        
        # 查找子GameObject的元数据
        gobj_data = self._find_gameobject_in_scene_data(child_id, scene_graph)
        if gobj_data:
            MonoBehaviour_lis = []
            for i, mono_comp in enumerate(mono_comp_ids):
                mono_comp_info = {}
                mono_comp_info[f"MonoBehaviour_{i}"] = mono_comp['mono_property']
                MonoBehaviour_lis.append(mono_comp_info)
            gobj_data['MonoBehaviour'] = MonoBehaviour_lis

            return {
                'id': child_id,
                'name': gobj_data.get('GameObject', {}).get('m_Name', 'Unknown'),
                'scene_meta': gobj_data
            }
        
        return None
    
    def _find_gameobject_in_scene_data(self, gobj_id: str, scene_graph: nx.Graph) -> Optional[Dict[str, Any]]:
        """
        在场景数据中查找指定ID的GameObject
        
        Args:
            gobj_id: GameObject的ID
            scene_graph: 场景数据图
        
        Returns:
            Dict: GameObject数据，如果未找到则返回None
        """
        print(f"🔍 在场景图中查找GameObject ID: {gobj_id}")
        print(f"   图节点数量: {scene_graph.number_of_nodes()}")
        print(f"   图边数量: {scene_graph.number_of_edges()}")
        
        # 遍历图中的所有节点
        gobj_data = {}
        found_node = None
        
        for node in scene_graph.nodes:
            node_data = scene_graph.nodes[node]
            #print(f"   检查节点: {node}")
            #print(f"     节点类型: {type(node_data)}")
            #print(f"     节点键: {list(node_data.keys()) if isinstance(node_data, dict) else 'Not a dict'}")

            if str(node.split("stripped")[0]) == str(gobj_id.split("stripped")[0]):
                print(f"      ✅ 找到匹配的GameObject!")
                found_node = node
                gobj_data[node_data.get('type', 'Unknown')] = node_data
                        
                        # 查找相关的Transform组件
                for source, target, edge_data in scene_graph.edges(data=True):
                    if (edge_data.get('type') == "Has_Other_Comp" and 
                        str(source) == str(gobj_id)):
                        print(f"      🔗 找到Has_Other_Comp边: {source} -> {target}")
                        target_node = scene_graph.nodes[target]
                        gobj_data["Transform"] = target_node
                                    
        if found_node:
            print(f"✅ 成功找到GameObject，返回数据结构:")
            for key, value in gobj_data.items():
                print(f"   {key}: {type(value)} - {len(str(value))} 字符")
            return gobj_data
        else:
            print(f"❌ 未找到GameObject ID: {gobj_id}")
            return None
    
    def _get_tag_logic_prompt(self, target_info: Dict[str, Any], child_id: str = None) -> str:
        """
        生成tag_logic_info的prompt
        
        Args:
            target_info: 目标信息
        
        Returns:
            str: tag_logic_info的prompt
        """
        tag_logic_info = target_info.get('tag_logic_info', [])
        if not tag_logic_info:
            return ""
        
        # 构建tag_dict
        tag_dict = {}
        for tag_info in tag_logic_info:
            tag_name = tag_info.get('tag_name')
            tag_id = tag_info.get('id')
            if tag_name and tag_id:
                tag_dict[tag_id] = tag_name
        
        if not tag_dict:
            return ""
        
        # 构建prompt
        prompt = f"""These are the gameobjects that may have corresponding tags with .CompareTag() in the gameobject {child_id}. We will show the corresponding gameobject ID with tags below. Please choose the gameobjects from below that has the corresponding tag to test the gameobject {child_id}. Please only answer with the list of \"gameobject_id\". For instance: ["12345"].\n"""
        prompt += "[dict of tags with gameobject IDs]\n"
        prompt += json.dumps(tag_dict, indent=2)
        
        return prompt
    
    def _process_tag_logic_response(self, response: str, target_info: Dict[str, Any]) -> List[str]:
        """
        解析LLM响应，提取需要的GameObject ID列表
        
        Args:
            response: LLM响应
            target_info: 目标信息
        
        Returns:
            List[str]: 需要的GameObject ID列表
        """
        try:
            # 尝试从响应中提取JSON格式的ID列表
            if '[' in response and ']' in response:
                start = response.find('[')
                end = response.find(']') + 1
                json_str = response[start:end]
                id_list = json.loads(json_str)
                if isinstance(id_list, list):
                    return [str(id) for id in id_list]
            
            # 如果无法解析JSON，尝试其他格式
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('[') and line.endswith(']'):
                    try:
                        id_list = json.loads(line)
                        if isinstance(id_list, list):
                            return [str(id) for id in id_list]
                    except:
                        continue
            
            return []
        except Exception as e:
            print(f"⚠️  解析LLM响应失败: {e}")
            return []
    
    def _get_formatted_script_sources_and_meta(self, needed_gameobject_ids: List[str], scene_name: str) -> str:
        """
        获取指定GameObject的脚本源代码和场景元数据，格式化输出
        
        Args:
            needed_gameobject_ids: 需要的GameObject ID列表
            scene_name: 场景名称
        
        Returns:
            str: 格式化的脚本源代码和场景元数据
        """
        result = ""
        
        for i, gobj_id in enumerate(needed_gameobject_ids):
            result += f"[GameObject {i+1}]: {gobj_id}\n"
            
            # 获取脚本源代码
            script_content = ""
            # 这里需要根据实际的脚本数据结构来实现
            # 暂时使用占位符
            script_content = f"// Script source code for GameObject {gobj_id}"
            
            result += f"Script source code:\n'''\n{script_content}\n'''\n"
            
            # 获取场景元数据
            scene_meta = f"// Scene meta data for GameObject {gobj_id}"
            result += f"Scene meta data:\n'''\n{scene_meta}\n'''\n\n"
        
        return result
    
    def process_all_tag_logic_info(self):
        """
        处理所有含有tag_logic_info的信息，通过与LLM对话筛选
        """
        print(f"🔄 开始处理所有含有tag_logic_info的信息...")
        
        # 遍历所有GameObject
        for gobj_info in self.gobj_hierarchy:
            gobj_id = gobj_info.get('gameobject_id')
            gobj_name = gobj_info.get('gameobject_name')
            
            # 检查是否有tag_logic_info
            tag_logic_info = gobj_info.get('tag_logic_info', [])
            if tag_logic_info:
                print(f"🏷️  处理GameObject {gobj_name} (ID: {gobj_id}) 的tag_logic_info...")
                
                # 处理主GameObject的tag_logic_info
                self._process_gameobject_tag_logic(gobj_info)
            
            # 处理子对象的tag_logic_info
            # 首先处理child_mono_comp_info中的tag_logic_info
            child_mono_comp_info = gobj_info.get('child_mono_comp_info', [])
            if child_mono_comp_info:
                for child_info in child_mono_comp_info:
                    # 检查子对象是否有tag_logic_info
                    child_tag_logic_info = child_info.get('tag_logic_info', [])
                    if child_tag_logic_info:
                        print(f"  🔍 处理子对象 {child_info.get('child_name', 'Unknown')} 的tag_logic_info...")
                        self._process_child_tag_logic(child_info, gobj_info)
            
        
        # 将筛选后的结果写入gobj_hierarchy.json
        self._update_gobj_hierarchy()
        
        print(f"✅ 所有tag_logic_info处理完成！")
    
    def _process_gameobject_tag_logic(self, gobj_info: Dict[str, Any]):
        """
        处理GameObject的tag_logic_info
        
        Args:
            gobj_info: GameObject信息
        """
        gobj_id = gobj_info.get('gameobject_id')
        gobj_name = gobj_info.get('gameobject_name')
        tag_logic_info = gobj_info.get('tag_logic_info', [])
        
        # 生成tag_logic_prompt
        tag_logic_prompt = self._get_tag_logic_prompt(gobj_info)
        if not tag_logic_prompt:
            return
        
        print(f"    📋 发送tag_logic_info请求...")
        
        # 发送tag_logic_info请求
        tag_response = self._call_llm_api(tag_logic_prompt)
        
        if tag_response:
            # 解析LLM响应，提取需要的GameObject ID列表
            needed_gameobject_ids = self._process_tag_logic_response(tag_response, gobj_info)
            
            if needed_gameobject_ids:
                print(f"    📋 LLM需要以下GameObject的信息: {needed_gameobject_ids}")
                
                # 将这些需要的GameObject ID添加到已处理集合中
                self.processed_object_ids.update(needed_gameobject_ids)
                
                # 存储筛选后的信息 - 只保存需要的tag_logic_info
                filtered_tag_logic_info = []
                for tag_info in tag_logic_info:
                    if tag_info.get('id') in needed_gameobject_ids:
                        filtered_tag_logic_info.append(tag_info)
                
                self.sorted_target_logic_info[gobj_id] = filtered_tag_logic_info
            else:
                print(f"    ⚠️  LLM没有指定需要的GameObject ID")
        else:
            print(f"    ❌ 获取tag_logic_info的LLM响应失败")
    
    def _process_child_tag_logic(self, child_info: Dict[str, Any], parent_info: Dict[str, Any]):
        """
        处理子对象的tag_logic_info
        
        Args:
            child_info: 子对象信息
            parent_info: 父对象信息
        """
        # 处理来自child_mono_comp_info的子对象（有child_id字段）
        if 'child_id' in child_info:
            child_id = child_info.get('child_id')
            child_name = child_info.get('child_name')
            mono_comp_ids = child_info.get('mono_comp_targets', [])
        # 处理来自child_relations的子对象（有target字段）
        elif 'target' in child_info:
            child_id = child_info.get('target')
            child_name = child_info.get('child_name', f"Child_{child_id}")
            mono_comp_ids = []
        else:
            print(f"    ⚠️  无法识别子对象结构: {child_info}")
            return
        
        tag_logic_info = child_info.get('tag_logic_info', [])
        
        # 获取子对象的基本信息
        parent_name = parent_info.get('gameobject_name')
        
        # 将当前子对象ID添加到已处理集合中
        self.processed_object_ids.add(child_id)
        
        # 获取脚本源代码
        script_content = ""
        if mono_comp_ids and len(mono_comp_ids) > 0:
            for i, mono_comp in enumerate(mono_comp_ids):
                target_script_id = mono_comp.get('target')
                script_source = self._extract_script_source_code(target_script_id)
                if i == len(mono_comp_ids) - 1:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                else:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                    script_content += "\n'''\n"
                    script_content += f"[Source code {i+1}th of script files ({target_script_id}) attached]\n'''\n"
        
        combined_script_source = script_content if script_content else "// Script source code not found"
        
        # 获取子对象的场景元数据
        child_scene_meta = self._find_child_gameobject_info(child_id, self.scene_name, mono_comp_ids) if mono_comp_ids else None
        
        # 生成tag_logic_prompt
        tag_logic_prompt = self._get_tag_logic_prompt(child_info, child_id)
        
        # 使用TAG_LOGIC_CHILD_REQUEST_TEMPLATE生成请求
        request = TAG_LOGIC_CHILD_REQUEST_TEMPLATE.format(
            child_name=child_name,
            child_id=child_id,
            parent_name=parent_name,
            combined_script_source=combined_script_source,
            child_scene_meta=child_scene_meta['scene_meta'] if child_scene_meta else "// Scene meta data not found",
            tag_logic_prompt=tag_logic_prompt
        )
        print(f"    📋 request: {request}")
        
        print(f"    📋 发送子对象tag_logic_info请求...")
        
        # 调用LLM API获取响应
        tag_response = self._call_llm_api(request)
        print(f"    📋 tag_response: {tag_response}")
        
        if tag_response:
            # 解析LLM响应，提取需要的GameObject ID列表
            needed_gameobject_ids = self._process_tag_logic_response(tag_response, child_info)
            
            if needed_gameobject_ids:
                print(f"    📋 LLM需要以下GameObject的信息: {needed_gameobject_ids}")
                
                # 将这些需要的GameObject ID也添加到已处理集合中
                self.processed_object_ids.update(needed_gameobject_ids)
                
                # 存储筛选后的信息 - 只保存需要的tag_logic_info
                filtered_tag_logic_info = []
                for tag_info in tag_logic_info:
                    if tag_info.get('id') in needed_gameobject_ids:
                        filtered_tag_logic_info.append(tag_info)
                
                self.sorted_target_logic_info[child_id] = filtered_tag_logic_info
            else:
                print(f"    ⚠️  LLM没有指定需要的GameObject ID")
        else:
            print(f"    ❌ 获取子对象tag_logic_info的LLM响应失败")
    
    def _find_child_info(self, child_id: str) -> Optional[Dict[str, Any]]:
        """
        查找子对象信息
        
        Args:
            child_id: 子对象ID
        
        Returns:
            Dict: 子对象信息，如果未找到则返回None
        """
        # 这里需要根据实际的数据结构来实现
        # 暂时返回None
        return None
    
    def _update_gobj_hierarchy(self):
        """
        更新gobj_hierarchy.json，添加sorted_target_logic_info字段
        """
        print(f"📝 更新gobj_hierarchy.json，添加sorted_target_logic_info字段...")
        
        # 为每个GameObject添加sorted_target_logic_info字段
        for gobj_info in self.gobj_hierarchy:
            gobj_id = gobj_info.get('gameobject_id')
            
            # 更新主GameObject的sorted_target_logic_info
            if gobj_id in self.sorted_target_logic_info:
                gobj_info['sorted_target_logic_info'] = self.sorted_target_logic_info[gobj_id]
            else:
                gobj_info['sorted_target_logic_info'] = []
            
            # 更新child_mono_comp_info中每个子对象的sorted_target_logic_info
            child_mono_comp_info = gobj_info.get('child_mono_comp_info', [])
            if child_mono_comp_info:
                for child_info in child_mono_comp_info:
                    child_id = child_info.get('child_id')
                    if child_id and child_id in self.sorted_target_logic_info:
                        child_info['sorted_target_logic_info'] = self.sorted_target_logic_info[child_id]
                    else:
                        child_info['sorted_target_logic_info'] = []
        
        # 保存更新后的文件
        self._save_gobj_hierarchy()
    
    def get_sorted_target_logic_info(self, gobj_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定GameObject的sorted_target_logic_info
        
        Args:
            gobj_id: GameObject ID
        
        Returns:
            Dict: sorted_target_logic_info，如果未找到则返回None
        """
        return self.sorted_target_logic_info.get(gobj_id)
    
    def is_object_processed(self, object_id: str) -> bool:
        """
        检查指定对象是否已经通过tag_logic_info处理过
        
        Args:
            object_id: 对象ID
        
        Returns:
            bool: 是否已处理过
        """
        return object_id in self.processed_object_ids


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="预处理tag_logic_info并生成sorted_target_logic_info")
    parser.add_argument('-r', '--results-dir', required=True, 
                       help='结果目录路径，包含gobj_hierarchy.json和场景数据')
    parser.add_argument('-s', '--scene-name', 
                       help='场景名称（可选，如果不指定则使用config.py中的默认值）')
    parser.add_argument('-a', '--app-name', 
                       help='应用名称（可选，如果不指定则使用config.py中的默认值）')
    
    args = parser.parse_args()
    results_dir = args.results_dir
    scene_name = args.scene_name
    app_name = args.app_name
    
    try:
        # 创建TagLogic预处理器
        preprocessor = TagLogicPreprocessor(results_dir, scene_name, app_name)
        
        # 处理所有tag_logic_info
        preprocessor.process_all_tag_logic_info()
        
        print(f"✅ TagLogic预处理完成！")
        print(f"📊 处理统计:")
        print(f"   - 已处理的对象数量: {len(preprocessor.processed_object_ids)}")
        print(f"   - 筛选后的tag_logic_info数量: {len(preprocessor.sorted_target_logic_info)}")
        
    except Exception as e:
        print(f"❌ 处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
