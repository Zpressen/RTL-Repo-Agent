"""Optional runtime adapters supplied by applications using the Agent."""
from importlib.metadata import entry_points


def workbench_integration():
    providers = list(entry_points(group="zerorepo.runtime", name="workbench"))
    if len(providers) != 1:
        raise RuntimeError(
            "Workbench execution requires one installed RTL Studio integration; "
            "install RTL-Studio in this runtime's Python environment."
        )
    return providers[0].load()()
