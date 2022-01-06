### How do I migrate from cctbx PHIL to freephil?

a good start:
```
$ find -name '*.py' -exec sed -i 's/from libtbx import phil/import freephil as phil/g' {} +
$ find -name '*.py' -exec sed -i 's/from libtbx.phil import/from freephil import/g' {} +
$ find -name '*.py' -exec sed -i 's/libtbx\.phil/freephil/g' {} +
$ find -name '*.py' -exec sed -i 's/from iotbx import phil/import freephil as phil/g' {} +
$ find -name '*.py' -exec sed -i 's/from iotbx.phil import/from freephil import/g' {} +
$ find -name '*.py' -exec sed -i 's/iotbx\.phil/freephil/g' {} +
```
