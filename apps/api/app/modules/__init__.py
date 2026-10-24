import importlib
import pkgutil


def load_models() -> None:
    """Import every module's ``models`` so all tables are registered on ``Base.metadata``."""
    for module in pkgutil.iter_modules(__path__):
        try:
            importlib.import_module(f"{__name__}.{module.name}.models")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{module.name}.models":
                raise
