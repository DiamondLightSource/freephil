
++++++++++++++++++++++++++
Code reference of FreePHIL
++++++++++++++++++++++++++

.. contents:: Sections


================
Common functions
================

.. automodule:: freephil
   :members: parse, show_attributes, find_scope, change_default_phil_values, process_command_line

===========
Phil object
===========

For overview see :ref:`phil-object`

The Phil object can be:

1. :class:`freephil.scope` if it has multiple sub-objects (parameters) or it is root object
2. :class:`freephil.definition` if it consist of a single value.

Both types provides similar set of functions and attributes.

.. autoclass:: freephil.scope
   :members:

.. autoclass:: freephil.definition
   :members:

=============================
Python object (scope_extract)
=============================

.. autoclass:: freephil.scope_extract
   :members: __phil_path__, __inject__, __phil_path_and_value__, __phil_join__
   :private-members:

=======================
Command line processing
=======================

.. autoclass:: freephil.command_line.argument_interpreter
   :members:

.. autoclass:: freephil.command_line.process
   :members:

..
    ========================
    Graphical user interface
    ========================

    FreePHIL provides some helpers for GUI creation.

    .. autoclass:: freephil.gui_objects.style
       :members: