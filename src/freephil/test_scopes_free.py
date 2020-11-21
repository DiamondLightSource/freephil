"""
Importable data structures for freephil unit tests
"""


class _Foreign_Scope:
    is_scope = True

    def show(self, out, attributes_level=0, expert_level=0):
        assert attributes_level > 0
        assert expert_level > 0
        out.write(
            """
            foreign_value = 13
              .type = int
            """
        )


foreign_scope = _Foreign_Scope()
