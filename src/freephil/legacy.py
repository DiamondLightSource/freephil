# Content in this file falls under the libtbx license

MANGLE_LEN = 256  # magic constant from compile.c


def mangle(name, klass):
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
            from libtbx.utils import mangle

        finally:
            warnings.showwarning = show_warning
            warnings.filters = warning_filters

        mnames = [mangle(name, self.__class__.__name__) for name in self.__slots__]

        return dict([(name, getattr(self, name)) for name in mnames])

    def __setstate__(self, state):
        for name, value in state.items():
            setattr(self, name, value)
