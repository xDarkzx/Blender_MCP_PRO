"""Addon preferences for BlenderMCP."""

try:
    import bpy
    from .shared.constants import DEFAULT_HOST, DEFAULT_PORT

    class BlenderMCPPreferences(bpy.types.AddonPreferences):
        bl_idname = __package__

        host: bpy.props.StringProperty(
            name="Host",
            description="TCP server host (localhost only for security)",
            default=DEFAULT_HOST,
        )

        port: bpy.props.IntProperty(
            name="Port",
            description="TCP server port",
            default=DEFAULT_PORT,
            min=1024,
            max=65535,
        )

        auto_start: bpy.props.BoolProperty(
            name="Auto Start",
            description="Automatically start server when Blender opens",
            default=False,
        )

        def draw(self, context):
            layout = self.layout
            layout.prop(self, "host")
            layout.prop(self, "port")
            layout.prop(self, "auto_start")

    def get_preferences():
        """Get addon preferences."""
        addon = bpy.context.preferences.addons.get(__package__)
        if addon:
            return addon.preferences
        return None

except ImportError:
    # Not running inside Blender
    class BlenderMCPPreferences:
        pass

    def get_preferences():
        return None
