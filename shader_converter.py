# blender-nodegraphs-to-xml
# Contributor(s): Tom Schäfer (tschaefer.acc@gmail.com) and Laurin von Bergmann
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import mathutils
import hashlib
import traceback
from lxml import etree as ET
from .geometry_converter import convert_nodegroup_to_xml

def convert_materials_to_xml(materials: list) -> str:
    # root element
    root = ET.Element("BlenderNodeGraphs")

    graph_id = 0
    for material in materials:
        graph_id = convert_material_to_xml(material, root, graph_id)
        graph_id += 1

    return ET.tostring(root, pretty_print=True).decode()

def convert_material_to_xml(material, root, graph_id):
    material_element = ET.SubElement(root, "Material", name=material.name, id=str(graph_id))

    # TODO: check if output format is optimal for info retrieval

    # Iterate through the nodes in the node group
    for node in material.node_tree.nodes:
        
        # check for node groups and convert them recursively
        is_nodegroup = node.bl_idname == "ShaderNodeGroup" or node.bl_idname == "GeometryNodeGroup"
        if is_nodegroup:
            if node.node_tree is not None:
                graph_id += 1
                convert_nodegroup_to_xml(node.node_tree, material_element, graph_id)
                convert_nodegroup_node_to_xml(node, material_element, graph_id)
                continue  # Skip the rest for node groups
            else:
                print(f"Node group {node.name} has no node tree assigned.")
            


        node_element = ET.SubElement(material_element, "Node", name=node.name, type=node.bl_idname)
        # mostly properties regarding graphical representation in blender
        # TODO: validate wether all needed node properties are exported
        filter_unnecessary = {
                'type',
                'name',
                'label',
                
                'width',
                'height',
                'use_custom_color',
                'color_tag',
                'select',
                'show_options',
                'show_preview',
                'hide',
                'show_texture',
                'internal_links',
                'warning_propagation',
        
                'bl_idname',
                'bl_label',
                'bl_description',
                'bl_icon',
                'bl_static_type',
                'bl_width_default',
                'bl_width_min',
                'bl_width_max',
                'bl_height_default',
                'bl_height_min',
                'bl_height_max',
        
                # these are currently filtered out by isinstance checking anyway lol
                'rna_type',
                'location',
                'location_absolute',
                'dimensions',
                'parent', # TODO: might be useful, don't know, investigate
                'color',
        
                # TODO: verify if these are needed
                'texture_mapping',
                'color_mapping',
        
                'node_tree' #handled elsewhere
                }
        convert_node_properties_to_xml(node, node_element, filter_unnecessary)



    # TODO: sort links in graph order
    # Store node links
    # Format: <Connection from='hash_id' to='hash_id' />
    # hash = sha1 of (per graph unique) node name and pointer
    
    for link in material.node_tree.links:
        from_id = port_id_hash(link.from_node.name, link.from_socket.as_pointer())
        to_id = port_id_hash(link.to_node.name, link.to_socket.as_pointer())
        connection_element = ET.SubElement(
            material_element,
            "Connection"
        )
        connection_element.set("from", from_id)
        connection_element.set("to", to_id)

    return graph_id



###################################################
# Conversion Helpers for different property types #
###################################################

def convert_nodegroup_node_to_xml(node, parent_element, graph_id):
    #1. split nodegroup node in 2
    wrapperIN_node_element = ET.SubElement(parent_element, "Node", name=node.name+'_WrapperIn', type=node.bl_idname+"Input")
    wrapperOUT_node_element = ET.SubElement(parent_element, "Node", name=node.name+'_WrapperOut', type=node.bl_idname+"Output")

    inner_input_node_element = parent_element.findall(f"Graph[@id='{graph_id}']")[0].findall(f"Node[@name='Group Input']")[0]
    inner_output_node_element = parent_element.findall(f"Graph[@id='{graph_id}']")[0].findall(f"Node[@name='Group Output']")[0]

    inner_input_node = node.node_tree.nodes.get('Group Input')
    inner_output_node = node.node_tree.nodes.get('Group Output')

    #2. Input Node: route input
    filter_for_input_node = {
                    'type',
                    'name',
                    'label',
                    
                    'width',
                    'height',
                    'use_custom_color',
                    'color_tag',
                    'select',
                    'show_options',
                    'show_preview',
                    'hide',
                    'show_texture',
                    'internal_links',
                    'warning_propagation',
            
                    'bl_idname',
                    'bl_label',
                    'bl_description',
                    'bl_icon',
                    'bl_static_type',
                    'bl_width_default',
                    'bl_width_min',
                    'bl_width_max',
                    'bl_height_default',
                    'bl_height_min',
                    'bl_height_max',
            
                    'rna_type',
                    'location',
                    'location_absolute',
                    'dimensions',
                    'parent',
                    'color',
            
                    'texture_mapping',
                    'color_mapping',
            
                    'node_tree',
                    'outputs'
                    }
    convert_node_properties_to_xml(node, wrapperIN_node_element, filter_for_input_node)

    #3. Output Node: route output
    property_map = {}
    convert_bpy_collection_to_xml(node.outputs, 'outputs', wrapperOUT_node_element, property_map)

    #4. Input Node: route outer to inner
    connect_wrapperIN_to_innerOUT(wrapperIN_node_element, inner_input_node_element, node, inner_input_node)

    #5. Output Node: route inner to outer
    connect_innerOUT_to_wrapperIN(wrapperOUT_node_element, inner_output_node_element, node, inner_output_node)




def convert_node_properties_to_xml(node, node_element, filter_unnecessary=None):

        property_map = {}
        for prop_name in node.bl_rna.properties.keys():
            if filter_unnecessary != None and prop_name in filter_unnecessary:  # filter out unnecessary properties
                continue
            prop = getattr(node, prop_name)

            # collection properties (inputs, outputs)
            if isinstance(prop, bpy.types.bpy_prop_collection):
                
                convert_bpy_collection_to_xml(prop, prop_name, node_element, property_map)

            # standard type properties
            elif isinstance(prop, (str, int, float, bool)):
                ET.SubElement(node_element, "Constant", name=prop_name+str(property_map_update(property_map, prop_name)), value=str(prop))

            # mapping properties (TexMapping, ColorMapping)
            #! Not Sure if these are even needed lol
            # elif isinstance(prop, bpy.types.TexMapping) or isinstance(prop, bpy.types.ColorMapping):
            #    convert_bpy_mapping_to_xml(prop, prop_name, node_element)

            # vector properties (Vector)
            elif isinstance(prop, mathutils.Vector):
                convert_mathutils_vector_to_xml(prop, prop_name, node_element, property_map)
            elif isinstance(prop, bpy.types.GeometryNodeTree) or isinstance(prop, bpy.types.ShaderNodeTree):
                continue  # Skip node_tree properties, handled elsewhere

            else:
                print(f"Unsupported property type for {prop_name} in node {node.name}: {type(prop)}")

        return property_map
                




def convert_mathutils_vector_to_xml(item, item_name, parent_element, property_map):
    try:
        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

        extracted_vec_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"), type="FunctionNodeInputVector")
        vec_value_counter = 0
        for i in item.default_value:
            ET.SubElement(extracted_vec_element, "Constant", name="Value"+str(vec_value_counter), value=str(i))
            vec_value_counter += 1
        extracted_vec_element_outsocket = ET.SubElement(extracted_vec_element, "Port", name="vectorOut", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"))

        connection_element = ET.SubElement(parent_element.getparent(), "Connection")
        from_id = extracted_vec_element_outsocket.get("id")
        to_id = item_element.get('id')
        connection_element.set("from", from_id)
        connection_element.set("to", to_id)

    except Exception as e:
        print(f"{item_name}: {type(item)} | is not a mathutils.Vector")
        traceback.print_exc()


# def convert_mathutils_euler_to_xml(prop, prop_name, parent_element):
#     try:
#         euler_element = ET.SubElement(parent_element, "Property", name=prop_name, type=type(prop).__name__)
#         for i, v in enumerate(prop):
#             ET.SubElement(euler_element, "Value", data=str(v))
#         ET.SubElement(euler_element, "Value", data=str(prop.order))
#     except Exception as e:
#         print(f"{prop_name}: {type(prop)} | is not a mathutils.Euler")
#         traceback.print_exc()




def convert_bpy_collection_to_xml(prop, prop_name, parent_element, property_map):
    try:
        for item in prop:
            if item is None:
                continue

            if item.is_linked:
                item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="out" if item.is_output else "in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))
            else:
                if item.is_output:
                    continue  # Skip unlinked output items

                # extract item into new node
                if hasattr(item, 'default_value'):
                    if isinstance(item.default_value, bpy.types.bpy_prop_array):
                        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

                        extracted_vec_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"), type="FunctionNodeInputVector")
                        vec_value_counter = 0
                        for i in range(3):
                            ET.SubElement(extracted_vec_element, "Constant", name="Value"+str(vec_value_counter), value=str(item.default_value[i]))
                            vec_value_counter += 1
                        extracted_vec_out_socket = ET.SubElement(extracted_vec_element, "Port", name="vectorOut", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"))

                        connection_element = ET.SubElement(parent_element.getparent(), "Connection")
                        from_id = extracted_vec_out_socket.get("id")
                        to_id = item_element.get('id')
                        connection_element.set("from", from_id)
                        connection_element.set("to", to_id)

                    else:
                        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

                        extracted_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}valueOut"), type="ShaderNodeValue")
                        ET.SubElement(extracted_element, "Constant", name=item.name, value=str(item.default_value))
                        extracted_out_socket = ET.SubElement(extracted_element, "Port", name="Value", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}valueOut"))

                        connection_element = ET.SubElement(parent_element.getparent(), "Connection")
                        from_id = extracted_out_socket.get("id")
                        to_id = item_element.get('id')
                        connection_element.set("from", from_id)
                        connection_element.set("to", to_id)

                    


    except Exception as e:
        print(f"{prop_name}: {type(prop)} | is not a bpy.types.bpy_prop_collection")
        traceback.print_exc()



# TODO: ColorMapping has item ColorRamp, which is a collection (of ColorRampElements); needs special handling, not imlemented yet
# def convert_bpy_mapping_to_xml(prop, prop_name, parent_element):
#     texture_mapping_element = ET.SubElement(parent_element, "Constant", name=prop_name)
#     for item, item_value in prop.bl_rna.properties.items():
#         if item == 'rna_type':
#             continue
#         item_value = getattr(prop, item, None)
#         item_element = ET.SubElement(texture_mapping_element, "Item", name=str(item), type=type(item_value).__name__)
#         if isinstance(item_value, mathutils.Vector) or isinstance(item_value, mathutils.Euler) or isinstance(item_value, mathutils.Color):
#             for v in item_value:
#                 ET.SubElement(item_element, "Value", data=str(v))
#             if isinstance(item_value, mathutils.Euler):
#                 ET.SubElement(item_element, "Value", data=str(item_value.order))
                
#         else:
#             item_element.set("value", str(item_value))


########################
# Other Helper Methods #
########################

def port_id_hash(parent_name, item_pointer):
    return hashlib.sha1(f'{parent_name}{item_pointer}'.encode()).hexdigest()

def connect_wrapperIN_to_innerOUT(wrapper_node_element, inner_input_node_element, wrapper_node, inner_node):
    inner_property_map = {}
    outer_property_map = {}
    for output_socket in inner_node.outputs:
            if output_socket.name == "":  # there is always an unnamed placeholder socket, skip that b*
                continue
            outer_id = port_id_hash(wrapper_node.get("name"), f"{output_socket.as_pointer()}_WrapperIn-Output")
            inner_id = port_id_hash(inner_node.get("name"), f"{output_socket.as_pointer()}_InnerIn-Input")
            ET.SubElement(wrapper_node_element, "Port", name=output_socket.name+str(property_map_update(outer_property_map, output_socket.name)), direction="out", id=outer_id)
            ET.SubElement(inner_input_node_element, "Port", name=output_socket.name+str(property_map_update(inner_property_map, output_socket.name)), direction="in", id=inner_id)
            connection_element = ET.SubElement(wrapper_node_element.getparent(), "Connection")
            connection_element.set("from", outer_id)
            connection_element.set("to", inner_id)


def connect_innerOUT_to_wrapperIN(wrapper_node_element, inner_output_node_element, wrapper_node, inner_node):
    inner_property_map = {}
    outer_property_map = {}
    for input_socket in inner_node.inputs:
            if input_socket.name == "":  # there is always an unnamed placeholder socket, skip that b*
                continue
            outer_id = port_id_hash(wrapper_node.get("name"), f"{input_socket.as_pointer()}_WrapperOUT-Input")
            inner_id = port_id_hash(inner_node.get("name"), f"{input_socket.as_pointer()}_InnerOUT-Output")
            ET.SubElement(inner_output_node_element, "Port", name=input_socket.name+str(property_map_update(inner_property_map, input_socket.name)), direction="out", id=inner_id)
            ET.SubElement(wrapper_node_element, "Port", name=input_socket.name+str(property_map_update(outer_property_map, input_socket.name)), direction="in", id=outer_id)
            connection_element = ET.SubElement(wrapper_node_element.getparent(), "Connection")
            connection_element.set("from", inner_id)
            connection_element.set("to", outer_id)

def property_map_update(property_map, prop_name):
    if prop_name in property_map:
        property_map[prop_name] += 1
    else:
        property_map[prop_name] = 0
    return property_map[prop_name]