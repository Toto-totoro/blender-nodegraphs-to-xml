# blender-nodegraphs-to-xml
# Contributor(s): Tom Schäfer (tschaefer.acc@gmail.com) and Laurin von Bergmann
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

#! if you come across weridly looking code, most is intentional and sometimes a bit hacky, since blenders api design is not really consistent from older to newer features.

import bpy
import mathutils
import hashlib
import traceback
from lxml import etree as ET

def convert_node_graphs_to_xml(node_graphs: list) -> str:
    """
    Converts a list of Blender node groups into a serialized XML string representation with lxml etree.
    """
    # root element
    root = ET.Element("BlenderNodeGraphs")

    #* this stupid way of id generation is used because blender does not allow easy use of global variables
    graph_id = 0
    for node_graph in node_graphs:
        try:
            graph_id = convert_node_graph_to_xml(node_graph, root, graph_id)
            graph_id += 1
        except Exception as e:
            print(f"Error converting node graph {node_graph.name}: {e}")
            traceback.print_exc()

    return ET.tostring(root, pretty_print=True).decode()

def convert_node_graph_to_xml(node_graph, root, graph_id) -> int:
    """
    Converts a single Blender node group into an XML element and appends it to the provided root element. \n
    Return:
      graph_id, which increments for each recursive node group conversion to ensure unique graph ids in the XML representation. \n
      or \n
      Exception
    """

    is_material = True if type(node_graph) is bpy.types.Material else False
    nodegroup_element = ET.SubElement(root, "Graph", name=node_graph.name, id=str(graph_id), type="Material" if is_material else "NodeGroup")

    for node in node_graph.nodes if not is_material else node_graph.node_tree.nodes:
        
        # check for node groups and convert them recursively
        node_is_nodegroup = node.bl_idname == "ShaderNodeGroup" or node.bl_idname == "GeometryNodeGroup"
        if node_is_nodegroup:
            if node.node_tree is not None:
                try:
                    graph_id += 1
                    current_graph_id = graph_id
                    graph_id = convert_node_graph_to_xml(node.node_tree, nodegroup_element, graph_id)
                    convert_nodegroup_node_to_xml(node, nodegroup_element, current_graph_id) #! needs to be called after inner node group is converted
                except Exception as e:
                    print(f"Error converting node group {node.name}")
                    raise e
                
                continue  # Skip the rest for node groups
            else:
                print(f"Node group {node.name} has no node tree assigned.")

        node_element = ET.SubElement(nodegroup_element, "Node", name=node.name, type=node.bl_idname)

        # filter contains mostly properties regarding graphical representation in blender
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

    # Store node links
    # Format: <Connection from='hash_id' to='hash_id' />
    # hash = sha1 of (per graph unique) node name and pointer (may vary for extraced nodes in `convert_mathutils_vector_to_xml()` and `convert_bpy_collection_to_xml()` to ensure it's unique)
    for link in node_graph.links if not is_material else node_graph.node_tree.links:
        if link.from_node is None or link.to_node is None:
            print(f"Link from {link.from_node} to {link.to_node} is invalid. Skipping.")
            continue
        if link.from_socket is None or link.to_socket is None:
            print(f"Link from {link.from_node.name} to {link.to_node.name} has invalid sockets. Skipping.")
            continue

        # GROUP nodes are split into 2 in `convert_nodegroup_node_to_xml()`, so names need to be adjusted accordingly
        from_node_name = link.from_node.name
        to_node_name = link.to_node.name
        if link.from_node.type == "GROUP":
            from_node_name += "_WrapperOut"
        if link.to_node.type == "GROUP":
            to_node_name += "_WrapperIn"

        from_id = port_id_hash(from_node_name, link.from_socket.as_pointer())
        to_id = port_id_hash(to_node_name, link.to_socket.as_pointer())
        create_connection_element(nodegroup_element, from_id, to_id)

    return graph_id



########################################################
# Conversion Helpers for different node/property types #
########################################################

#! this might fail to work correctly if the inner node group has more than one input or output node (which shouldn't be the case)
def convert_nodegroup_node_to_xml(node, parent_element, graph_id):
    """
    This function should always be called after the inner node group has been converted to xml \n
    Converts the nodegroup node (for recursive node_groups) by splitting it and wrapping the inner node graph.

    Args:
        node: The node to convert
        parent_element: The nodes parent
        graph_id: The id of the corresponding node graph this node wraps

    Returns:
        Exception if the group input or output node of the inner node graph could not be found in the xml representation
    """

    # retrieve the inner input and output nodes of the node group in the xml representation
    # the nodes are generated into the xml seperately and by using the id and (normally) unique node names we can find them again
    #* sadly currently simplest way for this since global variables are a little tricky in blender
    inner_input_node_elements = parent_element.xpath(f"Graph[@id='{graph_id}']/Node[@type='NodeGroupInput']")
    inner_output_node_elements = parent_element.xpath(f"Graph[@id='{graph_id}']/Node[@type='NodeGroupOutput']")

    if not inner_input_node_elements:
        raise Exception(f"Could not find a group input node for node group {node.name} in graph id {graph_id}. It either doesn't exist in blender or hasn't been converted to xml yet.")
    if not inner_output_node_elements:
        raise Exception(f"Could not find group output node for node group {node.name} in graph id {graph_id}. It either doesn't exist in blender or hasn't been converted to xml yet.")

    # only one output should exist, also check to find the one that is marked as active output (only one should be marked as such by blender)
    if len(inner_output_node_elements) > 1:
        print(f"Warning: Found multiple group output nodes for node group {node.name} in graph id {graph_id}. Only one should exist. Trying to find the correct one.")
    # search for Constant is_active_output and check for true
    inner_output_node_element = [n for n in inner_output_node_elements if n.xpath(".//Constant[@name='is_active_output0']") and n.xpath(".//Constant[@name='is_active_output0']")[0].get("value") == "True"][0] 
    if inner_output_node_element is not None:
        raise Exception(f"Could not find the ACTIVE group output node for node group {node.name} in graph id {graph_id}. It either doesn't exist in blender or hasn't been converted to xml yet.")



    # split nodegroup node in 2 to wrap the inner node graph
    # this allows to easily route the inner node graph inputs and outputs to the outer node graph
    wrapperIN_node_element = ET.SubElement(parent_element, "Node", name=node.name+'_WrapperIn', type=node.bl_idname+"Input")
    wrapperOUT_node_element = ET.SubElement(parent_element, "Node", name=node.name+'_WrapperOut', type=node.bl_idname+"Output")



    inner_input_nodes = [n for n in node.node_tree.nodes if n.bl_idname == 'NodeGroupInput']
    inner_output_nodes = [n for n in node.node_tree.nodes if n.bl_idname == 'NodeGroupOutput']

    # these checks are redundant, they do the same as above, if the nodes aren't found they should also be missing in the xml representation
    if not inner_input_nodes:
        raise Exception(f"Could not find group input node for node group {node.name} in blender.")
    if not inner_output_nodes:
        raise Exception(f"Could not find group output node for node group {node.name} in blender.")
    if len(inner_output_nodes) > 1:
        print(f"Warning: Found multiple group output nodes for node group {node.name} in graph {node.node_tree.name}. Only one should exist. Trying to find the correct one.")
    inner_output_node = [ n for n in inner_output_nodes if n.is_active_output ][0]
    if not inner_output_node:
        raise Exception(f"Could not find the ACTIVE group output node for node group {node.name} in blender.")



    # generate wrapper input, filter out outputs to add custom routing to the inner node group
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
            
                    'node_tree', #special
                    'outputs' #special
                    }
    convert_node_properties_to_xml(node, wrapperIN_node_element, filter_for_input_node)

    # generate wrapper output
    property_map = {}
    convert_bpy_collection_to_xml(node.outputs, 'outputs', wrapperOUT_node_element, property_map)

    # route wrapper nodes to their inner counterparts
    # the ports simply traverse the nodes without any additional processing, so the inner node group can be used as a black box
    connect_wrapperIN_to_innerIN(wrapperIN_node_element, inner_input_node_elements, node, inner_input_nodes)
    connect_innerOUT_to_wrapperOUT(wrapperOUT_node_element, inner_output_node_element, node, inner_output_node)



def convert_node_properties_to_xml(node, node_element, filter_unnecessary=None):
        """
        Converts all the properties of a single Blender node into XML elements and appends them to the provided node element.

        Args:
            node: The Blender node to convert.
            node_element: The XML element to append the node's properties to.
            filter_unnecessary: A list of property names to exclude from the conversion.

        Returns:
            A dictionary mapping property names to their values.
        """

        
        property_map = {} # keeps track of property names added to a node to ensure per node unique property names: names are per name numbered; e.g. "value0, value1, operation0, value2, ..."

        for prop_name in node.bl_rna.properties.keys():
            if filter_unnecessary != None and prop_name in filter_unnecessary:
                continue

            prop = getattr(node, prop_name)

            #* handle new property types here
            # currently unsupported: TexMapping, ColorMapping, mathutils.Euler
            # probably only need to implement new ones if you use custom properties

            # collection properties (inputs, outputs)
            if isinstance(prop, bpy.types.bpy_prop_collection):
                
                convert_bpy_collection_to_xml(prop, prop_name, node_element, property_map)

            # standard type properties
            elif isinstance(prop, (str, int, float, bool)):
                ET.SubElement(node_element, "Constant", name=prop_name+str(property_map_update(property_map, prop_name)), value=str(prop))

            # mapping properties (TexMapping, ColorMapping)
                #* Currently deemed not needed
                # elif isinstance(prop, bpy.types.TexMapping) or isinstance(prop, bpy.types.ColorMapping):
                #    convert_bpy_mapping_to_xml(prop, prop_name, node_element)

            # vector properties (Vector)
            elif isinstance(prop, mathutils.Vector):
                convert_mathutils_vector_to_xml(prop, prop_name, node_element, property_map)

            # rotation properties (Euler)
            elif isinstance(prop, mathutils.Euler):
                convert_mathutils_euler_to_xml(prop, prop_name, node_element, property_map)


            elif isinstance(prop, bpy.types.GeometryNodeTree) or isinstance(prop, bpy.types.ShaderNodeTree):
                continue  # Skip node_tree properties, handled recursively in `convert_node_graph_to_xml()`

            else:
                print(f"Unsupported property type for {prop_name} in node {node.name}: {type(prop)}")

        return property_map
                




def convert_mathutils_vector_to_xml(item, item_name, parent_element, property_map):
    """
    Extracts the given vector property into a new Node, creates a port at the original Node and connects them.
    """
    try:
        pseudo_pointer = f"{parent_element.get('name')}_{item_name}"

        item_element = ET.SubElement(parent_element, "Port", name=item_name+str(property_map_update(property_map, item_name)), direction="in", id=port_id_hash(parent_element.get("name"), pseudo_pointer))

        extracted_vector_element = ET.SubElement(parent_element.getparent(), "Node", name=item_name+"_"+port_id_hash(parent_element.get("name"), f"{pseudo_pointer}vectorOut"), type="FunctionNodeInputVector")

        vec_value_counter = 0
        for i in item:
            ET.SubElement(extracted_vector_element, "Constant", name="Value"+str(vec_value_counter), value=str(i))
            vec_value_counter += 1

        extracted_vector_element_outsocket = ET.SubElement(extracted_vector_element, "Port", name="Vector0", direction="out", id=port_id_hash(parent_element.get("name"), f"{pseudo_pointer}vectorOut"))

        from_id = extracted_vector_element_outsocket.get("id")
        to_id = item_element.get('id')
        create_connection_element(parent_element.getparent(), from_id, to_id)

    except Exception as e:
        raise Exception(f"{item_name}: {type(item)} | in (parent node: {parent_element.get('name')}, property: {item_name}) is either not a mathutils.Vector or broken.") from e



def convert_mathutils_euler_to_xml(item, item_name, parent_element, property_map):
    """
    Extracts the given euler or rotation property into a new Node, creates a port at the original Node and connects them.
    """
    try:
        pseudo_pointer = f"{parent_element.get('name')}_{item_name}"

        item_element = ET.SubElement(parent_element, "Port", name=item_name+str(property_map_update(property_map, item_name)), direction="in", id=port_id_hash(parent_element.get("name"), pseudo_pointer))

        extracted_vector_element = ET.SubElement(parent_element.getparent(), "Node", name=item_name+"_"+port_id_hash(parent_element.get("name"), f"{pseudo_pointer}vectorOut"), type="FunctionNodeInputRotation")

        vec_value_counter = 0
        for i in item:
            ET.SubElement(extracted_vector_element, "Constant", name="Value"+str(vec_value_counter), value=str(i))
            vec_value_counter += 1
        ET.SubElement(extracted_vector_element, "Constant", name="Order"+"0", value=str(item.order))
        extracted_vector_element_outsocket = ET.SubElement(extracted_vector_element, "Port", name="Rotation0", direction="out", id=port_id_hash(parent_element.get("name"), f"{pseudo_pointer}vectorOut"))

        from_id = extracted_vector_element_outsocket.get("id")
        to_id = item_element.get('id')
        create_connection_element(parent_element.getparent(), from_id, to_id)

    except Exception as e:
        raise Exception(f"{item_name}: {type(item)} | in (parent node: {parent_element.get('name')}, property: {item_name}) is either not a mathutils.Euler or broken.") from e


def convert_bpy_collection_to_xml(prop, prop_name, parent_element, property_map):
    """
    Takes a blender bpy_prop_collection element and converts it into an XML representation, appending it to the provided parent element. \n
    Is mainly used for node inputs and outputs, but can be used for any bpy_prop_collection. \n
    The function handles linked and unlinked items differently. Unlinked items usually represent constants. They are extracted into new nodes and then connected back to the original node as ports. \n

    Args:
        prop: The property object to convert
        prop_name: The string name of the property
        parent_element: The XML parent element (usually Node) to append this to
        property_map: A map to keep track of names for numbering

    Returns:
        property_map to update the input property_map
    """
    try:
        for item in prop:

            if item is None:
                continue

            if item.is_linked:
                item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="out" if item.is_output else "in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

            # extract unlinked input item into new node
            else:
                # Skip unlinked output items
                if item.is_output:
                    continue  

                
                if hasattr(item, 'default_value'):

                    #* handle new datatypes for inputs/ouputs here
                    # currently supported: Vector (bpy_prop_array), bool, int, str, Value (float)
                    # currently unsupported: Collection, Color, Image, Material, Object,

                    # Vector
                    if isinstance(item.default_value, bpy.types.bpy_prop_array):
                        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

                        extracted_vector_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"), type="FunctionNodeInputVector")
                        vec_value_counter = 0
                        # default_value can not be iterated over directly (blender stuff), so we have to access the values by index
                        for i in range(item.default_value.__len__()):
                            ET.SubElement(extracted_vector_element, "Constant", name="Value"+str(vec_value_counter), value=str(item.default_value[i]))
                            vec_value_counter += 1
                        extracted_vec_out_socket = ET.SubElement(extracted_vector_element, "Port", name="Vector0", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"))

                        from_id = extracted_vec_out_socket.get("id")
                        to_id = item_element.get('id')
                        create_connection_element(parent_element.getparent(), from_id, to_id)

                    # Rotation (Euler)
                    elif isinstance(item.default_value, bpy.types.NodeSocketRotation):
                        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

                        extracted_vector_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"), type="FunctionNodeInputRotation")
                        vec_value_counter = 0
                        for i in item.default_value:
                            ET.SubElement(extracted_vector_element, "Constant", name="Value"+str(vec_value_counter), value=str(i))
                            vec_value_counter += 1
                        ET.SubElement(extracted_vector_element, "Constant", name="Order"+"0", value=str(item.default_value.order))
                        extracted_vec_out_socket = ET.SubElement(extracted_vector_element, "Port", name="Rotation0", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}vectorOut"))

                        from_id = extracted_vec_out_socket.get("id")
                        to_id = item_element.get('id')
                        create_connection_element(parent_element.getparent(), from_id, to_id)

                    elif isinstance(item.default_value, mathutils.Euler):
                        convert_mathutils_euler_to_xml(item.default_value, item.name, parent_element, property_map)

                    # bool, int, str, float
                    elif isinstance(item.default_value, (int, float, str, bool)):
                        item_element = ET.SubElement(parent_element, "Port", name=item.name+str(property_map_update(property_map, item.name)), direction="in", id=port_id_hash(parent_element.get("name"), item.as_pointer()))

                        type_to_node = {
                            int: "FunctionNodeInputInt",
                            str: "FunctionNodeInputString",
                            float: "ShaderNodeValue",
                            bool: "FunctionNodeInputBool"
                        }

                        extracted_element = ET.SubElement(parent_element.getparent(), "Node", name=item.name+"_"+port_id_hash(parent_element.get("name"), f"{item.as_pointer()}valueOut"), type=type_to_node.get(type(item.default_value), "ShaderNodeValue"))
                        ET.SubElement(extracted_element, "Constant", name=item.name, value=str(item.default_value))
                        extracted_out_socket = ET.SubElement(extracted_element, "Port", name="Value0", direction="out", id=port_id_hash(parent_element.get("name"), f"{item.as_pointer()}valueOut"))

                        from_id = extracted_out_socket.get("id")
                        to_id = item_element.get('id')
                        create_connection_element(parent_element.getparent(), from_id, to_id)

                    else:
                        print(f"value: {item.default_value}, type: {type(item.default_value)} | is an unsupported type in bpy_prop_collection: (parent node: {parent_element.get('name')}, porperty: {prop_name})")



    except Exception as e:
        print(f"{prop_name}: {type(prop)} | is not a bpy.types.bpy_prop_collection or some of its items are broken: {e}")
        traceback.print_exc()



#* ColorMapping has item ColorRamp, which is a collection (of ColorRampElements); needs special handling, not imlemented yet (only for Shader Nodes, since ColorMapping is not used in Geometry Nodes afaik)
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


#############################
# Connection Helper Methods #
#############################

def port_id_hash(parent_name, item_pointer):
    """
    sha1 hash of the parent node name and the pointer of the port item, used to generate globally unique ids for ports in the XML representation.
    """
    return hashlib.sha1(f'{parent_name}{item_pointer}'.encode()).hexdigest()

def create_connection_element(parent_element, from_id, to_id):
    """
    Creates a connection element in the XML representation, connecting two ports by their unique ids.
    """
    connection_element = ET.SubElement(parent_element, "Connection")
    connection_element.set("from", from_id)
    connection_element.set("to", to_id)

def connect_wrapperIN_to_innerIN(wrapper_node_element, inner_input_node_elements, wrapper_node, inner_nodes):
    """
    Copys the output sockets of inner_input_node to wrapper_input_node outputs, duplicates them to the inputs of itself and connects them in the XML representation. \n
    1 to N relation, since multiple inner input nodes can exist.
    """
    inner_property_maps = [{} for _ in inner_nodes]
    outer_property_map = {}
    reference_node = inner_nodes[0]
    for socket_index, output_socket in enumerate(reference_node.outputs):
            if output_socket.name == "":  # there is always an unnamed placeholder socket, skip that b*
                continue
            outer_id = port_id_hash(wrapper_node.name, f"{output_socket.as_pointer()}_WrapperIn-Output")
            ET.SubElement(wrapper_node_element, "Port", name=output_socket.name+str(property_map_update(outer_property_map, output_socket.name)), direction="out", id=outer_id)

            for inner_node, inner_input_node_element, inner_property_map in zip(inner_nodes, inner_input_node_elements, inner_property_maps):

                target_socket = inner_node.outputs[socket_index] # grab specific socket for unique pointer

                inner_id = port_id_hash(inner_node.name, f"{target_socket.as_pointer()}_InnerIn-Input")
                ET.SubElement(inner_input_node_element, "Port", name=target_socket.name+str(property_map_update(inner_property_map, target_socket.name)), direction="in", id=inner_id)
                create_connection_element(wrapper_node_element.getparent(), outer_id, inner_id)


def connect_innerOUT_to_wrapperOUT(wrapper_node_element, inner_output_node_element, wrapper_node, inner_node):
    """
    Copys the input sockets of the inner_output_node to wrapper_output_node inputs, duplicates them to the outputs of itself and connects them in the XML representation.
    """
    inner_property_map = {}
    outer_property_map = {}
    for input_socket in inner_node.inputs:
            if input_socket.name == "":  # there is always an unnamed placeholder socket, skip that b*
                continue
            outer_id = port_id_hash(wrapper_node.name, f"{input_socket.as_pointer()}_WrapperOUT-Input")
            inner_id = port_id_hash(inner_node.name, f"{input_socket.as_pointer()}_InnerOUT-Output")
            ET.SubElement(inner_output_node_element, "Port", name=input_socket.name+str(property_map_update(inner_property_map, input_socket.name)), direction="out", id=inner_id)
            ET.SubElement(wrapper_node_element, "Port", name=input_socket.name+str(property_map_update(outer_property_map, input_socket.name)), direction="in", id=outer_id)
            create_connection_element(wrapper_node_element.getparent(), inner_id, outer_id)


########################
# Other Helper Methods #
########################

def property_map_update(property_map, prop_name):
    """
    Keeps track of the number of times a property name has been used in a node to ensure (per node) unique naming in the XML representation.
    """
    if prop_name in property_map:
        property_map[prop_name] += 1
    else:
        property_map[prop_name] = 0
    return property_map[prop_name]
