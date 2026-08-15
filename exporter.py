# Blender NodeGraphs_to_XML
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


import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator
from .geometry_converter import convert_node_groups_to_xml
from .shader_converter import convert_materials_to_xml

###############
# Node Groups #
###############

# UI and logic for selecting node groups to export
class ExportNodeGroupsSelector(bpy.types.Operator):
    bl_idname = "export.geometrynodegroups"
    bl_label = "Export Geometry Node Groups"

    select_all: BoolProperty(
        name="Select Everything",
        default=False,
        description="Toggle all node groups for export",
    )

    old_select_all: BoolProperty(
        default=False,
        options={'HIDDEN'}
    )

    # draws UI for selecting the node groups to export as a checkbox list
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "select_all")
        layout.separator()
        layout.label(text="Select Node Group to Export:")

        box = layout.box()

        for item in context.blend_data.node_groups:
            row = box.row()
            row.prop(item, "export", text=item.name)

    # Opens the export dialog when the operator is invoked
    def invoke(self, context, event):
        self.filepath = ""
        self.select_all = False
        self.old_select_all = False
        return context.window_manager.invoke_props_dialog(self)

    # Checks and updates the list of node groups to export when the "Select Everything" checkbox is toggled
    def check(self, context):
        if self.select_all != self.old_select_all:
            for item in context.blend_data.node_groups:
                item.export = self.select_all
            self.old_select_all = self.select_all    
            return True
        return True

    # Checks if node groups are selected for export and if so, opens the file dialog for exporting the geometry node groups to XML
    def execute(self, context):
        node_groups_to_export = any(item.export for item in bpy.data.node_groups)
        if not node_groups_to_export:
            self.report({'ERROR'}, "No node group selected for export.")
            return {'CANCELLED'}

        bpy.ops.export.nodegroups('INVOKE_DEFAULT')
        return {'FINISHED'}

# UI and logic for exporting the selected node groups to XML
class ExportNodeGroupsExecutor(bpy.types.Operator, ExportHelper):
    bl_idname = "export.nodegroups"
    bl_label = "Export Node Groups"
    filename_ext = ".xml"

    # Executes the export process for the selected node groups
    def execute(self, context):
        target_filepath = self.filepath
        node_groups_to_export = [item for item in bpy.data.node_groups if item.export]
        xml_string = convert_node_groups_to_xml(node_groups_to_export)

        # Generates XML file, stores XML string into generated file,saves it in specified location
        with open(target_filepath, 'w', encoding='utf-8') as file:
            file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file.write(xml_string)
        return {'FINISHED'}


#############
# Materials #
#############

# UI and logic for selecting materials to export
class ExportMaterialsSelector(bpy.types.Operator):
    bl_idname = "export.shadergraph"
    bl_label = "Export ShaderGraph"

    select_all: BoolProperty(
        name="Select Everything",
        default=False,
        description="Toggle all materials for export",
    )

    old_select_all: BoolProperty(
        default=False,
        options={'HIDDEN'}
    )

    # draws UI for selecting the materials to export as a checkbox list
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "select_all")
        layout.separator()
        layout.label(text="Select Material to Export:")

        box = layout.box()

        for item in context.blend_data.materials:
            row = box.row()
            row.prop(item, "export", text=item.name)

    # Opens the export dialog when the operator is invoked
    def invoke(self, context, event):
        self.filepath = ""
        self.select_all = False
        self.old_select_all = False
        return context.window_manager.invoke_props_dialog(self)

    # Checks and updates the list of materials to export when the "Select Everything" checkbox is toggled
    def check(self, context):
        if self.select_all != self.old_select_all:
            for item in context.blend_data.materials:
                item.export = self.select_all
            self.old_select_all = self.select_all    
            return True
        return True

    # Checks if materials are selected for export and if so, opens the file dialog for exporting the shader graph to XML
    def execute(self, context):
        materials_to_export = any(item.export for item in bpy.data.materials)
        if not materials_to_export:
            self.report({'ERROR'}, "No material selected for export.")
            return {'CANCELLED'}

        bpy.ops.export.materials('INVOKE_DEFAULT')
        return {'FINISHED'}

# UI and logic for exporting the selected materials to XML
class ExportMaterialsExecutor(bpy.types.Operator, ExportHelper):
    bl_idname = "export.materials"
    bl_label = "Export Materials"
    filename_ext = ".xml"

    # Executes the export process for the selected materials
    def execute(self, context):
        target_filepath = self.filepath
        materials_to_export = [item for item in bpy.data.materials if item.export]
        xml_string = convert_materials_to_xml(materials_to_export)

        # Generates XML file, stores XML string into generated file,saves it in specified location
        with open(target_filepath, 'w', encoding='utf-8') as file:
            file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file.write(xml_string)
        return {'FINISHED'}


############
# Register #
############
        
def register():
    bpy.types.GeometryNodeTree.export = BoolProperty(name="", default=False)
    bpy.utils.register_class(ExportNodeGroupsSelector)
    bpy.utils.register_class(ExportNodeGroupsExecutor)

    bpy.types.Material.export = BoolProperty(name="", default=False)
    bpy.utils.register_class(ExportMaterialsSelector)
    bpy.utils.register_class(ExportMaterialsExecutor)


def unregister():
    bpy.utils.unregister_class(ExportNodeGroupsExecutor)
    bpy.utils.unregister_class(ExportNodeGroupsSelector)
    del bpy.types.GeometryNodeTree.export

    bpy.utils.unregister_class(ExportMaterialsExecutor)
    bpy.utils.unregister_class(ExportMaterialsSelector)
    del bpy.types.Material.export