# Content in this file falls under the libtbx license

import freephil
import freephil.tokenizer

"""
Importable data structures for freephil unit tests
"""

include_scope_target_0n = None

include_scope_target_0f = 1.0

include_scope_target_1 = freephil.parse(
    """\
x=1
  .help=u
s
  .help=v
{
  y=2
    .help=w
}
"""
)

include_scope_target_2s = """\
p=1
include scope freephil.test_scopes.include_scope_target_1
q=2
r {
  include scope freephil.test_scopes.include_scope_target_1 s.y
}
x=3
"""

include_scope_target_2 = freephil.parse(include_scope_target_2s)

scope_call_not_callable = None


def scope_call_func(scope_extract, **keyword_args):
    if keyword_args.get("action") == "raise":
        raise ValueError("action==raise")
    return scope_extract, keyword_args


class scope_call_class:
    def __init__(self, scope_extract, **keyword_args):
        self.scope_extract = scope_extract
        self.keyword_args = keyword_args


class scope_call_class_object:
    def __init__(self, scope_extract, **keyword_args):
        self.scope_extract = scope_extract
        self.keyword_args = keyword_args


improper_phil_converters = None


class int_phil_converters:
    def __init__(self, factor=1):
        assert int(factor) == factor
        self.factor = factor

    def __str__(self):
        if self.factor == 1:
            return "freephil.test_scopes.int"
        return "freephil.test_scopes.int(factor=%d)" % self.factor

    def from_words(self, words, master):
        value = freephil.int_from_words(words=words, path=master.full_path())
        if value is None:
            return value
        return value * self.factor

    def as_words(self, python_object, master):
        if python_object is None:
            return [freephil.tokenizer.word(value="None")]
        return [freephil.tokenizer.word(value=str(python_object / self.factor))]


class converter_implementation(int_phil_converters):
    def __str__(self):
        if self.factor == 1:
            return "freephil.test_scopes.converter_factory"
        return "freephil.test_scopes.converter_factory(factor=%d)" % self.factor


def converter_factory_phil_converters(**args):
    return converter_implementation(**args)
