"""UI panel for BlenderMCP in the 3D Viewport sidebar."""

try:
    import bpy
    from .connection import get_server, start_server, stop_server
    from .preferences import get_preferences
    from .shared.constants import DEFAULT_HOST, DEFAULT_PORT

    class BLENDERMCP_OT_start_server(bpy.types.Operator):
        bl_idname = "blendermcp.start_server"
        bl_label = "Start MCP Server"
        bl_description = "Start the BlenderMCP TCP server"

        def execute(self, context):
            prefs = get_preferences()
            host = prefs.host if prefs else DEFAULT_HOST
            port = prefs.port if prefs else DEFAULT_PORT
            try:
                start_server(host, port)
                self.report({"INFO"}, f"BlenderMCP server started on {host}:{port}")
            except Exception as e:
                self.report({"ERROR"}, f"Failed to start server: {e}")
            return {"FINISHED"}

    class BLENDERMCP_OT_stop_server(bpy.types.Operator):
        bl_idname = "blendermcp.stop_server"
        bl_label = "Stop MCP Server"
        bl_description = "Stop the BlenderMCP TCP server"

        def execute(self, context):
            stop_server()
            self.report({"INFO"}, "BlenderMCP server stopped")
            return {"FINISHED"}

    class BLENDERMCP_PT_main_panel(bpy.types.Panel):
        bl_label = "BlenderMCP Pro"
        bl_idname = "BLENDERMCP_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "BlenderMCP"

        def draw(self, context):
            layout = self.layout
            server = get_server()

            if server and server.is_running:
                layout.label(text="Server: Running", icon="CHECKMARK")
                if server.is_connected:
                    layout.label(text="Client: Connected", icon="LINKED")
                else:
                    layout.label(text="Client: Waiting...", icon="UNLINKED")
                layout.operator("blendermcp.stop_server", icon="CANCEL")
            else:
                layout.label(text="Server: Stopped", icon="X")
                layout.operator("blendermcp.start_server", icon="PLAY")

            # Show connection info
            prefs = get_preferences()
            if prefs:
                box = layout.box()
                box.label(text=f"Host: {prefs.host}")
                box.label(text=f"Port: {prefs.port}")

    CLASSES = [
        BLENDERMCP_OT_start_server,
        BLENDERMCP_OT_stop_server,
        BLENDERMCP_PT_main_panel,
    ]

    def register():
        for cls in CLASSES:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)

except ImportError:
    # Not running inside Blender
    CLASSES = []
    def register(): pass
    def unregister(): pass
