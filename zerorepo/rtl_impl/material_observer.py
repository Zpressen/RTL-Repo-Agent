"""Optional source callbacks for durable workbench code/check observations."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_publisher = ContextVar('rtl_material_publisher', default=None)


@contextmanager
def observe_materials(publisher):
    token = _publisher.set(publisher)
    try:
        yield
    finally:
        _publisher.reset(token)


def current_publisher():
    return _publisher.get()


def code_saved(path, origin='fragment'):
    publisher = _publisher.get()
    if publisher is not None and Path(path).suffix in {'.v', '.sv', '.vh', '.svh'}:
        publisher.capture_file(Path(path), origin)
