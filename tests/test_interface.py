# Content in this file falls under the libtbx license

import io

import pytest

import freephil.interface


def test(tmp_path):
    master_phil = freephil.parse(
        """
refinement {
  input {
    pdb {
      file_name = None
        .type = path
        .multiple = True
    }
    sequence = None
      .type = path
      .style = seq_file
  }
  refine {
    strategy = *individual_sites *individual_adp *occupancies tls rigid_body
      .type = choice(multi=True)
    adp {
      tls = None
        .type = str
        .multiple = True
        .help = Selection for TLS group
    }
  }
  main {
    ncs = False
      .type = bool
      .help = This turns on NCS restraints
    ordered_solvent = False
      .type = bool
    number_of_macro_cycles = 3
      .type = int
    ias = False
      .type = bool
  }
  developer
    .expert_level = 3
  {
    place_elemental_ions = False
      .type = bool
  }
  gui {
    include scope freephil.interface.tracking_params
    output_dir = None
      .type = path
      .style = output_dir
  }
}
""",
        process_includes=True,
    )
    refine_phil1 = freephil.parse(
        """
refinement {
  input {
    pdb {
      file_name = protein.pdb
      file_name = ligand.pdb
    }
  }
  refine {
    adp {
      tls = "chain A"
      tls = "chain B"
    }
  }
  main {
    ncs = True
    ordered_solvent = True
  }
}
"""
    )
    refine_phil2_str = """
refinement {
  input {
    pdb {
      file_name = model1.pdb
    }
  }
  main {
    ncs = True
    ordered_solvent = False
  }
}"""
    refine_phil3 = freephil.parse("refinement.main.number_of_macro_cycles=5")
    refine_phil4_str = """
refinement.refine.adp.tls = None
"""
    i = freephil.interface.index(
        master_phil=master_phil, working_phil=refine_phil1, fetch_new=True
    )
    params = i.get_python_object()
    i.update(refine_phil2_str)
    # object retrieval
    pdb_phil = i.get_scope_by_name("refinement.input.pdb.file_name")
    assert len(pdb_phil) == 1
    os_phil = i.get_scope_by_name("refinement.main.ordered_solvent")
    assert os_phil.full_path() == "refinement.main.ordered_solvent"
    os_param = os_phil.extract()
    assert os_param is False
    params = i.get_python_object()
    assert len(params.refinement.refine.adp.tls) == 2
    # more updating, object extraction
    i.merge_phil(phil_object=refine_phil3)
    params = i.get_python_object()
    assert params.refinement.main.ncs is True
    assert params.refinement.main.ordered_solvent is False
    assert params.refinement.main.number_of_macro_cycles == 5
    assert params.refinement.input.pdb.file_name == ["model1.pdb"]
    i.merge_phil(phil_string=refine_phil4_str)
    params = i.get_python_object()
    assert len(params.refinement.refine.adp.tls) == 0
    phil1 = freephil.parse("""refinement.refine.strategy = *tls""")
    phil2 = freephil.parse("""refinement.input.pdb.file_name = ligand2.pdb""")
    i.save_param_file(
        file_name=tmp_path / "tst_params.eff",
        sources=[phil1, phil2],
        extra_phil="refinement.main.ias = True",
        diff_only=True,
    )
    params = i.get_python_from_file(tmp_path / "tst_params.eff")
    assert params.refinement.refine.strategy == ["tls"]
    assert params.refinement.input.pdb.file_name == ["model1.pdb", "ligand2.pdb"]
    assert params.refinement.main.ias is True
    i2 = i.copy(preserve_changes=False)
    params2 = i2.get_python_object()
    assert not params2.refinement.main.ncs
    i3 = i.copy(preserve_changes=True)
    params3 = i3.get_python_object()
    assert params3.refinement.main.ncs is True
    seq_file_def = i.get_seq_file_def_name()
    assert seq_file_def == "refinement.input.sequence"

    # text searching (we can assume this will break quickly, but easily checked
    # by uncommenting the print statements)
    names = i.search_phil_text("macro_cycles", phil_name_only=True)
    assert len(names) == 1
    names = i.search_phil_text("elemental")
    assert len(names) == 1
    i.update("refinement.gui.output_dir=/var/tmp")
    i.update('refinement.gui.job_title="Hello, world!"')
    assert i.get_output_dir() == "/var/tmp"
    assert i.get_job_title() == "Hello, world!"

    assert (
        freephil.interface.get_adjoining_phil_path(
            "refinement.input.xray_data.file_name", "labels"
        )
        == "refinement.input.xray_data.labels"
    )

    master_phil = freephil.parse(
        """
pdb_in = None
  .type = path
  .short_caption = Input model
  .style = file_type:pdb input_file
pdb_out = None
  .type = path
  .style = file_type:pdb new_file
"""
    )
    working_phil = master_phil.fetch(
        source=freephil.parse(
            """
pdb_in = foo.pdb
pdb_out = foo.modified.pdb
"""
        )
    )
    i = freephil.interface.index(
        master_phil=master_phil, working_phil=working_phil, fetch_new=False
    )
    pdb_map = i.get_file_type_map("pdb")
    assert pdb_map.get_param_names() == ["pdb_in"]
    assert i.get_input_files() == [("foo.pdb", "Input model", "pdb_in")]
    # test captions
    master_phil = freephil.parse(
        """
my_options {
opt1 = *foo bar
  .type = choice
  .caption = Foo Bar
opt2 = *two_fofc fofc
  .type = choice(multi=True)
  .caption = 2mFo-DFc
}
"""
    )
    with pytest.raises(AssertionError, match="my_options.opt2"):
        freephil.interface.validate_choice_captions(master_phil)


def test_adopt_phil():
    master_phil = freephil.parse(
        """\
scope1 {
  a = 1
    .type = int
  b = 2
    .type = int
}
"""
    )
    working_phil = freephil.parse(
        """\
scope1.a = 3
scope1.b = 4
"""
    )
    i = freephil.interface.index(
        master_phil=master_phil, working_phil=working_phil, fetch_new=True
    )
    assert i.get_python_object()
    other_master_phil = freephil.parse(
        """\
scope1 {
  c = 3
    .type = int
}
scope2 {
  subscope2 {
    d = 4
      .type = int
  }
  e = 5
    .type = int
}
"""
    )
    i.adopt_phil(phil_object=other_master_phil)
    scope1 = i.get_scope_by_name("scope1")
    s = io.StringIO()
    scope1.show(out=s)
    assert (
        s.getvalue()
        == """\
scope1 {
  a = 3
  b = 4
  c = 3
}
"""
    )
    s = io.StringIO()
    i.working_phil.show(out=s)
    assert (
        s.getvalue()
        == """\
scope1 {
  a = 3
  b = 4
  c = 3
}
scope2 {
  subscope2 {
    d = 4
  }
  e = 5
}
"""
    )
