import bpy
import mathutils
from lxml import etree as ET

class GeometryNodeSerializer:
    def __init__(self, element):
        self.e = element

    # Returns true if the value is of a vector type
    def isVector(self, value):
        return isinstance(value, bpy.types.bpy_prop_array) or isinstance(value, mathutils.Euler) or isinstance(value, mathutils.Color) or isinstance(value, mathutils.Vector)

    # Converts a given vector to multiple Value entries
    def handle_vector(self, vector, prefix=""):
        len = vector.__len__()
        for i, v in enumerate(vector):
            ET.SubElement(
                self.e,
                "Value",
                name = prefix + chr(ord('z')-(len-i-1)),
                value = str(v)
            )

        # If rotation, add quaternion angles too with q prefix
        if isinstance(vector, mathutils.Euler):
            self.handle_vector(vector.to_quaternion(), "q")

    # Placeholder hash function, not guaranteed unique due to abs
    def hash_thing(self, node):
        return hex(abs(hash(node)))

    # Handles serializing all slots of an element
    def handle_slots(self, slots):
        parent_elem = self.e
        
        for i, slot in enumerate(slots):
            # Add Socket tag
            self.e = ET.SubElement(
                parent_elem,
                "Socket",
                type = slot.label,
                name = slot.name+ str(i),
                direction = "out" if slot.is_output else "in",
                hash = self.hash_thing(slot)
            )

            # If default value exists, add it as a Value tag
            value = "None" 
            if "default_value" in dir(slot):
                def_v = slot.default_value
                if self.isVector(def_v):
                    # If it's a vector, parse differently
                    value = self.handle_vector(def_v)
                else:
                    # Otherwise convert to string
                    value = str(def_v)
                    ET.SubElement(
                        self.e,
                        "Value",
                        name = "v",
                        value = str(value)
                    )
        
        self.e = parent_elem
            

    # Serializes each node group, including the top level one
    def handle_node_group(self, node_group):
        olde = self.e

        # Add graph element
        self.e = ET.SubElement(
            self.e,
            "Graph",
            name = node_group.name
        )

        # Serialize Links
        self.links = {}
        for link in node_group.links:
            self.links[str(self.hash_thing(link.from_socket))] = str(self.hash_thing(link.to_socket))
            self.links[str(self.hash_thing(link.to_socket))] = str(self.hash_thing(link.from_socket))
            
            ET.SubElement(
                self.e,
                "Link",
                from_socket = self.hash_thing(link.from_socket),
                to_socket = self.hash_thing(link.to_socket)
            )

        
        parent_elem = self.e

        # Serialize nodes
        for node in node_group.nodes:
            # Add node tag
            node_elem = ET.SubElement(
                parent_elem,
                "Node",
                name = node.name,
                type = node.type
            )
            self.e = node_elem

            # Attributes to ignore
            irrelevant_attrs = [
                "__doc__",
                "__module__",
                "__slots__",
                "rna_type",
                "bl_rna",
                "parent",
                "show_options",
                "show_euler",
                "show_texture",
                "use_custom_color",
                "width",
                "height",
                "label",
                "color",
                "bl_label",
                "bl_width_max",
                "bl_width_min",
                "bl_width_default",
                "bl_static_type",
                "bl_height_max",
                "bl_height_min",
                "bl_height_default",
                "bl_icon",
                "bl_idname",
                "color_tag",
                "dimensions",
                "bl_description",
                "height",
                "location",
                "location_absolute",
                "select",
                "show_preview",
                "type",
                "warning_propagation",
                "name",
                "hide"
            ]
            # Attribute types to ignore
            irrelevant_attr_types = [
                "bpy_func",
                "bpy_prop_collection"
            ]

            for a in dir(node):
                if a not in irrelevant_attrs: # filter irrelevant
                    v = getattr(node, a)
                    if type(v).__name__ not in irrelevant_attr_types: # filter irrelevant types
                        parent_elem2 = self.e
                        # Add attribute Tag
                        self.e = ET.SubElement(
                            self.e,
                            "Attribute",
                            type = type(v).__name__,
                            name = a,
                        )

                        # Serialize value
                        if self.isVector(v):
                            self.handle_vector(v) # if vector
                        elif isinstance(v, bpy.types.GeometryNodeTree):
                            self.handle_node_group(v) # if subgraph recurse
                        else: # if normal value
                            ET.SubElement(
                                self.e,
                                "Value",
                                name = "v",
                                value = str(v)
                            )
                        self.e = parent_elem2
            
            # Serialize the nodes slots
            self.handle_slots(node.inputs)
            self.handle_slots(node.outputs)

        self.e = parent_elem
        self.e = olde

def export_graphs_fast(node_graphs: list) -> str:
    root = ET.Element(
        "BlenderNodeGraphs",
        exporter = "FAST",
        version = "0.1",
    )
    modifier = None

    for ng in node_graphs:
        s = GeometryNodeSerializer(root)
        s.handle_node_group(ng)
    
    return ET.tostring(root, pretty_print=True).decode()
    #print(ET.tostring(root, pretty_print=True).decode())