import freephil


def test_understand_foreign_scopes():
    master_phil = freephil.parse(
        """
        include scope freephil.test_scopes_free.foreign_scope
        native_value = 2
          .type = int
        """,
        process_includes=True,
    )
    assert master_phil.extract().native_value == 2
    assert master_phil.extract().foreign_value == 13
