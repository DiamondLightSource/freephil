# Content in this file falls under the libtbx license
import bz2
import gzip
import os.path

MANGLE_LEN = 256  # magic constant from compile.c


def _mangle(name, klass):
    """
    Since the compiler module is removed in Python 3, this is a copy of the
    mangle function from compiler.misc.

    This function is used for name mangling in libtbx/__init__.py for the
    slots_getstate_setstate class.
    """
    if not name.startswith("__"):
        return name
    if len(name) + 2 >= MANGLE_LEN:
        return name
    if name.endswith("__"):
        return name
    try:
        i = 0
        while klass[i] == "_":
            i = i + 1
    except IndexError:
        return name
    klass = klass[i:]

    tlen = len(klass) + len(name)
    if tlen > MANGLE_LEN:
        klass = klass[: MANGLE_LEN - tlen]

    return "_%s%s" % (klass, name)


class slots_getstate_setstate(object):
    """
    Implements getstate and setstate for classes with __slots__ defined. Allows an
    object to easily pickle only certain attributes.

    Examples
    --------
    >>> class sym_pair(libtbx.slots_getstate_setstate):
    ...     __slots__ = ["i_seq", "j_seq"]
    ...     def __init__(self, i_seq, j_seq):
    ...         self.i_seq = i_seq
    ...         self.j_seq = j_seq
    ...
    """

    __slots__ = []

    def __getstate__(self):
        """
        The name of some attributes may start with a double underscore such as
        cif_types.comp_comp_id.__rotamer_info. Python name mangling will rename such
        an attribute to _comp_comp_id_rotamer_info. Our __getstate__ function would then
        complain that the __slots__ list contains the non-existent attribute __rotamer_info.
        To fix this we manually mangle attributes with the compiler.misc.mangle function
        which does the right name mangling.
        """
        import warnings

        warning_filters = warnings.filters[:]
        show_warning = warnings.showwarning

        try:
            # avoid printing deprecation warning to stderr when loading mangle
            warnings.simplefilter("ignore")
        finally:
            warnings.showwarning = show_warning
            warnings.filters = warning_filters

        mnames = [_mangle(name, self.__class__.__name__) for name in self.__slots__]

        return dict([(name, getattr(self, name)) for name in mnames])

    def __setstate__(self, state):
        for name, value in state.items():
            setattr(self, name, value)


class AutoType(object):
    """
    Class for creating the Auto instance, which mimics the behavior of None
    with respect to the 'is' and '==' operators; this is used throughout
    CCTBX to indicate parameters that should be determined automatically.

    Examples
    --------
    >>> def f(optional=libtbx.Auto)
    ...    if optional is libtbx.Auto:
    ...        optional = 5
    ...    return optional
    ...
    >>> print(f())
    5
    >>> print(f(optional=10))
    10
    """

    singleton = None

    def __str__(self):
        return "Auto"

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """AutoType behaves as a singleton, so return the same hash value for all instances."""
        return hash(AutoType)

    def __new__(cls):
        if cls.singleton is None:
            cls.singleton = super(AutoType, cls).__new__(cls)
        return cls.singleton


def open_for_writing(file_name, mode="w", gzip_mode="wb"):
    assert mode in ["w", "wb", "a", "ab"]
    assert gzip_mode in ["w", "wb", "a", "ab"]
    file_name = os.path.expanduser(file_name)
    if file_name.endswith(".gz"):
        return gzip.open(file_name, gzip_mode)
    elif file_name.endswith(".bz2"):
        return bz2.BZ2File(file_name, mode)
    try:
        return open(file_name, mode)
    except IOError as e:
        raise IOError("Cannot open file for writing: %r\n" % file_name + "  " + str(e))
