# blender-nodegraphs-to-xml

Blender Addon to export node-groups and materials aka geometry/shader node graphs into a serialized graph in xml

> [!NOTE]
> This plugin is made primarily for exporting (geometry) node-groups. \
> Therefore not all material properties are currently supported. \
> If you are in need of certain functionality, feel free to open an issue. Or better, if you implement it yourself gladly open a pull request.

# Installation

1. zip this project and import it in Blender via Edit -> Preferences -> Get Extensions -> Install from Disk (dropdown arrow top right)

# Ussage

File -> Export -> Node Groups (.xml) \
File -> Export -> Shader Materials (.xml) \
From there you are prompted to select the ones you'd like to export into an xml file.

# Core Architecture (`converter.py`)

The conversion from Blender's internal node representation to XML is handled recursively using `lxml.etree`.

* **Graph Traversal:** The script iterates through all nodes and links of a given material or geometry node tree. Node groups (`ShaderNodeGroup`, `GeometryNodeGroup`) are processed recursively and instantiated as nested `<Graph>` elements.
* **Sub-Graph Routing:** To ensure seamless serialization, node groups nodes are abstracted using `WrapperIn` and `WrapperOut` nodes. These wrappers act as interfaces, directly routing inputs and outputs to the internal representation of the group.
* **Unlinked Inputs & Type Mapping:** Fixed input values (unlinked ports) are extracted into standalone constant nodes (e.g., `FunctionNodeInputVector` or `ShaderNodeValue`). All types of ports and constants are mapped to their Blender type equivalent if they aren't already in that format (e.g., `str` to `STRING`), and values of Euler/Rotation are automatically converted to quaternions via `to_quaternion()` to ensure standardized mathematical representations.
* **Connections:** Connections between nodes are established using global unique IDs generated via SHA1 hashing (`port_id_hash`). This hash is a combination of the node's unique name and its memory pointer (`as_pointer()`). This is subject to change to achieve deterministic behaviour.
* **Diagnostics:** If a graph fails to convert, the exception is caught and serialized into a `<Diagnostics>` block at the root of the XML document.
