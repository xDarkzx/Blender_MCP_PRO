"""Handler modules for BlenderMCP addon.

Each module registers its handlers with the dispatcher.
"""


def register_all_handlers():
    """Register all Phase 1 handlers."""
    from . import scene
    from . import mesh
    from . import object
    from . import material
    from . import modifier
    from . import viewport
    from . import selection

    scene.register()
    mesh.register()
    object.register()
    material.register()
    modifier.register()
    viewport.register()
    selection.register()


def unregister_all_handlers():
    """Unregister all handlers."""
    from ..dispatcher import clear_all_handlers
    clear_all_handlers()
