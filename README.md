# blender-nodegraphs-to-xml
Blender Addon to export node-groups and materials aka geometry/shader node graphs into a serialized graph in xml

> [!NOTE]
> This plugin is made primarily for exporting (geometry) node-groups. \
> Therefore the functions for materials and node-groups are currently semi-duplicate split into 2 converter files \
> to accomodate for future tweaks to the material conversion functionality

# Installation
1. zip this project and import it in Blender via Edit -> Preferences -> Get Extensions -> Install from Disk (dropdown arrow top right)

# Ussage
File -> Export -> Node Groups (.xml) \
File -> Export -> Shader Materials (.xml) \
From there you are prompted to select the ones you'd like to export into an xml file.
