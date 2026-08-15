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

import bpy
from bpy.types import Operator
from . import exporter


def menu_export_nodegraph_button(self, context):
    self.layout.operator(exporter.ExportNodeGroupsSelector.bl_idname, text="Node Groups (.xml)")

def menu_export_shadergraph_button(self, context):
    self.layout.operator(exporter.ExportMaterialsSelector.bl_idname, text="Shader Materials (.xml)")

def register():
    bpy.types.TOPBAR_MT_file_export.append(menu_export_nodegraph_button)
    bpy.types.TOPBAR_MT_file_export.append(menu_export_shadergraph_button)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_export_nodegraph_button)
    bpy.types.TOPBAR_MT_file_export.remove(menu_export_shadergraph_button)
