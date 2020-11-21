import io

import freephil


def read_libtbx_scope(scope):
    buffer = io.StringIO()
    top = 424242
    scope.show(out=buffer, expert_level=top, attributes_level=top)
    return freephil.parse(buffer.getvalue())
