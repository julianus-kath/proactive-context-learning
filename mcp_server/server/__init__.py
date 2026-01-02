from importlib import import_module

__all__ = ["app"]


def __getattr__(name):
    if name == "app":
        return import_module(".app", __name__).app
    raise AttributeError(name)
