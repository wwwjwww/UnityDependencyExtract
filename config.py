unity_analyzer_path = r"D:\\UnityDataAnalyzer\\UnityDependencyExtract\\UnityDataAnalyzer\\UnityDataAnalyzer.exe"
csharp_analyzer_path = r"D:\\UnityDataAnalyzer\\UnityDependencyExtract\\CSharpScriptAnalyzer\\CSharpAnalyzer.exe"
structure_analyzer_path = r"D:\\UnityDataAnalyzer\\UnityDependencyExtract\\CodeStructureAnalyzer\\CodeStructureAnalyzer.exe"
prompt_instruct_format = "Despite the events that can be triggered automatically, please choose the event we want to trigger in some conditions. We will provide the source code of the script attacked to this gameobjects below. Please give me a test plans to trigger all the events and also ensure wider code coverage. Do not generate other information other than I specified here. \n[Format of Test Plans] Give me a list of plans, each plan contains actions chosen from the action list: ['Grab', 'Move', 'Drop', 'Trigger', 'Transform']. I need a quantitative plan with a list of step by step actions:\nFor example, if you choose 'Move' action, please give me <'Move', '(x,y,z)('Position of the destination')'>;\nIf you choose 'Grab', please give me <'Grab', 'name of the gameobject you want to grab'>;\nIf you choose 'Trigger', please give me <'Trigger', 'name of the gameobject you want to trigger', 'how to trigger the gameobjects',  'how many times you need to trigger to ensure code coverage'>;\nIf you choose 'Transform', please give me <'Transform', 'name of the gameobject you want to transform', 'detailed position you want to transform to ensure code coverage'>;\nAfter you provide me sequence of action list, please give me list of expecting feedbacks to check after we perform the test. Here, please provide me with feedbacks that can easily be detected by our test engineers of multimodal feedback, such as vision and sound. For example, Action: <'Trigger', 'button 1'>; Feedbacks:<'Gameobject n', 'Status: Active'>.\n"
prompt_source_code_header = "[Source code of script files attached]\n"
prompt_meta_header = "[Compiled Information of scene meta file]\n"
prompt_meta_format = "The scene file can specify the detailed settings of gameobjects and its attached Monobehavior. We've already compiled the information in JSON format. I'll provide you with the related information of game object and its components. The monobehaviour component controls the logic of gameobject. And the transform component is used to store and manipulate the position, rotation and scale of the object. Please specify that the Monobehavior component in the scene file I provided is the settings of the script file attached to the game objects we want to test. Please read the scene settings below and finalize the quantative conditions of your detailed plan based on the scene file.\n"

# Test Plan Generation Prompt Templates
TEST_PLAN_FIRST_REQUEST_TEMPLATE = """Imagine you are helping software test engineers to create comprehensive test plans without delving into the specifics of the code. Test engineers want to test the {app_name} App. One game object we want to test in the scene of '{scene_name}.unity' is '{gobj_name}'.
Despite the events that can be triggered automatically, please choose the event we want to trigger in some conditions. We will provide the source code attached to this gameobjects below.
[Source code of scene meta file] The scene file of '{scene_name}.unity' can specify the detailed settings of gameobjects and its attached Monobehavior. I'll provide you with the related information of game object '{gobj_name}' and its script. The Guid of gameobject '{gobj_name}' is: {gobj_id}. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects we want to test. Please read the file below.
'''
{scene_meta}
'''
The 'm_Children' of Transform indicate series of attached child game objects. We can provide the related information of these objects to help formalize your test plans one by one. """

# Test Plan Generation Prompt Templates
TEST_PLAN_FIRST_REQUEST_SCRIPT_TEMPLATE = """Imagine you are helping software test engineers to create comprehensive test plans without delving into the specifics of the code. Test engineers want to test the {app_name} App. One game object we want to test in the scene of '{scene_name}.unity' is '{gobj_name}'.
Despite the events that can be triggered automatically, please choose the event we want to trigger in some conditions. We will provide the source code of the script attached to this gameobjects below. There may be more than one script attached to one gameobject. And the scene meta setting (MonoBehaviour Component) is shown corresponding to the script file shown.
[Source code of script files attached]
'''
{script_source}
'''
[Source code of scene meta file] The scene file of '{scene_name}.unity' can specify the detailed settings of gameobjects and its attached Monobehavior. I'll provide you with the related information of game object '{gobj_name}' and its script. The Guid of gameobject '{gobj_name}' is: {gobj_id}. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects we want to test. Please read the file below.
'''
{scene_meta}
'''
The 'm_Children' of Transform indicate series of attached child game objects. We can provide the related information of these objects to help formalize your test plans one by one. """

# Test Plan Generation Prompt Templates
TEST_PLAN_FIRST_REQUEST_NO_CHILD_TEMPLATE = """Imagine you are helping software test engineers to create comprehensive test plans without delving into the specifics of the code. Test engineers want to test the {app_name} App. One game object we want to test in the scene of '{scene_name}.unity' is '{gobj_name}'.
Despite the events that can be triggered automatically, please choose the event we want to trigger in some conditions. We will provide the source code attached to this gameobjects below.
[Source code of scene meta file] The scene file of '{scene_name}.unity' can specify the detailed settings of gameobjects and its attached Monobehavior. I'll provide you with the related information of game object '{gobj_name}' and its script. The Guid of gameobject '{gobj_name}' is: {gobj_id}. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects we want to test. Please read the file below.
'''
{scene_meta}
'''

[Format of Test Plans] Based on the provided information, please generate a comprehensive test plan for the GameObject. The test plan should contain actions chosen from the action list: ['Grab', 'Trigger', 'Transform']. You don't need to consider how to interact with the gameobject.

Please structure your response in the following JSON format:

{{
  "taskUnit": [
    {{
      "actionUnits": [
        {{
          "type": "Grab",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_object_name": {{target_object_name}},
          "target_object_fileID": {{target_object_fileID}}
        }},
        {{
          "type": "Trigger",
          "source_object_name": {{source_object_name}},
          "method": "The name of method to trigger it",
          "condition": "How many times to trigger it or condition"
        }},
        {{
          "type": "Transform",
          "source_object_name": {{source_object_name}},
          "target_name": "target_position_or_transformation"
        }}
      ]
    }}
  ],
  "Need_more_Info": true/false
}}
**Action Type Guidelines:**
- **Grab**: Grab or pick up source object and drop it to the target object
- **Trigger**: Activate events or change state of gameobjects
- **Transform**: Move the gameobject to the target position or rotation
Please give me one test plan based on all the information I provided to trigger all the events to ensure code coverage. If you need other information to finalize this test plan, Please also respond with a draft test plan and respond with "Need_more_Info" be true."""

# Test Plan Generation Prompt Templates
TEST_PLAN_FIRST_REQUEST_NO_CHILD_SCRIPT_TEMPLATE = """Imagine you are helping software test engineers to create comprehensive test plans without delving into the specifics of the code. Test engineers want to test the {app_name} App. One game object we want to test in the scene of '{scene_name}.unity' is '{gobj_name}'.
Despite the events that can be triggered automatically, please choose the event we want to trigger in some conditions. We will provide the source code of the script attached to this gameobjects below. There may be more than one script attached to one gameobject. And the scene meta setting (MonoBehaviour Component) is shown corresponding to the script file shown.
[Source code of script files attached]
'''
{script_source}
'''
[Source code of scene meta file] The scene file of '{scene_name}.unity' can specify the detailed settings of gameobjects and its attached Monobehavior. I'll provide you with the related information of game object '{gobj_name}' and its script. The Guid of gameobject '{gobj_name}' is: {gobj_id}. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects we want to test. Please read the file below.
'''
{scene_meta}
'''
[Format of Test Plans] Based on the provided information, please generate a comprehensive test plan for the GameObject. The test plan should contain actions chosen from the action list: ['Grab', 'Trigger', 'Transform']. You don't need to consider how to interact with the gameobject.

Please structure your response in the following JSON format:

{{
  "taskUnit": [
    {{
      "actionUnits": [
        {{
          "type": "Grab",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_object_name": {{target_object_name}},
          "target_object_fileID": {{target_object_fileID}}
        }},
        {{
          "type": "Trigger",
          "source_object_name": {{source_object_name}},
          "method": "The name of method to trigger it",
          "condition": "How many times to trigger it or condition"
        }},
        {{
          "type": "Transform",
          "source_object_name": {{source_object_name}},
          "target_name": "target_position_or_transformation"
        }}
      ]
    }}
  ],
  "Need_more_Info": true/false
}}
**Action Type Guidelines:**
- **Grab**: Grab or pick up source object and drop it to the target object
- **Trigger**: Activate events or change state of gameobjects
- **Transform**: Move the gameobject to the target position or rotation
Please give me one test plan based on all the information I provided to trigger all the events to ensure code coverage. If you need other information to finalize this test plan, Please also respond with a draft test plan and respond with "Need_more_Info" be true.
"""


TEST_PLAN_CHILD_REQUEST_TEMPLATE = """The children is "{child_name}": {{fileID: {child_id}}}. The direct parent of this gameobject is "{parent_name}". We only present the child with attached script. And the {child_name} gameobject which has attached script's information is below. There may be more than one script attached to one gameobject. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects. And the scene meta setting (MonoBehaviour Component) is shown corresponding to the script file shown.
[Source code of 1st script files attached]
'''
{script_source}
'''
[Source code of scene meta file]
'''
{child_scene_meta}
'''
[Format of Test Plans] The test plan should contain actions chosen from the action list: ['Grab', 'Trigger', 'Transform']. You don't need to consider how to interact with the gameobject.

Please structure your response in the following JSON format:

{{
  "taskUnit": [
    {{
      "actionUnits": [
        {{
          "type": "Grab",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_object_name": {{target_object_name}},
          "target_object_fileID": {{target_object_fileID}}
        }},
        {{
          "type": "Trigger",
          "source_object_name": {{source_object_name}},
          "method": "The name of method to trigger it",
          "condition": "How many times to trigger it or condition"
        }},
        {{
          "type": "Transform",
          "source_object_name": {{source_object_name}},
          "target_name": "target_position_or_transformation"
        }}
      ]
    }}
  ],
  "Need_more_Info": true/false
}}
**Action Type Guidelines:**
- **Grab**: Grab or pick up source object and drop it to the target object
- **Trigger**: Activate events or change state of gameobjects
- **Transform**: Move the gameobject to the target position or rotation

Please give me one test plan based on all the information I provided to trigger all the events to ensure code coverage. If you need another information, Please also respond with a draft test plan and respond with "Need_more_Info" be true."""

# Tag Logic Test Request Template
TAG_TEST_REQUEST_TEMPLATE = """Based on the tag logic information, the following gameobjects {needed_gameobject_ids} have corresponding tags with script of gameobject "{child_id}". The information of these gameobjects is below.

{script_sources_and_meta}

[Format of Test Plans] The test plan should contain actions chosen from the action list: ['Grab', 'Trigger', 'Transform']. You don't need to consider how to interact with the gameobject.

Please structure your response in the following JSON format:

{{
  "taskUnit": [
    {{
      "actionUnits": [
        {{
          "type": "Grab",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_object_name": {{target_object_name}},
          "target_object_fileID": {{target_object_fileID}}
        }},
        {{
          "type": "Trigger",
          "source_object_name": {{source_object_name}},
          "method": "The name of method to trigger it",
          "condition": "How many times to trigger it or condition"
        }},
        {{
          "type": "Transform",
          "source_object_name": {{source_object_name}},
          "target_name": "target_position_or_transformation"
        }}
      ]
    }}
  ],
  "Need_more_Info": true/false
}}
**Action Type Guidelines:**
- **Grab**: Grab or pick up source object and drop it to the target object
- **Trigger**: Activate events or change state of gameobjects
- **Transform**: Move the gameobject to the target position or rotation

Please finalize the test plan based on all the information I provided to trigger all the events to ensure code coverage. If you need another information, Please also respond with a draft test plan and respond with "Need_more_Info" be true."""

TAG_LOGIC_CHILD_REQUEST_TEMPLATE = """The children is "{child_name}": {{fileID: {child_id}}}. The direct parent of this gameobject is "{parent_name}". We only present the child with attached script. And the {child_name} gameobject which has attached script's information is below. There may be more than one script attached to one gameobject. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects. And the scene meta setting (MonoBehaviour Component) is shown corresponding to the script file shown.
[Source code of 1st script files attached]
'''
{combined_script_source}
'''
[Source code of scene meta file]
'''
{child_scene_meta}
'''
{tag_logic_prompt}
"""

# Tag Logic Child Request Template (for children with tag_logic_info)
TAG_LOGIC_CHILD_REQUEST_TEMPLATE_NEW = f"""The children is "{child_name}": {{fileID: {child_id}}}. The direct parent of this gameobject is "{parent_name}". We only present the child with attached script. And the {child_name} gameobject which has attached script's information is below. There may be more than one script attached to one gameobject. Please specify that the Monobehaviour component in the scene file I provided is the settings of the script file attached to the game objects. And the scene meta setting (MonoBehaviour Component) is shown corresponding to the script file shown.
[Source code of 1st script files attached]
'''
{combined_script_source}
'''
[Source code of scene meta file]
'''
{child_scene_meta}
'''

The following gameobjects {needed_gameobject_ids} have corresponding tags with .CompareTag() logic in the source script of gameobject "{child_id}". The information of these gameobjects are belows:
{script_sources_and_meta}

[Format of Test Plans] The test plan should contain actions chosen from the action list: ['Grab', 'Trigger', 'Transform']. You don't need to consider how to interact with the gameobject.

Please structure your response in the following JSON format:

{{
  "taskUnit": [
    {{
      "actionUnits": [
        {{
          "type": "Grab",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_object_name": {{target_object_name}},
          "target_object_fileID": {{target_object_fileID}}
        }}
      ]
    }},
    {{
      "actionUnits": [
        {{
          "type": "Trigger",
          "source_object_name": {{source_object_name}},
          "triggerring_time": {{triggerring_time}},
          "source_object_fileID": {{source_object_fileID}},
          "condition": "Trigger condition description (may include script ID, GUID, serialization config, expected behavior calls)",
          "triggerring_events": [
            {{
              "methodCallUnits": [
                {{
                  "script_fileID": {{script_fileID}},
                  "method_name": {{method_name}},
                  "parameter_fileID": [{{parameter_fileID}}]
                }}
              ]
            }}
          ]
        }}
      ]
    }},
    {{
      "actionUnits": [
        {{
          "type": "Transform",
          "source_object_name": {{source_object_name}},
          "source_object_fileID": {{source_object_fileID}},
          "target_position": {{
            "x": {{x}},
            "y": {{y}},
            "z": {{z}}
          }},
          "target_rotation": {{
            "x": {{x}},
            "y": {{y}},
            "z": {{z}}
          }},
          "target_scale": {{
            "x": {{x}},
            "y": {{y}},
            "z": {{z}}
          }},
          "triggerring_events": [
            {{
              "methodCallUnits": [
                {{
                  "script_fileID": {{script_fileID}},
                  "method_name": {{method_name}},
                  "parameter_fileID": [{{parameter_fileID}}]
                }}
              ]
            }}
          ],
          "triggerred_events": [
          ],
          "triggerring_time": {{triggerring_time}}
          }}
      ]
    }}
  ],
  "Need_more_Info": true/false
}}
**Action Type Guidelines:**
- **Grab**: Grab or pick up source object and drop it to the target object
Grab action format1:
{{
  "type": "Grab",
  "source_object_name": "<string>",       // Name of the agent or object initiating the grab
  "source_object_fileID": <long>,         // FileID of the source object in the Unity scene file
  "target_object_name": "<string>",       // Name of the target object being grabbed
  "target_object_fileID": <long>          // FileID of the target object in the Unity scene file
}}
Grab action format2:
{{
  "type": "Grab",
  "source_object_name": "<string>",       // Name of the source object
  "source_object_fileID": <long>,         // FileID of the source object in the Unity scene file
  "target_position": {{                   // Target world position to which the object should be moved
    "x": <float>,
    "y": <float>,
    "z": <float>
  }}
}}
- **Trigger**: Activate events or change state of gameobjects
Trigger action format:
{{
  "type": "Trigger",
  "source_object_name": "<string>",       // Name of the source object that triggers the event
  "triggerring_time": <float>, 			      // Duration of the trigger
  "source_object_fileID": <long>,         // FileID of the source object in Unity scene file
  "condition": "<string>",                // Trigger condition description (may include script ID, GUID, serialization config, expected behavior calls)
  "triggerring_events": [                 // List of events during the Trigger process
    // 0 or more event units
    {{
      "methodCallUnits": [                // An event unit containing 0 or more methodCallUnit
        {{
          "script_fileID": <long>,       // FileID of the target script
          "method_name": "<string>",     // Name of the method to call
          "parameter_fileID": []         // List of FileIDs for method parameters
        }}
      ]
    }}
  ],
  "triggerred_events": [                  // List of events after Trigger completion
    	// 0 or more event units
  ]
}}
- **Transform**: Move the gameobject to the target position or rotation
Transform action format:
{{
  "type": "Transform",
  "source_object_name": "<string>",        // Target object name
  "source_object_fileID": <long>,          // FileID of the object in Unity scene
  "target_position": {{                     // Position delta value
    "x": <float>,
    "y": <float>,
    "z": <float>
  }},
  "target_rotation": {{                     // Rotation delta value
    "x": <float>,
    "y": <float>,
    "z": <float>
  }},
  "target_scale": {{                        // Scale delta value
    "x": <float>,
    "y": <float>,
    "z": <float>
  }},
  "triggerring_events": [                 // List of events during the Trigger process
        // 0 or more event units
        {{
          "methodCallUnits": [                // An event unit containing 0 or more methodCallUnit
            {{
              "script_fileID": <long>,     // FileID of the target script
              "method_name": "<string>",     // Name of the method to call
              "parameter_fileID": []         // List of FileIDs for method parameters
            }}
          ]
        }}
      ],
  "triggerred_events": [                  // List of events after Trigger completion
            // 0 or more event units
      ],
  "triggerring_time": <float>                  // Duration of the action
}}


Please finalize the test plan based on all the information I provided to ensure code coverage. If you need another information, Please also respond with a draft test plan and respond with "Need_more_Info" be true.
"""

