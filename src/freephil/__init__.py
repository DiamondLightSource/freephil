try:
    from libtbx import Auto
    from libtbx.utils import Sorry
except ModuleNotFoundError:
    from .legacy import AutoType

    Auto = AutoType()

    class Sorry(SystemExit):
        pass


from .common import *  # noqa

__version__ = "0.1.0"
