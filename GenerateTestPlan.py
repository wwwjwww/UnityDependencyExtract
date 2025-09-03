import os
import json
import argparse
from typing import List, Dict, Any, Optional
import re
from datetime import datetime
import networkx as nx
import openai
import time
from config import (
    TEST_PLAN_FIRST_REQUEST_TEMPLATE, 
    TEST_PLAN_FIRST_REQUEST_SCRIPT_TEMPLATE,
    TEST_PLAN_CHILD_REQUEST_TEMPLATE, 
    TEST_PLAN_FIRST_REQUEST_NO_CHILD_TEMPLATE,
    TEST_PLAN_FIRST_REQUEST_NO_CHILD_SCRIPT_TEMPLATE,
    TAG_TEST_REQUEST_TEMPLATE,
    TAG_LOGIC_CHILD_REQUEST_TEMPLATE,
    DEFAULT_SCENE_NAME, 
    DEFAULT_APP_NAME, 
    OPENAI_API_KEY, 
    basicUrl_gpt35
)

class TestPlanGenerator:
    """
    测试计划生成器，通过多轮对话与LLM交互生成针对GameObject的测试计划
    """
    
    def __init__(self, results_dir: str, scene_name: str = None, app_name: str = None, enable_llm: bool = True):
        """
        初始化测试计划生成器
        
        Args:
            results_dir: 结果目录路径
            scene_name: 场景名称（可选）
            app_name: 应用名称（可选）
            enable_llm: 是否启用LLM API调用（默认True）
        """
        self.results_dir = results_dir
        self.scene_name = scene_name or DEFAULT_SCENE_NAME
        self.app_name = app_name or DEFAULT_APP_NAME
        self.enable_llm = enable_llm
        self.gobj_hierarchy_file = os.path.join(results_dir, 'gobj_hierarchy.json')
        self.scene_meta_dir = os.path.join(results_dir, 'scene_detailed_info', 'mainResults')
        self.script_dir = os.path.join(results_dir, 'script_detailed_info', 'mainResults')
        
        # 设置OpenAI API（仅在启用LLM时）
        if self.enable_llm:
            self._setup_openai_api()
        else:
            print("⚠️  LLM API调用已禁用，将使用模拟模式")
        
        # 加载场景元数据（GML文件）
        self.scene_meta_data = self._load_scene_meta_data()
        
        # 加载脚本数据
        self.script_data = self._load_script_data()
        
        # 加载GameObject层次结构
        self.gobj_hierarchy = self._load_gobj_hierarchy()
        
        # 加载场景图数据（用于查找Source_Code_File关系）
        self.scene_graphs = self._load_scene_graphs()
    
    def _setup_openai_api(self):
        """设置OpenAI API配置"""
        try:
            openai.base_url = basicUrl_gpt35
            openai.api_key = OPENAI_API_KEY
            print("✅ OpenAI API配置成功")
        except Exception as e:
            print(f"❌ OpenAI API配置失败: {e}")
            print("请检查config.py中的API配置")
    
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
        解析LLM的响应，提取测试计划和Need_more_Info标志
        
        Args:
            response: LLM的响应内容
        
        Returns:
            Dict: 解析后的测试计划信息
        """
        try:
            # 尝试提取JSON格式的测试计划
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                test_plan = json.loads(json_str)
                return {
                    'test_plan': test_plan,
                    'need_more_info': test_plan.get('Need_more_Info', False),
                    'raw_response': response
                }
            else:
                # 如果没有找到JSON，尝试手动解析
                need_more_info = 'Need_more_Info' in response and 'true' in response.lower()
                return {
                    'test_plan': None,
                    'need_more_info': need_more_info,
                    'raw_response': response
                }
        except Exception as e:
            print(f"❌ 解析LLM响应失败: {e}")
            # 返回默认值
            return {
                'test_plan': None,
                'need_more_info': True,  # 解析失败时默认需要更多信息
                'raw_response': response
            }
    
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
    
    def _load_script_data(self) -> Dict[str, Any]:
        """加载脚本数据"""
        script_data = {}
        
        if not os.path.exists(self.script_dir):
            print(f"警告: 脚本数据目录不存在: {self.script_dir}")
            return script_data
        
        # 查找脚本文件
        for file in os.listdir(self.script_dir):
            if file.endswith('.json') and not file.endswith('_log.json') and not file.endswith('.log'):
                script_file_path = os.path.join(self.script_dir, file)
                try:
                    with open(script_file_path, 'r', encoding='utf-8') as f:
                        script_info = json.load(f)
                        script_name = file.replace('.json', '')
                        script_data[script_name] = script_info
                except Exception as e:
                    print(f"加载脚本文件 {file} 失败: {e}")
        
        print(f"已加载 {len(script_data)} 个脚本文件")
        return script_data
    
    def _load_gobj_hierarchy(self) -> List[Dict[str, Any]]:
        """加载GameObject层次结构"""
        if not os.path.exists(self.gobj_hierarchy_file):
            print(f"错误: GameObject层次结构文件不存在: {self.gobj_hierarchy_file}")
            print("请先运行 TraverseSceneHierarchy.py 生成 gobj_hierarchy.json 文件")
            return []
        
        try:
            with open(self.gobj_hierarchy_file, 'r', encoding='utf-8') as f:
                gobj_hierarchy = json.load(f)
                print(f"已加载GameObject层次结构: {len(gobj_hierarchy)} 个对象")
                return gobj_hierarchy
        except Exception as e:
            print(f"加载GameObject层次结构失败: {e}")
            return []
    

    
    def _get_tag_logic_prompt(self, gobj_info: Dict[str, Any], child_info: Dict[str, Any] = None) -> str:
        """
        生成 tag_logic_info 相关的特殊 prompt
        
        Args:
            gobj_info: GameObject信息
            child_info: 子对象信息（如果是子对象请求）
        
        Returns:
            str: 特殊的 prompt 内容
        """
        target_info = child_info if child_info else gobj_info
        tag_logic_info = target_info.get('tag_logic_info', [])
        
        if not tag_logic_info or len(tag_logic_info) == 0:
            return ""
        
        # 直接使用 tag_logic_info 中的信息，不需要再从 gobj_tag.json 中查找
        # 构建 tag 信息字典：tag名称 -> GameObject ID列表
        tag_dict = {}
        for tag_info in tag_logic_info:
            tag_name = tag_info.get('tag_name')
            gobj_id = tag_info.get('id')
            if tag_name and gobj_id:
                if tag_name not in tag_dict:
                    tag_dict[tag_name] = []
                tag_dict[tag_name].append(gobj_id)
        
        if not tag_dict:
            return ""
        
        # 构建 prompt
        prompt = f"""These are the gameobjects that may have corresponding tags with .CompareTag() in the source script. We will show the corresponding gameobject ID with tags below. Please choose the gameobjects from below that has the correct tag to test the script and only answer with the list of \"gameobject_id\". For instance: ["12345"].\n"""
        prompt += "[dict of tags with gameobject IDs]\n"
        prompt += json.dumps(tag_dict, indent=2)
        
        return prompt
    

    
    def _process_tag_logic_response(self, response: str, gobj_info: Dict[str, Any]) -> List[str]:
        """
        处理 LLM 对 tag_logic_info 的响应，提取需要的 GameObject ID 列表
        
        Args:
            response: LLM 的响应内容
            gobj_info: GameObject信息
        
        Returns:
            List[str]: 需要的 GameObject ID 列表
        """
        try:
            # 尝试从响应中提取 GameObject ID 列表
            # 可能的格式：["id1", "id2", "id3"] 或者 id1, id2, id3 等
            import re
            
            # 尝试匹配 JSON 格式的列表
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                try:
                    id_list = json.loads(json_match.group(0))
                    if isinstance(id_list, list):
                        return [str(id) for id in id_list]
                except:
                    pass
            
            # 尝试匹配引号包围的 ID
            quoted_ids = re.findall(r'"([^"]+)"', response)
            if quoted_ids:
                return quoted_ids
            
            # 尝试匹配数字 ID
            numeric_ids = re.findall(r'\b\d+\b', response)
            if numeric_ids:
                return numeric_ids
            
            print(f"⚠️  无法从LLM响应中解析GameObject ID列表: {response}")
            return []
            
        except Exception as e:
            print(f"❌ 处理 tag_logic_info 响应失败: {e}")
            return []
    

    
    def _get_last_generated_test_plans(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        从对话历史中提取最后生成的测试计划
        
        Args:
            conversation_history: 对话历史记录
        
        Returns:
            str: 最后生成的测试计划内容，如果没有则返回空字符串
        """
        # 从后往前查找最后生成的测试计划
        for msg in reversed(conversation_history):
            if (msg.get('role') == 'assistant' and 
                msg.get('test_plan') and 
                isinstance(msg['test_plan'], dict)):
                
                test_plan = msg['test_plan']
                # 将测试计划格式化为易读的字符串
                return test_plan
        
        return "// No previous test plan available"
    
    def _get_formatted_script_sources_and_meta(self, gameobject_ids: List[str], scene_name: str) -> str:
        """
        根据 GameObject ID 列表获取格式化的脚本源代码和场景元数据
        
        Args:
            gameobject_ids: GameObject ID 列表
            scene_name: 场景名称
        
        Returns:
            str: 格式化的脚本源代码和场景元数据内容
        """
        if not gameobject_ids:
            return "// No GameObject IDs provided"
        
        formatted_content = ""
        
        # 从 gobj_hierarchy 中获取 GameObject 的名称信息
        gobj_hierarchy = self._load_gobj_hierarchy()
        gobj_name_map = {}
        
        # 构建 GameObject ID 到名称的映射
        # 首先从 tag_logic_info 中查找 id 和 gameobject_name 的映射
        for gobj_info in gobj_hierarchy:
            # 检查是否有 tag_logic_info
            tag_logic_info = gobj_info.get('tag_logic_info', [])
            if tag_logic_info:
                for tag_info in tag_logic_info:
                    print(f"tag_info: {tag_info}")
                    tag_id = tag_info.get('id')
                    if tag_id:
                        gobj_name = gobj_info.get('gameobject_name', 'Unknown')
                        gobj_name_map[tag_id] = gobj_name
            
            # 检查 child_mono_comp_info 列表中的 tag_logic_info
            child_mono_comp_info = gobj_info.get('child_mono_comp_info', [])
            if child_mono_comp_info:
                for child_info in child_mono_comp_info:
                    # 检查子对象是否有 tag_logic_info
                    child_tag_logic_info = child_info.get('tag_logic_info', [])
                    if child_tag_logic_info:
                        for child_tag_info in child_tag_logic_info:
                            child_tag_id = child_tag_info.get('id')
                            if child_tag_id:
                                # 使用子对象的名称，如果没有则使用父对象的名称
                                child_name = child_tag_info.get('gameobject_name', 'Unknown')
                                gobj_name_map[child_tag_id] = child_name
            
            # 同时也保留原来的 gameobject_id 到名称的映射作为备用
            gobj_id = gobj_info.get('gameobject_id')
            gobj_name = gobj_info.get('gameobject_name', 'Unknown')
            if gobj_id:
                gobj_name_map[gobj_id] = gobj_name
        
        
        for i, gobj_id in enumerate(gameobject_ids):
            # 为每个 GameObject 添加分隔符和标题
            if i > 0:
                formatted_content += "\n"
            
            # 获取 GameObject 名称，如果找不到则使用 "Unknown"
            gobj_name = gobj_name_map.get(gobj_id, 'Unknown')
            formatted_content += f"GameObject ID: {gobj_id} GameObject Name: {gobj_name}:\n"
            
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
                        if self._extract_script_source_code(mono_comp_id):
                            script_source += self._extract_script_source_code(mono_comp_id)
            
            if script_source:
                formatted_content += "[Source code of script files attached]\n"
                formatted_content += "'''\n"
                formatted_content += script_source
                formatted_content += "\n'''\n"
            else:
                formatted_content += "[Source code of script files attached]\n"
                formatted_content += "// Script source code not found for this GameObject\n"
            
            formatted_content += "\n"
            
            # 获取该 GameObject 的场景元数据
            # 注意：这里需要修复 _find_gameobject_info 函数调用
            # 暂时使用 _extract_scene_meta_info 作为替代
            scene_meta = self._extract_scene_meta_info(gobj_id, scene_name, [])
            if scene_meta:
                formatted_content += "[Source code of scene meta file]\n"
                formatted_content += "'''\n"
                formatted_content += scene_meta
                formatted_content += "\n'''\n"
            else:
                formatted_content += "[Source code of scene meta file]\n"
                formatted_content += "// Scene meta data not found for this GameObject\n"
            
            formatted_content += "\n"
        
        return formatted_content
    
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
    
    def _extract_scene_meta_info(self, gobj_id: str, scene_name: str, gobj_script_lis: List[Dict[str, Any]]) -> Optional[str]:
        """
        从场景元数据中提取指定GameObject的信息
        
        Args:
            gobj_id: GameObject的ID
            scene_name: 场景名称
        
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
            for script_file in os.listdir(self.script_dir):
                if script_file == script_filename or script_file.endswith('.cs'):
                    script_file_path = os.path.join(self.script_dir, script_file)
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
                    script_content += script_source
                else:
                    script_content += script_source
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
        生成子对象的请求，并处理tag_logic_info逻辑
        
        Args:
            child_info: 子对象信息
            child_index: 子对象索引
            scene_name: 场景名称
            conversation_history: 对话历史记录（用于处理tag_logic_info）
        
        Returns:
            Dict: 包含请求内容和处理结果的字典
        """
        parent_name = child_info['parent_info']['parent_name']
        child_name = child_info['child_name']
        child_id = child_info['child_id']
        mono_comp_ids = child_info['mono_comp_targets']  # 现在是列表
        
        # 检查是否有 tag_logic_info 需要处理
        tag_logic_info = child_info.get('tag_logic_info', [])
        has_tag_logic = tag_logic_info and len(tag_logic_info) > 0
        
        if has_tag_logic:
            print(f"🔍 检测到子对象 {child_info['child_name']} 有 tag_logic_info，需要先处理 tag 相关的请求...")
            
            # 处理 tag_logic_info 的循环逻辑
            if conversation_history is not None:
                conversation_history = self._handle_tag_logic_conversation(
                    gobj_info=None,  # 这里传入None，因为我们是处理子对象
                    scene_name=scene_name,
                    conversation_history=conversation_history,
                    child_info=child_info  # 传入子对象信息
                )
                print(f"✅ 子对象 {child_info['child_name']} 的 tag_logic_info 处理完成")
            
            # 由于 TAG_LOGIC_CHILD_REQUEST_TEMPLATE 已经包含了该子对象的所有信息
            # 包括脚本源代码、场景元数据和tag_logic_prompt，所以不需要再生成额外的请求
            return {
                'request': None,
                'has_tag_logic': True,
                'message': f"该子对象的信息已通过 tag_logic_request 完整提供，跳过 generate_child_request"
            }
        
        # 没有 tag_logic_info 的子对象，使用正常的流程
        print(f"📋 子对象 {child_info['child_name']} 没有 tag_logic_info，使用正常的 generate_child_request 流程")
        
        # 获取脚本源代码（处理多个Mono组件）
        script_content = ""
        if len(mono_comp_ids) > 0:
            for i, mono_comp in enumerate(mono_comp_ids):
                target_script_id = mono_comp['target']
                script_source = self._extract_script_source_code(target_script_id) 

                if i == len(mono_comp_ids) - 1:
                    script_content += script_source
                else:
                    script_content += script_source
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
            'has_tag_logic': False,
            'message': "正常生成的子对象请求"
        }
    
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
    
    def generate_all_test_plans(self, scene_name: str = None) -> Dict[str, Any]:
        """
        为所有GameObject生成测试计划对话
        
        Args:
            scene_name: 场景名称，如果为None则使用第一个可用的场景
        
        Returns:
            Dict: 包含所有测试计划对话的结果
        """
        if not self.gobj_hierarchy:
            print("错误: 没有可用的GameObject层次结构数据")
            return {}
        
        # 如果没有指定场景名称，使用第一个可用的场景
        if scene_name is None:
            available_scenes = list(self.scene_meta_data.keys())
            if available_scenes:
                scene_name = available_scenes[0]
                print(f"使用默认场景: {scene_name}")
            else:
                print("错误: 没有可用的场景数据")
                return {}
        
        print(f"开始为场景 {scene_name} 生成测试计划...")
        
        all_test_plans = {
            'scene_name': scene_name,
            'generated_at': datetime.now().isoformat(),
            'gameobjects': []
        }
        
        for gobj_info in self.gobj_hierarchy:
            print(f"正在处理GameObject: {gobj_info['gameobject_name']} (ID: {gobj_info['gameobject_id']})")
            
            # 生成测试计划对话
            conversation = self.generate_test_plan_conversation(gobj_info, scene_name)
            
            # 保存LLM响应
            self._save_llm_responses(gobj_info, conversation, scene_name)
            
            test_plan_result = {
                'gameobject_id': gobj_info['gameobject_id'],
                'gameobject_name': gobj_info['gameobject_name'],
                'gameobject_type': gobj_info['gameobject_type'],
                'conversation_history': conversation,
                'total_requests': len(conversation),
                'has_children_with_mono': len(gobj_info.get('child_mono_comp_info', [])) > 0
            }
            
            all_test_plans['gameobjects'].append(test_plan_result)
        
        # 保存结果到文件
        output_file = os.path.join(self.results_dir, f'test_plan_conversations_{scene_name}.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_test_plans, f, indent=2, ensure_ascii=False)
        
        print(f"测试计划对话已保存到: {output_file}")
        print(f"总共生成了 {len(all_test_plans['gameobjects'])} 个GameObject的测试计划对话")
        
        return all_test_plans
    
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
        
        # 提取并保存测试计划
        test_plans = []
        for msg in conversation_history:
            if msg.get('role') == 'assistant' and msg.get('test_plan'):
                test_plans.append({
                    'timestamp': msg['timestamp'],
                    'test_plan': msg['test_plan']
                })
        
        if test_plans:
            test_plan_file = os.path.join(responses_dir, f"{gobj_info['gameobject_name']}_{gobj_info['gameobject_id']}_test_plans.json")
            with open(test_plan_file, 'w', encoding='utf-8') as f:
                json.dump(test_plans, f, indent=2, ensure_ascii=False)
            
            print(f"💾 测试计划已保存到: {test_plan_file}")
        
        print(f"💾 对话历史已保存到: {conversation_file}")
    
    def print_conversation_summary(self, test_plans: Dict[str, Any]):
        """
        打印测试计划对话的摘要信息
        
        Args:
            test_plans: 测试计划结果
        """
        print("\n" + "=" * 80)
        print("测试计划对话摘要")
        print("=" * 80)
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
                    if 'taskUnit' in test_plan:
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
                    break
            
    def _handle_tag_logic_conversation(self, gobj_info: Dict[str, Any], scene_name: str, conversation_history: List[Dict[str, Any]], child_info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        处理 tag_logic_info 相关的对话循环
        
        Args:
            gobj_info: GameObject信息（如果为None，则使用child_info）
            scene_name: 场景名称
            conversation_history: 对话历史记录
            child_info: 子对象信息（可选，当gobj_info为None时使用）
        
        Returns:
            List[Dict]: 更新后的对话历史记录
        """
        # 确定要处理的tag_logic_info来源
        if gobj_info is None and child_info is not None:
            # 处理子对象的tag_logic_info
            target_info = child_info
            info_type = "子对象"
        else:
            # 处理主GameObject的tag_logic_info
            target_info = gobj_info
            info_type = "主GameObject"
        
        tag_logic_info = target_info.get('tag_logic_info', [])
        if not tag_logic_info:
            return conversation_history
        
        print(f"🔄 开始处理 {info_type} 的 tag_logic_info 循环，包含 {len(tag_logic_info)} 个 tag...")
        
        # 用于跟踪已经通过tag_logic_info处理过的对象ID
        processed_object_ids = set()
        
        # 处理每个 tag_logic_info
        for tag_index, tag_info in enumerate(tag_logic_info, 1):
            tag_name = tag_info.get('tag_name')
            tag_id = tag_info.get('id')
            
            if not tag_name:
                continue
            
            print(f"🏷️  处理第 {tag_index} 个 tag: {tag_name} (ID: {tag_id})")
            
            # 检查是否是处理子对象的tag_logic_info
            if gobj_info is None and child_info is not None:
                # 处理子对象的tag_logic_info，使用TAG_LOGIC_CHILD_REQUEST_TEMPLATE
                print(f"🔍 检测到子对象 {child_info['child_name']} 有 tag_logic_info，使用 TAG_LOGIC_CHILD_REQUEST_TEMPLATE")
                
                # 获取子对象的基本信息
                parent_name = child_info['parent_info']['parent_name']
                child_name = child_info['child_name']
                child_id = child_info['child_id']
                mono_comp_ids = child_info['mono_comp_targets']
                
                # 将当前子对象ID添加到已处理集合中
                processed_object_ids.add(child_id)
                
                # 获取脚本源代码
                script_content = ""
                if len(mono_comp_ids) > 0:
                    for i, mono_comp in enumerate(mono_comp_ids):
                        target_script_id = mono_comp['target']
                        script_source = self._extract_script_source_code(target_script_id) 
                        if i == len(mono_comp_ids) - 1:
                            script_content += script_source
                        else:
                            script_content += script_source
                            script_content += "\n'''\n"
                            script_content += f"[Source code {i}th of script files ({target_script_id}) attached]\n'''\n"
                
                combined_script_source = script_content if script_content else "// Script source code not found"
                
                # 获取子对象的场景元数据
                child_scene_meta = self._find_child_gameobject_info(child_id, scene_name, mono_comp_ids)
                
                # 生成 tag_logic_prompt
                tag_logic_prompt = self._get_tag_logic_prompt(target_info)
                
                # 使用 TAG_LOGIC_CHILD_REQUEST_TEMPLATE 生成请求
                request = TAG_LOGIC_CHILD_REQUEST_TEMPLATE.format(
                    child_index=tag_index,  # 使用tag_index作为child_index
                    parent_name=parent_name,
                    child_name=child_name,
                    child_id=child_id,
                    combined_script_source=combined_script_source,
                    child_scene_meta=child_scene_meta['scene_meta'] if child_scene_meta else "// Scene meta data not found",
                    tag_logic_prompt=tag_logic_prompt
                )
                
                # 发送请求到对话历史
                conversation_history.append({
                    'role': 'user',
                    'content': request,
                    'request_type': 'tag_logic_child_request',
                    'tag_index': tag_index,
                    'tag_info': tag_info,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 调用LLM API获取响应
                tag_response = self._call_llm_api(request)
                
                if tag_response:
                    # 解析LLM响应，提取需要的 GameObject ID 列表
                    needed_gameobject_ids = self._process_tag_logic_response(tag_response, target_info)
                    
                    conversation_history.append({
                        'role': 'assistant',
                        'content': tag_response,
                        'response_type': 'tag_logic_response',
                        'needed_gameobject_ids': needed_gameobject_ids,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    if needed_gameobject_ids:
                        print(f"📋 LLM需要以下GameObject的信息: {needed_gameobject_ids}")
                        
                        # 将这些需要的GameObject ID也添加到已处理集合中
                        processed_object_ids.update(needed_gameobject_ids)
                        
                        # 获取这些GameObject的脚本源代码和场景元数据，分别标注
                        script_sources_and_meta = self._get_formatted_script_sources_and_meta(needed_gameobject_ids, scene_name)
                        
                        # 使用 TAG_TEST_REQUEST_TEMPLATE 发送请求
                        # 对于主GameObject，使用target_info的ID作为child_id
                        tag_test_request = TAG_TEST_REQUEST_TEMPLATE.format(
                            needed_gameobject_ids=needed_gameobject_ids,
                            child_id=child_id,
                            script_sources_and_meta=script_sources_and_meta
                        )
                        
                        conversation_history.append({
                            'role': 'user',
                            'content': tag_test_request,
                            'request_type': 'tag_test_request',
                            'tag_index': tag_index,
                            'tag_info': tag_info,
                            'needed_gameobject_ids': needed_gameobject_ids,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        # 调用LLM API获取测试计划响应
                        tag_test_response = self._call_llm_api(tag_test_request)
                        
                        if tag_test_response:
                            # 解析LLM响应
                            parsed_tag_test_response = self._parse_llm_response(tag_test_response)
                            conversation_history.append({
                                'role': 'assistant',
                                'content': tag_test_response,
                                'response_type': 'test_plan_response',
                                'need_more_info': parsed_tag_test_response['need_more_info'],
                                'test_plan': parsed_tag_test_response['test_plan'],
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # 如果LLM仍然需要更多信息，继续循环
                            if parsed_tag_test_response['need_more_info']:
                                print(f"📋 LLM仍然需要更多信息，继续处理下一个 tag...")
                                continue
                            else:
                                print(f"✅ LLM已获得足够信息，tag_logic_info 处理完成")
                                break
                        else:
                            print(f"❌ 获取 tag {tag_name} 的测试计划响应失败")
                            conversation_history.append({
                                'role': 'assistant',
                                'content': f"Error: Failed to get test plan response for tag {tag_name}",
                                'response_type': 'error',
                                'need_more_info': True,
                                'timestamp': datetime.now().isoformat()
                            })
                    else:
                        print(f"⚠️  LLM没有指定需要的GameObject ID")
                else:
                    print(f"❌ 获取 tag {tag_name} 的LLM响应失败")
                    conversation_history.append({
                        'role': 'assistant',
                        'content': f"Error: Failed to get LLM response for tag {tag_name}",
                        'response_type': 'error',
                        'need_more_info': True,
                        'timestamp': datetime.now().isoformat()
                    })
                
            else:
                # 处理主GameObject的tag_logic_info，使用原来的逻辑
                # 生成 tag_logic_info 的 prompt
                tag_logic_prompt = self._get_tag_logic_prompt(target_info)
                if tag_logic_prompt:
                    # 发送 tag_logic_info 请求
                    conversation_history.append({
                        'role': 'user',
                        'content': tag_logic_prompt,
                        'request_type': 'tag_logic_request',
                        'tag_index': tag_index,
                        'tag_info': tag_info,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # 调用LLM API获取响应
                    tag_response = self._call_llm_api(tag_logic_prompt)
                    
                    if tag_response:
                        # 解析LLM响应，提取需要的 GameObject ID 列表
                        needed_gameobject_ids = self._process_tag_logic_response(tag_response, target_info)
                        
                        conversation_history.append({
                            'role': 'assistant',
                            'content': tag_response,
                            'response_type': 'tag_logic_response',
                            'needed_gameobject_ids': needed_gameobject_ids,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        if needed_gameobject_ids:
                            print(f"📋 LLM需要以下GameObject的信息: {needed_gameobject_ids}")
                            
                            # 将这些需要的GameObject ID也添加到已处理集合中
                            processed_object_ids.update(needed_gameobject_ids)
                            
                            # 获取这些GameObject的脚本源代码和场景元数据，分别标注
                            script_sources_and_meta = self._get_formatted_script_sources_and_meta(needed_gameobject_ids, scene_name)
                            
                            # 使用 TAG_TEST_REQUEST_TEMPLATE 发送请求
                            tag_test_request = TAG_TEST_REQUEST_TEMPLATE.format(
                                needed_gameobject_ids=needed_gameobject_ids,
                                child_id=child_id,
                                script_sources_and_meta=script_sources_and_meta
                            )
                            
                            conversation_history.append({
                                'role': 'user',
                                'content': tag_test_request,
                                'request_type': 'tag_test_request',
                                'tag_index': tag_index,
                                'tag_info': tag_info,
                                'needed_gameobject_ids': needed_gameobject_ids,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # 调用LLM API获取测试计划响应
                            tag_test_response = self._call_llm_api(tag_test_request)
                            
                            if tag_test_response:
                                # 解析LLM响应
                                parsed_tag_test_response = self._parse_llm_response(tag_test_response)
                                conversation_history.append({
                                    'role': 'assistant',
                                    'content': tag_test_response,
                                    'response_type': 'test_plan_response',
                                    'need_more_info': parsed_tag_test_response['need_more_info'],
                                    'test_plan': parsed_tag_test_response['test_plan'],
                                    'timestamp': datetime.now().isoformat()
                                })
                                
                                # 如果LLM仍然需要更多信息，继续循环
                                if parsed_tag_test_response['need_more_info']:
                                    print(f"📋 LLM仍然需要更多信息，继续处理下一个 tag...")
                                    continue
                                else:
                                    print(f"✅ LLM已获得足够信息，tag_logic_info 处理完成")
                                    break
                            else:
                                print(f"❌ 获取 tag {tag_name} 的测试计划响应失败")
                                conversation_history.append({
                                    'role': 'assistant',
                                    'content': f"Error: Failed to get test plan response for tag {tag_name}",
                                    'response_type': 'error',
                                    'need_more_info': True,
                                    'timestamp': datetime.now().isoformat()
                                })
                        else:
                            print(f"⚠️  LLM没有指定需要的GameObject ID")
                    else:
                        print(f"❌ 获取 tag {tag_name} 的LLM响应失败")
                        conversation_history.append({
                            'role': 'assistant',
                            'content': f"Error: Failed to get LLM response for tag {tag_name}",
                            'response_type': 'error',
                            'need_more_info': True,
                            'timestamp': datetime.now().isoformat()
                        })
        
        # 在对话历史中添加已处理对象ID的信息
        if processed_object_ids:
            conversation_history.append({
                'role': 'system',
                'content': f"已通过tag_logic_info处理过的对象ID: {list(processed_object_ids)}",
                'response_type': 'processed_objects_info',
                'processed_object_ids': list(processed_object_ids),
                'timestamp': datetime.now().isoformat()
            })
            print(f"📝 已记录通过tag_logic_info处理过的对象ID: {list(processed_object_ids)}")
        
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
        
        # 从对话历史中提取已经通过tag_logic_info处理过的对象ID
        processed_object_ids = set()
        for msg in conversation_history:
            if msg.get('response_type') == 'processed_objects_info' and 'processed_object_ids' in msg:
                processed_object_ids.update(msg['processed_object_ids'])
        
        if processed_object_ids:
            print(f"🔍 发现已通过tag_logic_info处理过的对象ID: {list(processed_object_ids)}")
        
        for i, child_info in enumerate(child_mono_comp_info, 1):
            child_id = child_info['child_id']
            child_name = child_info['child_name']
            
            # 检查该子对象是否已经在tag_logic_info中被处理过
            if child_id in processed_object_ids:
                print(f"⏭️  跳过子对象 {child_name} (ID: {child_id})，已在tag_logic_info中处理过")
                conversation_history.append({
                    'role': 'system',
                    'content': f"跳过子对象 {child_name} (ID: {child_id})，已在tag_logic_info中处理过",
                    'response_type': 'skipped_object_info',
                    'skipped_object_id': child_id,
                    'skipped_object_name': child_name,
                    'timestamp': datetime.now().isoformat()
                })
                continue
            
            print(f"📤 正在提供第{i}个子对象信息: {child_name}")
            
            # 生成子对象请求，并处理tag_logic_info逻辑
            child_request_result = self.generate_child_request(child_info, i, scene_name, conversation_history)
            
            if child_request_result['has_tag_logic']:
                # 如果有tag_logic_info，已经通过generate_child_request处理完成
                print(f"📋 {child_request_result['message']}")
                continue
            
            # 没有tag_logic_info的子对象，使用正常的流程
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


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="生成Unity GameObject的测试计划对话")
    parser.add_argument('-r', '--results-dir', required=True, 
                       help='结果目录路径，包含gobj_hierarchy.json和场景数据')
    parser.add_argument('-s', '--scene-name', 
                       help='场景名称（可选，如果不指定则使用config.py中的默认值）')
    parser.add_argument('-a', '--app-name', 
                       help='应用名称（可选，如果不指定则使用config.py中的默认值）')
    parser.add_argument('--no-llm', action='store_true',
                       help='禁用LLM API调用，使用模拟模式')
    
    args = parser.parse_args()
    results_dir = args.results_dir
    scene_name = args.scene_name
    app_name = args.app_name
    enable_llm = not args.no_llm
    
    try:
        # 创建测试计划生成器
        generator = TestPlanGenerator(results_dir, scene_name, app_name, enable_llm)
        
        # 生成所有测试计划
        test_plans = generator.generate_all_test_plans(generator.scene_name)
        
        if test_plans:
            # 打印摘要信息
            generator.print_conversation_summary(test_plans)
        else:
            print("没有生成任何测试计划")
            
    except Exception as e:
        print(f"生成测试计划时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
