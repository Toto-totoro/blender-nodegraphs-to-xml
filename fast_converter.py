import bpy
import mathutils
from lxml import etree as ET

class GeometryNodeSerializer:
    def __init__(self, element):
        self.e = element

    def isVector(self, slot):
        return isinstance(slot, bpy.types.bpy_prop_array) or isinstance(slot, mathutils.Euler) or isinstance(slot, mathutils.Color) or isinstance(slot, mathutils.Vector)

    def vec2string(self, vector, prefix=""):
        len = vector.__len__()
        for i, v in enumerate(vector):
            ET.SubElement(
                self.e,
                "Value",
                name = prefix + chr(ord('z')-(len-i-1)),
                value = str(v)
            )
        
        if isinstance(vector, mathutils.Euler):
            self.vec2string(vector.to_quaternion(), "q")

    def hash_thing(self, node):
        return hex(abs(hash(node)))

    def handle_slots(self, slots):
        parent_elem = self.e
        
        for i, slot in enumerate(slots):
            self.e = ET.SubElement(
                parent_elem,
                "Socket",
                type = slot.label,
                name = slot.name+ str(i),
                direction = "out" if slot.is_output else "in",
                hash = self.hash_thing(slot)
            )
            
            value = "None" 
            if "default_value" in dir(slot):
                def_v = slot.default_value
                if self.isVector(def_v):
                    value = self.vec2string(def_v)
                else:
                    value = str(def_v)
                    ET.SubElement(
                        self.e,
                        "Value",
                        name = "v",
                        value = str(value)
                    )
        
        self.e = parent_elem
            

    def handle_node_group(self, node_group):
        olde = self.e
        
        self.e = ET.SubElement(
            self.e,
            "Graph",
            name = node_group.name
        )
        
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
        
        for node in node_group.nodes:
            node_elem = ET.SubElement(
                parent_elem,
                "Node",
                name = node.name,
                type = node.type
            )
            self.e = node_elem
            
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
            irrelevant_attr_types = [
                "bpy_func",
                "bpy_prop_collection"
            ]
            
            for a in dir(node):
                if a not in irrelevant_attrs:
                    v = getattr(node, a)
                    if type(v).__name__ not in irrelevant_attr_types:
                        parent_elem2 = self.e
                        self.e = ET.SubElement(
                            self.e,
                            "Attribute",
                            type = type(v).__name__,
                            name = a,
                        )
                        if self.isVector(v):
                            self.vec2string(v)
                        elif isinstance(v, bpy.types.GeometryNodeTree):
                            self.handle_node_group(v)
                        else:
                            ET.SubElement(
                                self.e,
                                "Value",
                                name = "v",
                                value = str(v)
                            )
                        self.e = parent_elem2
                
            self.handle_slots(node.inputs)
            self.handle_slots(node.outputs)

            print()
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