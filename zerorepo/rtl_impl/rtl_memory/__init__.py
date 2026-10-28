__all__ = ["RTLMemoryDistiller", "RTLMemorySelector", "RTLMemoryStore"]

def __getattr__(name):
    # Ledger/CLI consumers do not need to load the Agent/model stack.
    import importlib
    modules = {'RTLMemoryDistiller':'distiller', 'RTLMemorySelector':'selector', 'RTLMemoryStore':'store'}
    if name not in modules: raise AttributeError(name)
    return getattr(importlib.import_module('.'+modules[name], __name__), name)
