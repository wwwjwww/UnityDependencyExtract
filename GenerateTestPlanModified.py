#!/usr/bin/env python3
"""
修改后的GenerateTestPlan.py - 使用sorted_target_logic_info字段

该文件是GenerateTestPlan.py的修改版本，主要变化：
1. 在进行generate_test_plan_conversation函数时，直接查询sorted_target_logic_info字段
2. 使用TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW模板向LLM提供tag相关的prompt信息
3. 不再需要复杂的tag_logic_info处理逻辑，直接使用预处理的结果
"""

import json
import os
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import networkx as nx
import openai
import time
from config import (
    TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW,
    TEST_PLAN_FIRST_REQUEST_TEMPLATE,
    TEST_PLAN_FIRST_REQUEST_SCRIPT_TEMPLATE,
    TEST_PLAN_FIRST_REQUEST_NO_CHILD_TEMPLATE,
    TEST_PLAN_FIRST_REQUEST_NO_CHILD_SCRIPT_TEMPLATE,
    TEST_PLAN_CHILD_REQUEST_TEMPLATE,
    DEFAULT_SCENE_NAME, 
    DEFAULT_APP_NAME,
    basicUrl_gpt35,
    OPENAI_API_KEY
)


class GenerateTestPlanModified:
    """修改后的测试计划生成器"""
    
    def __init__(self, results_dir: str, scene_name: str = None, app_name: str = None, enable_llm: bool = True):
        """
        初始化测试计划生成器
        
        Args:
            results_dir: 结果目录路径
            scene_name: 场景名称
            app_name: 应用名称
            enable_llm: 是否启用LLM API调用（默认True）
        """
        self.results_dir = results_dir
        self.scene_name = scene_name or DEFAULT_SCENE_NAME
        self.app_name = app_name or DEFAULT_APP_NAME
        self.enable_llm = enable_llm
        self.gobj_hierarchy_path = os.path.join(results_dir, "gobj_hierarchy.json")
        self.scene_data_dir = os.path.join(results_dir, "scene_detailed_info")
        self.script_data_dir = os.path.join(results_dir, "script_detailed_info")
        self.scene_meta_dir = os.path.join(results_dir, 'scene_detailed_info', 'mainResults')
        
        # 设置OpenAI API（仅在启用LLM时）
        if self.enable_llm:
            self._setup_openai_api()
        else:
            print("⚠️  LLM API调用已禁用，将使用模拟模式")
            
        # 加载场景元数据（GML文件）
        self.scene_meta_data = self._load_scene_meta_data()
        # 加载gobj_hierarchy.json
        self.gobj_hierarchy = self._load_gobj_hierarchy()
        
        # 加载场景图数据（用于查找Source_Code_File关系）
        self.scene_graphs = self._load_scene_graphs()

        
        # 用于跟踪已经通过sorted_target_logic_info处理过的对象ID
        self.processed_object_ids = set()
    
    def _load_gobj_hierarchy(self) -> List[Dict[str, Any]]:
        """加载gobj_hierarchy.json文件"""
        try:
            with open(self.gobj_hierarchy_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载gobj_hierarchy.json失败: {e}")
            return []
    
    def _setup_openai_api(self):
        """设置OpenAI API配置"""
        try:
            openai.base_url = basicUrl_gpt35
            openai.api_key = OPENAI_API_KEY
            print("✅ OpenAI API配置成功")
        except Exception as e:
            print(f"❌ OpenAI API配置失败: {e}")
            print("请检查config.py中的API配置")
    
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
    
    def _call_llm_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        调用LLM API获取响应
        
        Args:
            prompt: 发送给LLM的提示
            max_retries: 最大重试次数
        
        Returns:
            str: LLM的响应内容，如果失败则返回None
        """
        # 如果LLM API被禁用，使用模拟模式
        if not self.enable_llm:
            return self._generate_simulated_response(prompt)
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 正在调用LLM API (尝试 {attempt + 1}/{max_retries})...")
                
                response = openai.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1
                )
                
                # 提取响应内容
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    print("✅ LLM API调用成功")
                    return content
                else:
                    print("❌ LLM响应为空")
                    return None
                    
            except Exception as e:
                print(f"❌ LLM API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("⏳ 等待30秒后重试...")
                    time.sleep(30)
                else:
                    print("❌ 所有重试都失败了")
                    return None
        
        return None
    
    def _generate_simulated_response(self, prompt: str) -> str:
        """
        生成模拟的LLM响应（用于测试）
        
        Args:
            prompt: 提示内容
        
        Returns:
            str: 模拟的响应内容
        """
        print("🤖 生成模拟LLM响应...")
        
        # 根据提示类型生成不同的模拟响应
        if "first_request" in prompt or "first" in prompt.lower():
            # 第一个请求的模拟响应
            return '''Based on the provided scene information, I can see this is a GameObject in the Unity scene. However, I need more information about the child objects and their attached scripts to generate a comprehensive test plan.

{
  "taskUnit": [
    {
      "actionUnits": [
        {
          "type": "Trigger",
          "source_object_name": "Initial GameObject",
          "method": "Basic interaction",
          "condition": "Single trigger to test basic functionality"
        }
      ]
    }
  ],
  "Need_more_Info": true
}

I need more information about the child GameObjects and their scripts to provide a complete test plan.'''
        
        elif "child_request" in prompt or "children" in prompt.lower():
            # 子对象请求的模拟响应
            return '''Thank you for providing the child object information. Based on the script source code and scene meta data, I can now generate a more comprehensive test plan.

{
  "taskUnit": [
    {
      "actionUnits": [
        {
          "type": "Grab",
          "source_object_name": "Player",
          "source_object_fileID": "12345",
          "target_object_name": "Interactive Object",
          "target_object_fileID": "67890"
        },
        {
          "type": "Trigger",
          "source_object_name": "Interactive Object",
          "method": "OnTriggerEnter",
          "condition": "Trigger once when player enters collision area"
        },
        {
          "type": "Transform",
          "source_object_name": "Interactive Object",
          "target_name": "Move to position (10, 5, 0) for testing"
        }
      ]
    }
  ],
  "Need_more_Info": false
}

This test plan covers the main functionality based on the provided information.'''
        
        else:
            # 默认模拟响应
            return '''I understand you want me to generate a test plan. Here's a basic test plan:

{
  "taskUnit": [
    {
      "actionUnits": [
        {
          "type": "Trigger",
          "source_object_name": "Test Object",
          "method": "Basic test",
          "condition": "Single execution"
        }
      ]
    }
  ],
  "Need_more_Info": false
}'''
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应
        
        Returns:
            Dict: 解析后的响应
        """
        try:
            # 尝试解析JSON响应
            if 'taskUnit' in response:
                # 包含测试计划的响应
                # 尝试解析JSON，如果失败则返回原始字符串
                try:
                    import json
                    parsed_response = json.loads(response)
                    return {
                        'need_more_info': False,
                        'test_plan': parsed_response
                    }
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回原始响应
                    return {
                        'need_more_info': False,
                        'test_plan': response
                    }
            else:
                # 需要更多信息的响应
                return {
                    'need_more_info': True,
                    'test_plan': None
                }
        except Exception as e:
            print(f"⚠️  解析LLM响应失败: {e}")
            return {
                'need_more_info': True,
                'test_plan': None
            }
    
    def _extract_scene_meta_info(self, gobj_id: str, scene_name: str, gobj_script_lis: List[Dict[str, Any]]) -> Optional[str]:
        """
        从场景元数据中提取指定GameObject的信息
        
        Args:
            gobj_id: GameObject的ID
            scene_name: 场景名称
            gobj_script_lis: GameObject的脚本列表
        
        Returns:
            str: 场景元数据信息，如果未找到则返回None
        """
        if scene_name not in self.scene_meta_data:
            return None
        
        scene_graph = self.scene_meta_data[scene_name]
        
        # 查找GameObject的元数据
        MonoBehaviour_lis = []
        gobj_data = self._find_gameobject_in_scene_data(gobj_id, scene_graph)
        
        if gobj_data:
            if gobj_script_lis:
                for i, script_info in enumerate(gobj_script_lis):
                    mono_comp_info = {}
                    mono_comp_info[f"MonoBehaviour_{i}"] = script_info['mono_property']
                    MonoBehaviour_lis.append(mono_comp_info)
                gobj_data['MonoBehaviour'] = MonoBehaviour_lis
            else:
                # 使用enumerate来获取正确的索引
                mono_comp_edges = [(source, target, edge_data) for source, target, edge_data in scene_graph.edges(data=True) 
                                  if edge_data.get('type') == 'Has_Mono_Comp' and source == gobj_id]
                
                for j, (source, target, edge_data) in enumerate(mono_comp_edges):
                    mono_comp_id = target
                    mono_comp_info = {}
                    # 将index j正确写入字段名中
                    mono_comp_info[f"MonoBehaviour_{j}"] = scene_graph.nodes[mono_comp_id].get('properties', {})
                    MonoBehaviour_lis.append(mono_comp_info)
                
                gobj_data['MonoBehaviour'] = MonoBehaviour_lis

        return str(gobj_data)
    
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
    
    def _find_gameobject_by_id(self, gobj_id: str) -> Optional[Dict[str, Any]]:
        """
        根据GameObject ID查找GameObject信息
        
        Args:
            gobj_id: GameObject的ID
        
        Returns:
            Dict: GameObject信息，如果未找到则返回None
        """
        for gobj_info in self.gobj_hierarchy:
            if gobj_info.get('gameobject_id') == gobj_id:
                return gobj_info
        return None
    
    def _save_llm_responses(self, gobj_info: Dict[str, Any], conversation_history: List[Dict[str, Any]], scene_name: str):
        """
        保存LLM响应到文件
        
        Args:
            gobj_info: GameObject信息
            conversation_history: 对话历史
            scene_name: 场景名称
        """
        # 创建响应保存目录
        responses_dir = os.path.join(self.results_dir, 'llm_responses', scene_name)
        os.makedirs(responses_dir, exist_ok=True)
        
        # 保存对话历史
        conversation_file = os.path.join(responses_dir, f"{gobj_info['gameobject_name']}_{gobj_info['gameobject_id']}_conversation.json")
        with open(conversation_file, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=2, ensure_ascii=False)
        
        # 提取并合并测试计划
        merged_test_plan = {
            "taskUnit": [
                {
                    "actionUnits": []
                }
            ]
        }
        
        for msg in conversation_history:
            if msg.get('role') == 'assistant' and msg.get('test_plan'):
                test_plan = msg['test_plan']
                
                # 检查test_plan是字典还是字符串
                if isinstance(test_plan, dict) and 'taskUnit' in test_plan:
                    # test_plan是字典，直接访问
                    for task in test_plan['taskUnit']:
                        if 'actionUnits' in task:
                            merged_test_plan['taskUnit'][0]['actionUnits'].extend(task['actionUnits'])
                elif isinstance(test_plan, str) and 'taskUnit' in test_plan:
                    # test_plan是字符串，尝试解析JSON
                    try:
                        parsed_plan = json.loads(test_plan)
                        if 'taskUnit' in parsed_plan:
                            for task in parsed_plan['taskUnit']:
                                if 'actionUnits' in task:
                                    merged_test_plan['taskUnit'][0]['actionUnits'].extend(task['actionUnits'])
                    except json.JSONDecodeError:
                        print(f"⚠️  无法解析测试计划JSON: {test_plan[:100]}...")
                        continue
        
        # 保存合并后的测试计划
        if merged_test_plan['taskUnit'][0]['actionUnits']:
            test_plan_file = os.path.join(responses_dir, f"{gobj_info['gameobject_name']}_{gobj_info['gameobject_id']}_test_plans.json")
            with open(test_plan_file, 'w', encoding='utf-8') as f:
                json.dump(merged_test_plan, f, indent=2, ensure_ascii=False)
            
            print(f"💾 合并后的测试计划已保存到: {test_plan_file}")
            print(f"   包含 {len(merged_test_plan['taskUnit'][0]['actionUnits'])} 个动作单元")
        
        print(f"💾 对话历史已保存到: {conversation_file}")
    
    def _get_formatted_script_sources_and_meta(self, sorted_target_logic_info: List[Dict[str, Any]], scene_name: str) -> str:
        """
        获取指定GameObject的脚本源代码和场景元数据，格式化输出
        
        Args:
            sorted_target_logic_info: sorted_target_logic_info列表，每个元素包含id、gameobject_name、tag_name等字段
            scene_name: 场景名称
        
        Returns:
            str: 格式化的脚本源代码和场景元数据
        """
        result = ""
        
        for i, item in enumerate(sorted_target_logic_info):
            gobj_id = item.get('id')
            gobj_name = item.get('gameobject_name', 'Unknown')
            tag_name = item.get('tag_name', 'Unknown')
            
            if not gobj_id:
                continue
            
            # 为每个 GameObject 添加分隔符和标题
            if i > 0:
                result += "\n"
            
            result += f"""GameObject ID: "{gobj_id}" GameObject Name: "{gobj_name}" Tag: "{tag_name}":\n"""
            
            # 获取该 GameObject 的脚本源代码
            # 需要在graph中查找Has_Mono_Comp关系，取其target调用_extract_script_source_code
            script_source = ""
            if scene_name in self.scene_meta_data:
                scene_graph = self.scene_meta_data[scene_name]   
                # 查找以gobj_id为source的Has_Mono_Comp关系
                for source, target, edge_data in scene_graph.edges(data=True):
                    if (edge_data.get('type') == 'Has_Mono_Comp' and 
                        source == gobj_id):                        
                        # 找到Has_Mono_Comp关系，使用target调用_extract_script_source_code
                        mono_comp_id = target
                        extracted_script = self._extract_script_source_code(mono_comp_id)
                        if extracted_script:
                            script_source += extracted_script
            
            if script_source:
                result += "[Source code of script files attached]\n"
                result += "'''\n"
                result += script_source
                result += "\n'''\n"
            else:
                result += "[Source code of script files attached]\n"
                result += "// Script source code not found for this GameObject\n"
            
            result += "\n"
            
            # 获取该 GameObject 的场景元数据
            # 使用 _extract_scene_meta_info 方法获取场景元数据
            scene_meta = self._extract_scene_meta_info(gobj_id, scene_name, [])
            if scene_meta:
                result += "[Source code of scene meta file]\n"
                result += "'''\n"
                result += scene_meta
                result += "\n'''\n"
            else:
                result += "[Source code of scene meta file]\n"
                result += "// Scene meta data not found for this GameObject\n"
            
            result += "\n"
        
        return result
    
    def generate_first_request(self, gobj_info: Dict[str, Any], scene_name: str) -> str:
        """
        生成第一个请求（介绍GameObject和场景信息）
        
        Args:
            gobj_info: GameObject信息
            scene_name: 场景名称
        
        Returns:
            str: 第一个请求的内容
        """
        gobj_name = gobj_info['gameobject_name']
        gobj_id = gobj_info['gameobject_id']
        gobj_script_lis = gobj_info['mono_comp_relations']
        child_relations = gobj_info.get('child_relations', [])
        scene_meta = self._extract_scene_meta_info(gobj_id, scene_name, gobj_script_lis)

        # 检查是否有子对象关系
        has_children = len(child_relations) > 0

        if len(gobj_script_lis) > 0:
            # 有脚本的情况
            script_content = ""
            for i, script_info in enumerate(gobj_script_lis):
                target_script_id = script_info['target']
                script_source = self._extract_script_source_code(target_script_id)
                if i == len(gobj_script_lis) - 1:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                else:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                    script_content += "\n'''\n"
                    script_content += f"[Source code of {i+1}th script files attached]\n'''\n"
            
            if has_children:
                # 有子对象，使用需要继续提供子对象信息的模板
                request = TEST_PLAN_FIRST_REQUEST_SCRIPT_TEMPLATE.format(
                    app_name=self.app_name,
                    scene_name=scene_name,
                    gobj_name=gobj_name,
                    gobj_id=gobj_id,
                    scene_meta=scene_meta if scene_meta else "// Scene meta data not found",
                    script_source=script_content
                )
            else:
                # 没有子对象，使用直接生成测试计划的模板
                request = TEST_PLAN_FIRST_REQUEST_NO_CHILD_SCRIPT_TEMPLATE.format(
                    app_name=self.app_name,
                    scene_name=scene_name,
                    gobj_name=gobj_name,
                    gobj_id=gobj_id,
                    scene_meta=scene_meta if scene_meta else "// Scene meta data not found",
                    script_source=script_content
                )
        else:
            # 没有脚本的情况
            if has_children:
                # 有子对象，使用需要继续提供子对象信息的模板
                request = TEST_PLAN_FIRST_REQUEST_TEMPLATE.format(
                    app_name=self.app_name,
                    scene_name=scene_name,
                    gobj_name=gobj_name,
                    gobj_id=gobj_id,
                    scene_meta=scene_meta if scene_meta else "// Scene meta data not found"
                )
            else:
                # 没有子对象，使用直接生成测试计划的模板
                request = TEST_PLAN_FIRST_REQUEST_NO_CHILD_TEMPLATE.format(
                    app_name=self.app_name,
                    scene_name=scene_name,
                    gobj_name=gobj_name,
                    gobj_id=gobj_id,
                    scene_meta=scene_meta if scene_meta else "// Scene meta data not found"
                )
        
        return request
    
    def generate_child_request(self, child_info: Dict[str, Any], child_index: int, scene_name: str, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        生成子对象的请求，并处理sorted_target_logic_info逻辑
        
        Args:
            child_info: 子对象信息
            child_index: 子对象索引
            scene_name: 场景名称
            conversation_history: 对话历史记录（用于处理sorted_target_logic_info）
        
        Returns:
            Dict: 包含请求内容和处理结果的字典
        """
        parent_name = child_info['parent_info']['parent_name']
        child_name = child_info['child_name']
        child_id = child_info['child_id']
        mono_comp_ids = child_info['mono_comp_targets']  # 现在是列表
        
        # 检查是否有 sorted_target_logic_info 需要处理
        # 从gobj_hierarchy中查找该子对象的sorted_target_logic_info
        sorted_target_logic_info = self._find_sorted_target_logic_info(child_id)
        has_sorted_target_logic = sorted_target_logic_info is not None
        
        if has_sorted_target_logic:
            print(f"🔍 检测到子对象 {child_info['child_name']} 有 sorted_target_logic_info，使用 TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW...")
            
            # 处理 sorted_target_logic_info 的逻辑
            if conversation_history is not None:
                conversation_history = self._handle_sorted_target_logic_conversation(
                    child_info, scene_name, conversation_history, sorted_target_logic_info
                )
                print(f"✅ 子对象 {child_info['child_name']} 的 sorted_target_logic_info 处理完成")
            
            # 由于 TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW 已经包含了该子对象的所有信息
            # 包括脚本源代码、场景元数据和tag相关的prompt，所以不需要再生成额外的请求
            return {
                'request': None,
                'has_sorted_target_logic': True,
                'message': f"该子对象的信息已通过 sorted_target_logic_info 完整提供，跳过 generate_child_request"
            }
        
        # 没有 sorted_target_logic_info 的子对象，使用正常的流程
        print(f"📋 子对象 {child_info['child_name']} 没有 sorted_target_logic_info，使用正常的 generate_child_request 流程")
        
        # 获取脚本源代码（处理多个Mono组件）
        script_content = ""
        if len(mono_comp_ids) > 0:
            for i, mono_comp in enumerate(mono_comp_ids):
                target_script_id = mono_comp['target']
                script_source = self._extract_script_source_code(target_script_id) 

                if i == len(mono_comp_ids) - 1:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                else:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                    script_content += "\n'''\n"
                    script_content += f"[Source code of {i+1}th script files attached]\n'''\n"
        
        # 合并所有脚本源代码
        combined_script_source = script_content if script_content else "// Script source code not found"
        
        # 获取子对象的场景元数据
        child_scene_meta = self._find_child_gameobject_info(child_id, scene_name, mono_comp_ids)
        
        # 生成正常的请求
        request = TEST_PLAN_CHILD_REQUEST_TEMPLATE.format(
            child_index=child_index,
            parent_name=parent_name,
            child_name=child_name,
            child_id=child_id,
            script_source=combined_script_source,
            child_scene_meta=child_scene_meta['scene_meta'] if child_scene_meta else "// Scene meta data not found"
        )
        
        return {
            'request': request,
            'has_sorted_target_logic': False,
            'message': "正常生成的子对象请求"
        }
    
    def _find_sorted_target_logic_info(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        查找指定对象的sorted_target_logic_info
        
        Args:
            object_id: 对象ID
        
        Returns:
            Dict: sorted_target_logic_info，如果未找到则返回None
        """
        for gobj_info in self.gobj_hierarchy:
            # 检查主GameObject
            if gobj_info.get('gameobject_id') == object_id:
                return gobj_info.get('sorted_target_logic_info')
            
            # 检查child_mono_comp_info中的子对象
            child_mono_comp_info = gobj_info.get('child_mono_comp_info', [])
            if child_mono_comp_info:
                for child_info in child_mono_comp_info:
                    if child_info.get('child_id') == object_id:
                        return child_info.get('sorted_target_logic_info')
        return None
    
    def _handle_sorted_target_logic_conversation(self, child_info: Dict[str, Any], scene_name: str, conversation_history: List[Dict[str, Any]], sorted_target_logic_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        处理 sorted_target_logic_info 相关的对话
        
        Args:
            child_info: 子对象信息
            scene_name: 场景名称
            conversation_history: 对话历史记录
            sorted_target_logic_info: 排序后的目标逻辑信息
        
        Returns:
            List[Dict]: 更新后的对话历史记录
        """
        child_name = child_info['child_name']
        child_id = child_info['child_id']
        mono_comp_ids = child_info['mono_comp_targets']
        
        print(f"🔄 开始处理子对象 {child_name} 的 sorted_target_logic_info...")
        
        # 将当前子对象ID添加到已处理集合中
        self.processed_object_ids.add(child_id)
        
        # 获取脚本源代码
        script_content = ""
        if len(mono_comp_ids) > 0:
            for i, mono_comp in enumerate(mono_comp_ids):
                target_script_id = mono_comp['target']
                script_source = self._extract_script_source_code(target_script_id) 
                if i == len(mono_comp_ids) - 1:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                else:
                    script_content += script_source or f"// Script source code for {target_script_id}"
                    script_content += "\n'''\n"
                    script_content += f"[Source code {i}th of script files ({target_script_id}) attached]\n'''\n"
        
        combined_script_source = script_content if script_content else "// Script source code not found"
        
        # 获取子对象的场景元数据
        child_scene_meta = self._find_child_gameobject_info(child_id, scene_name, mono_comp_ids)
        
        # 从sorted_target_logic_info中获取需要的GameObject ID列表
        # sorted_target_logic_info是一个列表，每个元素包含id、gameobject_name、tag_name等字段
        needed_gameobject_ids = []
        if isinstance(sorted_target_logic_info, list):
            needed_gameobject_ids = [item.get('id') for item in sorted_target_logic_info if item.get('id')]
        
        # 获取这些GameObject的脚本源代码和场景元数据
        script_sources_and_meta = self._get_formatted_script_sources_and_meta(sorted_target_logic_info, scene_name)
        
        # 使用 TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW 生成请求
        request = TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW.format(
            child_name=child_name,
            child_id=child_id,
            parent_name=child_info['parent_info']['parent_name'],
            combined_script_source=combined_script_source,
            child_scene_meta=child_scene_meta['scene_meta'] if child_scene_meta else "// Scene meta data not found",
            needed_gameobject_ids=needed_gameobject_ids,
            script_sources_and_meta=script_sources_and_meta
        )
        
        # 发送请求到对话历史
        conversation_history.append({
            'role': 'user',
            'content': request,
            'request_type': 'sorted_target_logic_request',
            'child_info': child_info,
            'sorted_target_logic_info': sorted_target_logic_info,
            'timestamp': datetime.now().isoformat()
        })
        
        # 调用LLM API获取响应
        tag_response = self._call_llm_api(request)
        
        if tag_response:
            # 解析LLM响应
            parsed_response = self._parse_llm_response(tag_response)
            conversation_history.append({
                'role': 'assistant',
                'content': tag_response,
                'response_type': 'test_plan_response',
                'need_more_info': parsed_response['need_more_info'],
                'test_plan': parsed_response['test_plan'],
                'timestamp': datetime.now().isoformat()
            })
            
            if parsed_response['need_more_info']:
                print(f"📋 LLM仍然需要更多信息")
            else:
                print(f"✅ LLM已获得足够信息，sorted_target_logic_info 处理完成")
        else:
            print(f"❌ 获取 sorted_target_logic_info 的LLM响应失败")
            conversation_history.append({
                'role': 'assistant',
                'content': f"Error: Failed to get LLM response for sorted_target_logic_info",
                'response_type': 'error',
                'need_more_info': True,
                'timestamp': datetime.now().isoformat()
            })
        
        return conversation_history
    
    def generate_test_plan_conversation(self, gobj_info: Dict[str, Any], scene_name: str) -> List[Dict[str, Any]]:
        """
        为指定的GameObject生成完整的测试计划对话
        
        Args:
            gobj_info: GameObject信息
            scene_name: 场景名称
        
        Returns:
            List[Dict]: 对话历史记录
        """
        conversation_history = []
        
        # 生成第一个请求
        first_request = self.generate_first_request(gobj_info, scene_name)
        conversation_history.append({
            'role': 'user',
            'content': first_request,
            'request_type': 'first_request',
            'timestamp': datetime.now().isoformat()
        })
        
        # 调用LLM API获取第一个响应
        print(f"🤖 正在为GameObject '{gobj_info['gameobject_name']}' 生成第一个测试计划...")
        first_response = self._call_llm_api(first_request)
        
        if first_response:
            # 检查是否有子对象关系
            child_relations = gobj_info.get('child_relations', [])
            has_children = len(child_relations) > 0
            
            if has_children:
                # 有子对象，直接记录first_response结果，不需要解析need_more_info
                conversation_history.append({
                    'role': 'assistant',
                    'content': first_response,
                    'response_type': 'test_plan_response',
                    'need_more_info':  True,  # 有子对象时总是需要更多信息
                    'test_plan': None,  # 不解析测试计划
                    'timestamp': datetime.now().isoformat()
                })
                
                print("📋 有子对象，继续提供子对象信息...")

                # 处理子对象的Mono组件信息
                conversation_history = self._handle_child_conversation(
                    gobj_info, scene_name, conversation_history
                )
            else:
                # 没有子对象，需要解析LLM响应判断need_more_info
                parsed_response = self._parse_llm_response(first_response)
                conversation_history.append({
                    'role': 'assistant',
                    'content': first_response,
                    'response_type': 'test_plan_response',
                    'need_more_info': parsed_response['need_more_info'],
                    'test_plan': parsed_response['test_plan'],
                    'timestamp': datetime.now().isoformat()
                })
                
                if parsed_response['need_more_info']:
                    print("📋 LLM需要更多信息，但该GameObject没有子对象，无法提供更多信息")
                else:
                    print("✅ LLM已获得足够信息，测试计划生成完成")
        else:
            print(f"❌ 获取GameObject '{gobj_info['gameobject_name']}' 的LLM响应失败")
            # 添加错误响应到对话历史
            conversation_history.append({
                'role': 'assistant',
                'content': f"Error: Failed to get LLM response for GameObject {gobj_info['gameobject_name']}",
                'response_type': 'error',
                'need_more_info': True,
                'timestamp': datetime.now().isoformat()
            })
        
        return conversation_history
    
    def _handle_child_conversation(self, gobj_info: Dict[str, Any], scene_name: str, conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理子对象的对话
        
        Args:
            gobj_info: GameObject信息
            scene_name: 场景名称
            conversation_history: 对话历史记录
        
        Returns:
            List[Dict]: 更新后的对话历史记录
        """
        # 处理子对象的Mono组件信息
        child_mono_comp_info = gobj_info.get('child_mono_comp_info', [])
        
        # 从对话历史中提取已经通过sorted_target_logic_info处理过的对象ID
        processed_object_ids = set()
        for msg in conversation_history:
            if msg.get('response_type') == 'processed_objects_info' and 'processed_object_ids' in msg:
                processed_object_ids.update(msg['processed_object_ids'])
        
        if processed_object_ids:
            print(f"🔍 发现已通过sorted_target_logic_info处理过的对象ID: {list(processed_object_ids)}")
        
        for i, child_info in enumerate(child_mono_comp_info, 1):
            child_id = child_info['child_id']
            child_name = child_info['child_name']
            
            # 检查该子对象是否已经在sorted_target_logic_info中被处理过
            if child_id in processed_object_ids:
                print(f"⏭️  跳过子对象 {child_name} (ID: {child_id})，已在sorted_target_logic_info中处理过")
                conversation_history.append({
                    'role': 'system',
                    'content': f"跳过子对象 {child_name} (ID: {child_id})，已在sorted_target_logic_info中处理过",
                    'response_type': 'skipped_object_info',
                    'skipped_object_id': child_id,
                    'skipped_object_name': child_name,
                    'timestamp': datetime.now().isoformat()
                })
                continue
            
            print(f"📤 正在提供第{i}个子对象信息: {child_name}")
            
            # 生成子对象请求，并处理sorted_target_logic_info逻辑
            child_request_result = self.generate_child_request(child_info, i, scene_name, conversation_history)
            
            if child_request_result['has_sorted_target_logic']:
                # 如果有sorted_target_logic_info，已经通过generate_child_request处理完成
                print(f"📋 {child_request_result['message']}")
                continue
            
            # 没有sorted_target_logic_info的子对象，使用正常的流程
            child_request = child_request_result['request']
            print(f"📋 {child_request_result['message']}")
            
            conversation_history.append({
                'role': 'user',
                'content': child_request,
                'request_type': 'child_request',
                'child_index': i,
                'child_info': child_info,
                'timestamp': datetime.now().isoformat()
            })
            
            # 调用LLM API获取子对象响应
            child_response = self._call_llm_api(child_request)
            
            if child_response:
                # 解析LLM响应
                parsed_child_response = self._parse_llm_response(child_response)
                conversation_history.append({
                    'role': 'assistant',
                    'content': child_response,
                    'response_type': 'test_plan_response',
                    'need_more_info': parsed_child_response['need_more_info'],
                    'test_plan': parsed_child_response['test_plan'],
                    'timestamp': datetime.now().isoformat()
                })
                
                # 如果LLM仍然需要更多信息，继续下一个子对象
                if parsed_child_response['need_more_info'] and i < len(child_mono_comp_info):
                    print(f"📋 LLM仍然需要更多信息，继续提供下一个子对象...")
                    continue
                elif not parsed_child_response['need_more_info']:
                    print(f"✅ LLM已获得足够信息，测试计划生成完成")
                    break
                else:
                    print(f"✅ 已提供所有子对象信息，测试计划生成完成")
                    break
            else:
                print(f"❌ 获取子对象 {child_name} 的LLM响应失败")
                # 添加错误响应到对话历史
                conversation_history.append({
                    'role': 'assistant',
                    'content': f"Error: Failed to get LLM response for child object {child_name}",
                    'return': 'error',
                    'timestamp': datetime.now().isoformat()
                })
        
        return conversation_history
    
    def generate_all_test_plans(self, scene_name: str = None) -> Dict[str, Any]:
        """
        为所有GameObject生成测试计划对话
        
        Args:
            scene_name: 场景名称，如果为None则使用第一个可用的场景
        
        Returns:
            Dict: 包含所有测试计划对话的结果
        """
        if scene_name is None:
            scene_name = self.scene_name
        
        print(f"🚀 开始为场景 '{scene_name}' 的所有GameObject生成测试计划...")
        
        all_test_plans = {
            'scene_name': scene_name,
            'generated_at': datetime.now().isoformat(),
            'gameobjects': []
        }
        
        # 遍历所有GameObject
        for gobj_info in self.gobj_hierarchy:
            gobj_id = gobj_info.get('gameobject_id')
            gobj_name = gobj_info.get('gameobject_name')
            
            print(f"\n📋 正在处理GameObject: {gobj_name} (ID: {gobj_id})")
            
            # 生成测试计划对话
            conversation_history = self.generate_test_plan_conversation(gobj_info, scene_name)

            self._save_llm_responses(gobj_info, conversation_history, scene_name)
            
            # 统计对话信息
            total_requests = len([msg for msg in conversation_history if msg['role'] == 'user'])
            has_children = len(gobj_info.get('child_relations', [])) > 0
            has_children_with_mono = any(
                child.get('mono_comp_targets') 
                for child in gobj_info.get('child_mono_comp_info', [])
            )
            
            # 添加到结果中
            gobj_plan = {
                'gameobject_id': gobj_id,
                'gameobject_name': gobj_name,
                'gameobject_type': gobj_info.get('gameobject_type', 'Unknown'),
                'total_requests': total_requests,
                'has_children': has_children,
                'has_children_with_mono': has_children_with_mono,
                'conversation_history': conversation_history
            }
            
            all_test_plans['gameobjects'].append(gobj_plan)
            
            print(f"✅ GameObject {gobj_name} 的测试计划生成完成，共 {total_requests} 个请求")
        
        print(f"\n🎉 所有GameObject的测试计划生成完成！")
        print(f"📊 统计信息:")
        print(f"   - 总GameObject数量: {len(all_test_plans['gameobjects'])}")
        print(f"   - 总请求数量: {sum(gobj['total_requests'] for gobj in all_test_plans['gameobjects'])}")
        
        return all_test_plans
    
    def print_test_plans_summary(self, test_plans: Dict[str, Any]):
        """
        打印测试计划摘要
        
        Args:
            test_plans: 测试计划结果
        """
        print(f"\n📋 测试计划摘要")
        print(f"场景名称: {test_plans['scene_name']}")
        print(f"生成时间: {test_plans['generated_at']}")
        print(f"GameObject数量: {len(test_plans['gameobjects'])}")
        print()
        
        for i, gobj_plan in enumerate(test_plans['gameobjects'], 1):
            print(f"{i}. {gobj_plan['gameobject_name']} (ID: {gobj_plan['gameobject_id']})")
            print(f"   类型: {gobj_plan['gameobject_type']}")
            print(f"   对话轮数: {gobj_plan['total_requests']}")
            print(f"   有Mono组件的子对象: {'是' if gobj_plan['has_children_with_mono'] else '否'}")
            
            # 统计对话类型和测试计划
            request_types = {}
            test_plans_count = 0
            need_more_info_count = 0
            
            for msg in gobj_plan['conversation_history']:
                if msg['role'] == 'user':
                    req_type = msg.get('request_type', 'unknown')
                    request_types[req_type] = request_types.get(req_type, 0) + 1
                elif msg['role'] == 'assistant':
                    if msg.get('test_plan'):
                        test_plans_count += 1
                    if msg.get('need_more_info'):
                        need_more_info_count += 1
            
            print(f"   请求类型分布:")
            for req_type, count in request_types.items():
                print(f"     - {req_type}: {count}")
            
            print(f"   生成的测试计划数量: {test_plans_count}")
            print(f"   需要更多信息的次数: {need_more_info_count}")
            
            # 显示第一个测试计划（如果有的话）
            for msg in gobj_plan['conversation_history']:
                 if msg.get('role') == 'assistant' and msg.get('test_plan'):
                     print(f"   第一个测试计划:")
                     test_plan = msg['test_plan']
                     
                     # 检查test_plan是字典还是字符串
                     if isinstance(test_plan, dict) and 'taskUnit' in test_plan:
                         # test_plan是字典，直接访问
                         task_units = test_plan['taskUnit']
                         for j, task in enumerate(task_units):
                             if 'actionUnits' in task:
                                 actions = task['actionUnits']
                                 print(f"     任务 {j+1}: {len(actions)} 个动作")
                                 for k, action in enumerate(actions[:3]):  # 只显示前3个动作
                                     action_type = action.get('type', 'Unknown')
                                     print(f"       - 动作 {k+1}: {action_type}")
                                 if len(actions) > 3:
                                     print(f"       ... 还有 {len(actions) - 3} 个动作")
                     elif isinstance(test_plan, str) and 'taskUnit' in test_plan:
                         # test_plan是字符串，尝试解析JSON
                         try:
                             import json
                             parsed_plan = json.loads(test_plan)
                             if 'taskUnit' in parsed_plan:
                                 task_units = parsed_plan['taskUnit']
                                 for j, task in enumerate(task_units):
                                     if 'actionUnits' in task:
                                         actions = task['actionUnits']
                                         print(f"     任务 {j+1}: {len(actions)} 个动作")
                                         for k, action in enumerate(actions[:3]):  # 只显示前3个动作
                                             action_type = action.get('type', 'Unknown')
                                             print(f"       - 动作 {k+1}: {action_type}")
                                         if len(actions) > 3:
                                             print(f"       ... 还有 {len(actions) - 3} 个动作")
                         except json.JSONDecodeError:
                             print(f"     JSON解析失败，显示原始内容:")
                             print(f"     {test_plan[:200]}...")
                     else:
                         print(f"     测试计划格式未知: {type(test_plan)}")
                         if isinstance(test_plan, str):
                             print(f"     {test_plan[:200]}...")
                     break


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="生成Unity GameObject的测试计划对话（使用sorted_target_logic_info）")
    parser.add_argument('-r', '--results-dir', required=True, 
                       help='结果目录路径，包含gobj_hierarchy.json和场景数据')
    parser.add_argument('-s', '--scene-name', 
                       help='场景名称（可选，如果不指定则使用config.py中的默认值）')
    parser.add_argument('-a', '--app-name', 
                       help='应用名称（可选，如果不指定则使用config.py中的默认值）')
    parser.add_argument('--disable-llm', action='store_true',
                       help='禁用LLM API调用，使用模拟模式（用于测试）')
    
    args = parser.parse_args()
    results_dir = args.results_dir
    scene_name = args.scene_name
    app_name = args.app_name
    enable_llm = not args.disable_llm
    
    try:
        # 创建测试计划生成器
        generator = GenerateTestPlanModified(results_dir, scene_name, app_name, enable_llm)
        
        # 生成所有测试计划
        test_plans = generator.generate_all_test_plans(generator.scene_name)
        
        # 打印摘要
        generator.print_test_plans_summary(test_plans)
        
        # 保存结果到文件
        output_file = os.path.join(results_dir, f"test_plan_conversations_sorted_{generator.scene_name}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_plans, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 测试计划对话已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 生成测试计划过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
