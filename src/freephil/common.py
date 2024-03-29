# Content in this file falls under the libtbx license

"Documentation: https://cctbx.github.io/libtbx/libtbx.phil.html"

import io
import math
import os
import sys
import textwrap
import tokenize as python_tokenize
import warnings
import weakref
from itertools import count

import pkg_resources

import freephil

from . import adapter, parser, tokenizer
from .converters import (
    bool_converters,
    bool_from_words,
    choice_converters,
    float_converters,
    floats_converters,
    int_converters,
    int_from_words,
    ints_converters,
    is_standard_identifier,
    key_converters,
    path_converters,
    qstr_converters,
    str_converters,
    str_from_words,
    strings_as_words,
    strings_converters,
    strings_from_words,
    tokenize_value_literal,
    words_converters,
)
from .legacy import slots_getstate_setstate
from .tokens import (
    is_plain_auto,
    is_plain_none,
    standard_identifier_continuation_characters,
    standard_identifier_start_characters,
)

default_print_width = 79


class PhilDeprecationWarning(DeprecationWarning):
    pass


warnings.filterwarnings("always", category=PhilDeprecationWarning)


class _import_python_object:
    def __init__(self, import_path, error_prefix, target_must_be, where_str):
        path_elements = import_path.split(".")
        if len(path_elements) < 2:
            raise ValueError(
                '%simport path "%s" is too short%s%s'
                % (error_prefix, import_path, target_must_be, where_str)
            )
        module_path = ".".join(path_elements[:-1])
        try:
            module = __import__(module_path)
        except ImportError:
            raise ImportError(
                "%sno module %s%s or possibly import errors in "
                "module %s" % (error_prefix, module_path, where_str, module_path)
            )
        for attr in path_elements[1:-1]:
            module = getattr(module, attr)
        try:
            self.object = getattr(module, path_elements[-1])
        except AttributeError:
            raise AttributeError(
                '%sobject "%s" not found in module "%s"%s'
                % (error_prefix, path_elements[-1], module_path, where_str)
            )
        self.path_elements = path_elements
        self.module_path = module_path
        self.module = module


def is_reserved_identifier(string):
    if len(string) < 5:
        return False
    return string.startswith("__") and string.endswith("__")


def get_converters_phil_type(converters):
    result = getattr(converters, "phil_type", None)
    if result is None:
        result = str(converters())  # backward compatibility
    return result


def extended_converter_registry(additional_converters, base_registry=None):
    if base_registry is None:
        base_registry = default_converter_registry
    result = dict(base_registry)
    for converters in additional_converters:
        result[get_converters_phil_type(converters)] = converters
    return result


default_converter_registry = extended_converter_registry(
    additional_converters=[
        words_converters,
        strings_converters,
        str_converters,
        qstr_converters,
        path_converters,
        key_converters,
        bool_converters,
        int_converters,
        float_converters,
        ints_converters,
        floats_converters,
        choice_converters,
    ]
    + [e.load() for e in pkg_resources.iter_entry_points("freephil.converter")],
    base_registry={},
)


def extract_args(*args, **keyword_args):
    return args, keyword_args


def normalize_call_expression(expression):
    result = []
    p = ""
    for info in python_tokenize.generate_tokens(io.StringIO(expression).readline):
        t = info[1]
        if len(t) == 0:
            continue
        if (
            t != "."
            and t[0] in standard_identifier_start_characters
            and len(p) > 0
            and p != "."
            and p[-1] in standard_identifier_continuation_characters
        ):
            result.append(" ")
        result.append(t)
        if t[0] == ",":
            result.append(" ")
        p = t
    return "".join(result)


def definition_converters_from_words(words, converter_registry, converter_cache):
    if is_plain_none(words=words):
        return None
    if is_plain_auto(words=words):
        return freephil.Auto
    call_expression_raw = str_from_words(words).strip()
    try:
        call_expression = normalize_call_expression(expression=call_expression_raw)
    except python_tokenize.TokenError as e:
        raise RuntimeError(
            'Error evaluating definition type "%s": %s%s'
            % (call_expression_raw, str(e), words[0].where_str())
        )
    converters_weakref = converter_cache.get(call_expression, None)
    if converters_weakref is not None:
        converters_instance = converters_weakref()
        if converters_instance is not None:
            return converters_instance
    flds = call_expression.split("(", 1)
    converters = converter_registry.get(flds[0], None)
    if converters is not None:
        if len(flds) == 1:
            parens = "()"
        else:
            parens = ""
        try:
            converters_instance = eval(
                call_expression + parens, math.__dict__, {flds[0]: converters}
            )
        except Exception as e:
            raise RuntimeError(
                f'Error constructing definition type "%s": {e.__class__.__name__}: {e!s}%s'
                % (call_expression, words[0].where_str())
            )
    else:
        import_path = flds[0] + "_phil_converters"
        if len(flds) == 1:
            keyword_args = {}
        else:
            extractor = "__extract_args__(" + flds[1]
            try:
                args, keyword_args = eval(
                    extractor, math.__dict__, {"__extract_args__": extract_args}
                )
            except Exception as e:
                raise RuntimeError(
                    f'Error evaluating definition type "%s": {e.__class__.__name__}: {e!s}%s'
                    % (call_expression, words[0].where_str())
                )
        try:
            imported = _import_python_object(
                import_path=import_path,
                error_prefix=".type=%s: " % call_expression,
                target_must_be="; target must be a callable Python object",
                where_str=words[0].where_str(),
            )
        except (ValueError, ImportError):
            raise RuntimeError(
                'Unexpected definition type: "%s"%s'
                % (call_expression, words[0].where_str())
            )
        if not callable(imported.object):
            raise TypeError(
                '"%s" is not a callable Python object%s'
                % (import_path, words[0].where_str())
            )
        try:
            converters_instance = imported.object(**keyword_args)
        except Exception as e:
            raise RuntimeError(
                f'Error constructing definition type "%s": {e.__class__.__name__}: {e!s}%s'
                % (call_expression, words[0].where_str())
            )
    converter_cache[call_expression] = weakref.ref(converters_instance)
    return converters_instance


def full_path(self):
    # should be a member function to scope? Depreceted?
    result = [self.name]
    pps = self.primary_parent_scope
    while pps is not None:
        if pps.name == "":
            break
        result.append(pps.name)
        pps = pps.primary_parent_scope
    result.reverse()
    return ".".join(result)


def alias_path(self):
    if self.alias is not None:
        return self.alias
    have_alias = False
    result = [self.name]
    pps = self.primary_parent_scope
    while pps is not None:
        if pps.alias is not None:
            result.append(pps.alias)
            have_alias = True
            break
        elif pps.name == "":
            break
        else:
            result.append(pps.name)
        pps = pps.primary_parent_scope
    if not have_alias:
        return None
    result.reverse()
    return ".".join(result)


def show_attributes(self, out, prefix, attributes_level, print_width):
    """
    Prints attributes of the Phil object (scope or definition) to a file

    :param self: Phil object to be printed
    :type self: freephil.scope
    :param out: Output file name
    :type out: str
    :param prefix:
    :type prefix: str
    :param attributes_level: Verbosity of the attributes
    :type attributes_level: int
    :param print_width: Max. lenght of a row
    :type print_width: int

    """
    if attributes_level <= 0:
        return
    for name in self.attribute_names:
        value = getattr(self, name)
        if (name == "deprecated") and (not value):
            continue  # only show .deprecated if True
        if (
            (name == "help" and value is not None)
            or (name == "alias" and value is not None)
            or (value is not None and attributes_level > 1)
            or attributes_level > 2
        ):
            if (name == "alias") and (value is None):
                continue
            if not isinstance(value, str):
                # Python 2.2 workaround
                if name in ["optional", "multiple", "disable_add", "disable_delete"]:
                    if value is False:
                        value = "False"
                    elif value is True:
                        value = "True"
                print(prefix + "  ." + name, "=", value, file=out)
            else:
                indent = " " * (len(prefix) + 3 + len(name) + 3)
                fits_on_one_line = len(indent + value) < print_width
                if not is_standard_identifier(value) or not fits_on_one_line:
                    value = str(tokenizer.word(value=value, quote_token='"'))
                    fits_on_one_line = len(indent + value) < print_width
                if fits_on_one_line:
                    print(prefix + "  ." + name, "=", value, file=out)
                else:
                    is_first = True
                    for block in textwrap.wrap(
                        value[1:-1], width=print_width - 2 - len(indent)
                    ):
                        if is_first:
                            print(
                                prefix + "  ." + name, "=", '"' + block + '"', file=out
                            )
                            is_first = False
                        else:
                            print(indent + '"' + block + '"', file=out)


class object_locator:
    def __init__(self, parent, path, object):
        self.parent = parent
        self.path = path
        self.object = object

    def __str__(self):
        return f"{self.path}{self.object.where_str}"


# is_template (set by .fetch() and .format() methods of definition or scope):
#   0: not a template
#  -1: template but there are other copies
#   1: template and there are no copies


class try_tokenize_proxy:
    def __init__(self, error_message, tokenized):
        self.error_message = error_message
        self.tokenized = tokenized


class try_extract_proxy:
    def __init__(self, error_message, extracted):
        self.error_message = error_message
        self.extracted = extracted


class try_format_proxy:
    def __init__(self, error_message, formatted):
        self.error_message = error_message
        self.formatted = formatted


class definition(slots_getstate_setstate):
    """
    One line definitions used in Phil objects. The class is usually
    generated as part of parent :class:`freephil.scope`

    Attributes possible from parsing Phil string/file. Attribute levels are:

    1. level: ``help`` and ``alias``
    2. level: everything, whose value is not None
    3. level: everything else

    :ivar help: Help entry for the parameter
    :vartype help: str
    :ivar caption: Caption
    :vartype caption: str
    :ivar short_caption: Short caption
    :vartype shot_caption: str
    :ivar optional: Is optional?
    :vartype optional: bool
    :ivar type: Type (see :ref:`phil-type`)
    :ivar multiple: Possible mltiple times? (see :ref:`phil-multiple`)
    :vartype multiple: bool
    :ivar input_size: Input size
    :ivar style:
    :ivar expert_level: Expert level
    :vartype expert_level: int
    :ivar deprecated:
    :ivar alias: Alias

    Other class variables:

    :ivar is_definition: Always ``True``
    :vartype is_definition: bool
    :ivar is_scope: Always ``False``
    :vartype is_scope: bool

    Other instance variables:

    :ivar name:
    :ivar words: Actual value (equivalent of ``objects`` in :class:`freephil.scope`)
    :ivar primary_id:
    :ivar primary_parent_scope: Parent scope
    :vartype primary_parent_scope: freephil.scope
    :ivar is_disabled:
    :ivar is_template:
    :ivar where_str:
    :ivar merge_names:
    :ivar tmp:

    """

    is_definition = True
    is_scope = False

    attribute_names = [
        "help",
        "caption",
        "short_caption",
        "optional",
        "type",
        "multiple",
        "input_size",
        "style",
        "expert_level",
        "deprecated",
        "alias",
    ]

    __slots__ = [
        "name",
        "words",
        "primary_id",
        "primary_parent_scope",
        "is_disabled",
        "is_template",
        "where_str",
        "merge_names",
        "tmp",
    ] + attribute_names

    def __init__(
        self,
        name,
        words,
        primary_id=None,
        primary_parent_scope=None,
        is_disabled=False,
        is_template=0,
        where_str="",
        merge_names=False,
        tmp=None,
        help=None,
        caption=None,
        short_caption=None,
        optional=None,
        type=None,
        multiple=None,
        input_size=None,
        style=None,
        expert_level=None,
        deprecated=None,
        alias=None,
    ):
        if is_reserved_identifier(name):
            raise RuntimeError(f'Reserved identifier: "{name}"{where_str}')
        if name != "include" and "include" in name.split("."):
            raise RuntimeError('Reserved identifier: "include"%s' % where_str)
        self.name = name
        self.words = words
        self.primary_id = primary_id
        self.primary_parent_scope = primary_parent_scope
        self.is_disabled = is_disabled
        self.is_template = is_template
        self.where_str = where_str
        self.merge_names = merge_names
        self.tmp = tmp
        self.help = help
        self.caption = caption
        self.short_caption = short_caption
        self.optional = optional
        self.type = type
        self.multiple = multiple
        self.input_size = input_size
        self.style = style
        self.expert_level = expert_level
        self.deprecated = deprecated
        self.alias = alias

    def __setstate__(self, *args, **kwds):
        slots_getstate_setstate.__setstate__(self, *args, **kwds)
        # XXX backwards compatibility 2012-03-27
        if not hasattr(self, "deprecated"):
            setattr(self, "deprecated", None)

    def copy(self):
        """
        Copy of itself

        :rtype: freephil.definition
        """
        keyword_args = {}
        for keyword in self.__slots__:
            keyword_args[keyword] = getattr(self, keyword)
        return definition(**keyword_args)

    def customized_copy(self, name=None, words=None):
        """
        Customized copy of itself, with new name and words

        :param name: New name
        :type name: str
        :param words: new value(s)
        :rtype: freephil.definition
        """
        result = self.copy()
        if name is not None:
            result.name = name
        if words is not None:
            result.words = words
        result.is_template = 0
        return result

    def full_path(self):
        """
        Returns full path to the definition

        :rtype: str
        """
        return full_path(self)

    def alias_path(self):
        """
        Returns alias of the definition.

        :rtype: str
        """
        return alias_path(self)

    def assign_tmp(self, value, active_only=False):
        if not active_only or not self.is_disabled:
            self.tmp = value

    def fetch_value(self, source, diff_mode=False, skip_incompatible_objects=False):
        if source.is_scope:
            if skip_incompatible_objects:
                return self.copy()
            raise RuntimeError(
                'Incompatible parameter objects: definition "%s"%s vs. scope "%s"%s'
                % (self.name, self.where_str, source.name, source.where_str)
            )
        source.tmp = True
        source = source.resolve_variables(diff_mode=diff_mode)
        type_fetch = getattr(self.type, "fetch", None)
        if self.deprecated:
            # issue warning if value is not the default, otherwise return None so
            # this parameter stays invisible to users
            result_as_str = strings_from_words(source.words)
            self_as_str = strings_from_words(self.words)
            if result_as_str != self_as_str:
                warnings.warn(
                    "%s is deprecated - not recommended for use." % self.full_path(),
                    PhilDeprecationWarning,
                )
            else:
                return None
        if type_fetch is None:
            return self.customized_copy(words=source.words)
        if self.type.phil_type == "choice":
            return type_fetch(
                source_words=source.words,
                master=self,
                ignore_errors=skip_incompatible_objects,
            )
        else:
            return type_fetch(source_words=source.words, master=self)

    def fetch_diff(self, source, skip_incompatible_objects=False):
        """
        Merges the definition with defintions from others sources,
        returns only difference

        :param source:
        :param skip_incompatible_objects:
        :return: Phil object definition
        :rtype: freephil.definition
        """
        result = self.fetch_value(
            source=source,
            diff_mode=True,
            skip_incompatible_objects=skip_incompatible_objects,
        )
        result_as_str = self.extract_format(source=result).as_str()
        self_as_str = self.extract_format().as_str()
        if result_as_str == self_as_str:
            result = None
        return result

    def fetch(self, source, diff=False, skip_incompatible_objects=False):
        """
        Merge the definition with definitions from other source

        :param source: Other definition to merge with
        :type source: freephil.definition
        :param diff: If ``True``, returns only differences.
        :type diff: bool
        :param skip_incompatible_objects: Skip incompatible objects
        :type skip_incompatible_objects: bool
        :return:
        """
        if diff:
            return self.fetch_diff(
                source=source, skip_incompatible_objects=skip_incompatible_objects
            )
        return self.fetch_value(
            source=source, skip_incompatible_objects=skip_incompatible_objects
        )

    def has_attribute_with_name(self, name):
        """
        Returns ``True``, if the atribute exists

        :param name: Attribue name
        :type name: str
        :rtype: bool
        """
        return name in self.attribute_names

    def assign_attribute(self, name, words, converter_registry, converter_cache):
        assert self.has_attribute_with_name(name)
        if name in ["optional", "multiple"]:
            value = bool_from_words(words=words, path="." + name)
        elif name == "type":
            value = definition_converters_from_words(
                words=words,
                converter_registry=converter_registry,
                converter_cache=converter_cache,
            )
        elif name in ["input_size", "expert_level"]:
            value = int_from_words(words=words, path="." + name)
        else:
            value = str_from_words(words)
        setattr(self, name, value)

    def show(
        self,
        out=None,
        merged_names=[],
        prefix="",
        expert_level=None,
        attributes_level=0,
        print_width=None,
    ):
        """
        Pretty prints the definition

        :param out: If provided, writes to the file. The file had to be opened
        :type out: None or file object
        :param merged_names:
        :type merged_names: list of str
        :param prefix: Prefix
        :type prefix: str
        :param expert_level: Maximal expert level
        :type expert_level: int
        :param attributes_level: Attribute level
        :type attributes_level: int
        :param print_width: Maximum linewidth
        :type print_width: int
        """
        if self.is_template < 0 and attributes_level < 2:
            return
        elif self.deprecated and attributes_level < 3:
            return
        if (
            self.expert_level is not None
            and expert_level is not None
            and expert_level >= 0
            and self.expert_level > expert_level
        ):
            return
        if out is None:
            out = sys.stdout
        if print_width is None:
            print_width = default_print_width
        if self.is_disabled:
            hash = "!"
        else:
            hash = ""
        line = prefix + hash + ".".join(merged_names + [self.name])
        if self.name != "include":
            line += " ="
        indent = " " * len(line)
        if self.deprecated:
            print(prefix + "# WARNING: deprecated parameter", file=out)
        for word in self.words:
            line_plus = line + " " + str(word)
            if len(line_plus) > print_width - 2 and len(line) > len(indent):
                print(line + " \\", file=out)
                line = indent + " " + str(word)
            else:
                line = line_plus
        print(line, file=out)
        show_attributes(
            self=self,
            out=out,
            prefix=prefix,
            attributes_level=attributes_level,
            print_width=print_width,
        )

    def as_str(
        self, prefix="", expert_level=None, attributes_level=0, print_width=None
    ):
        """
        Returns pretty print of the definition as string

        :param prefix: Prefix
        :type prefix: str
        :param expert_level: Maximal expert level
        :type expert_level: int
        :param attributes_level: Attribute level
        :type attributes_level: int
        :param print_width: Maximum linewidth
        :type print_width: int
        :return: Pretty print of the definition
        :rtype: str
        """
        out = io.StringIO()
        self.show(
            out=out,
            prefix=prefix,
            expert_level=expert_level,
            attributes_level=attributes_level,
            print_width=print_width,
        )
        return out.getvalue()

    def _all_definitions(
        self, suppress_multiple, select_tmp, parent, parent_path, result
    ):
        if suppress_multiple and self.multiple:
            return
        if select_tmp is not None and not (self.tmp == select_tmp):
            return
        if self.name == "include":
            return
        result.append(
            object_locator(parent=parent, path=parent_path + self.name, object=self)
        )

    def get_without_substitution(self, path, alias_path=None):
        if self.is_disabled or (
            self.name != path and ((alias_path is None) or (self.name != alias_path))
        ):
            return []
        return [self]

    def _type_from_words(self):
        try:
            return self.type.from_words
        except AttributeError as e:
            raise RuntimeError(
                f".type=%s does not have a from_words method%s: {e.__class__.__name__}: {e!s}"
                % (str(self.type), self.where_str)
            )

    def try_extract(self):
        if self.type is None:
            return try_extract_proxy(
                error_message=None, extracted=strings_from_words(words=self.words)
            )
        type_from_words = self._type_from_words()
        try:
            return try_extract_proxy(
                error_message=None, extracted=type_from_words(self.words, master=self)
            )
        except RuntimeError as e:
            return try_extract_proxy(error_message=str(e), extracted=None)

    def extract(self, parent=None):
        """
        Extracts the Phil object definition into Python object.

        :param parent: Set parent Phil object
        :type parent:  freephil.scope
        :return: Python object
        :rtype: freephil.scope_extract

        """
        if self.type is None:
            return strings_from_words(words=self.words)
        return self._type_from_words()(self.words, master=self)

    def format(self, python_object):
        """
        Converts Python object into Phil object definition. It has to be called
        as a member function of the base Phil object definition to recover Phil metadata.

        :param python_object: Python object to be converted
        :type python_object: freephil.scope_extract
        :return: Phil definitio
        :rtype:  freephil.definition
        """
        if self.type is None:
            words = strings_as_words(python_object=python_object)
        else:
            try:
                type_as_words = self.type.as_words
            except AttributeError as e:
                raise RuntimeError(
                    f".type=%s does not have an as_words method%s: {e.__class__.__name__}: {e!s}"
                    % (str(self.type), self.where_str)
                )
            words = type_as_words(python_object=python_object, master=self)
        return self.customized_copy(words=words)

    def extract_format(self, source=None):
        """
        Performs extract-format of itself (or source)

        :param source: None, or a scope
        :type source: freephil.scope or None
        :return: Filtered scope by itself
        :rtype: freephil.scope
        """
        if source is None:
            source = self
        return self.format(python_object=source.extract())

    def try_extract_format(self):
        proxy = self.try_extract()
        if proxy.error_message is not None:
            return try_format_proxy(error_message=proxy.error_message, formatted=None)
        return try_format_proxy(
            error_message=None, formatted=self.format(python_object=proxy.extracted)
        )

    def try_tokenize(self, input_string, source_info=None):
        try:
            words = tokenize_value_literal(
                input_string=input_string, source_info=source_info
            )
        except RuntimeError as e:
            return try_tokenize_proxy(error_message=str(e), tokenized=None)
        if len(words) == 0:
            words = [tokenizer.word(value="None")]
        return try_tokenize_proxy(
            error_message=None, tokenized=self.customized_copy(words=words)
        )

    def _validate(self, input_string, source_info, call):
        proxy = self.try_tokenize(input_string=input_string, source_info=source_info)
        if proxy.error_message is not None:
            return proxy
        return getattr(proxy.tokenized, call)()

    def validate(self, input_string, source_info=None):
        return self._validate(
            input_string=input_string, source_info=source_info, call="try_extract"
        )

    def validate_and_format(self, input_string, source_info=None):
        return self._validate(
            input_string=input_string,
            source_info=source_info,
            call="try_extract_format",
        )

    def unique(self):
        return self

    def resolve_variables(self, diff_mode=False):
        new_words = []
        for word in self.words:
            if word.quote_token == "'":
                new_words.append(word)
                continue
            substitution_proxy = variable_substitution_proxy(word)
            for fragment in substitution_proxy.fragments:
                if not fragment.is_variable:
                    fragment.result = tokenizer.word(
                        value=fragment.value, quote_token='"'
                    )
                    continue
                variable_words = None
                if self.primary_parent_scope is not None:
                    substitution_source = self.primary_parent_scope.lexical_get(
                        path=fragment.value, stop_id=self.primary_id
                    )
                    if substitution_source is not None:
                        if not substitution_source.is_definition:
                            raise RuntimeError(
                                "Not a definition: $%s%s"
                                % (fragment.value, word.where_str())
                            )
                        substitution_source.tmp = True
                        variable_words = substitution_source.resolve_variables().words
                if variable_words is None:
                    if diff_mode:
                        env_var = "$" + fragment.value
                    else:
                        env_var = os.environ.get(fragment.value, None)
                    if env_var is not None:
                        variable_words = [
                            tokenizer.word(
                                value=env_var,
                                quote_token='"',
                                source_info='environment: "%s"' % fragment.value,
                            )
                        ]
                if variable_words is None:
                    raise RuntimeError(
                        f"Undefined variable: ${fragment.value}{word.where_str()}"
                    )
                if not substitution_proxy.force_string:
                    fragment.result = variable_words
                else:
                    fragment.result = tokenizer.word(
                        value=" ".join([word.value for word in variable_words]),
                        quote_token='"',
                    )
            new_words.extend(substitution_proxy.get_new_words())
        return self.customized_copy(words=new_words)


class scope_extract_call_proxy_object:
    def __init__(self, where_str, expression, callable, keyword_args):
        self.where_str = where_str
        self.expression = expression
        self.callable = callable
        self.keyword_args = keyword_args

    def __str__(self):
        return self.expression


def scope_extract_call_proxy(full_path, words, cache):
    if is_plain_none(words=words):
        return None
    if is_plain_auto(words=words):
        return freephil.Auto
    call_expression_raw = str_from_words(words).strip()
    try:
        call_expression = normalize_call_expression(expression=call_expression_raw)
    except python_tokenize.TokenError as e:
        raise RuntimeError(
            'scope "%s" .call=%s: %s%s'
            % (full_path, call_expression_raw, str(e), words[0].where_str())
        )
    call_proxy = cache.get(call_expression, None)
    if call_proxy is None:
        where_str = words[0].where_str()
        flds = call_expression.split("(", 1)
        import_path = flds[0]
        if len(flds) == 1:
            keyword_args = {}
        else:
            extractor = "__extract_args__(" + flds[1]
            try:
                args, keyword_args = eval(
                    extractor, math.__dict__, {"__extract_args__": extract_args}
                )
            except Exception as e:
                raise RuntimeError(
                    f'scope "%s" .call=%s: {e.__class__.__name__}: {e!s}%s'
                    % (full_path, call_expression, where_str)
                )
        imported = _import_python_object(
            import_path=import_path,
            error_prefix='scope "%s" .call: ' % full_path,
            target_must_be="; target must be a callable Python object",
            where_str=where_str,
        )
        if not callable(imported.object):
            raise TypeError(
                'scope "%s" .call: "%s" is not a callable Python object%s'
                % (full_path, import_path, where_str)
            )
        call_proxy = scope_extract_call_proxy_object(
            where_str=where_str,
            expression=call_expression,
            callable=imported.object,
            keyword_args=keyword_args,
        )
        cache[call_expression] = call_proxy
    return call_proxy


class scope_extract_attribute_error:
    pass


class scope_extract_is_disabled:
    pass


class scope_extract_list(list):
    def __init__(self, optional):
        self.__phil_optional__ = optional
        list.__init__(self)


class scope_extract:
    """
    Python object (see :ref:`python-object`). It is easy to access
    pythonic reprezentation of Phil object, but luckying metainformation,
    like expert_level. Further nested scopes and data are stored as
    attributes of the object.

    :ivar __phil_name__: Phil name
    :ivar __phil_parent__: parent object
    :ivar __phil_call__: function to be called, if the scope is callable
    """

    def __init__(self, name, parent, call):
        object.__setattr__(self, "__phil_name__", name)
        object.__setattr__(self, "__phil_parent__", parent)
        object.__setattr__(self, "__phil_call__", call)

    def __phil_path__(self, object_name=None):
        """
        Returns fully qualified path of the scope. If ``object_name``
        is given, path to the object is given

        :meta public:

        :param object_name: Object of the ``scope_extract``
        :type object_name: str
        :return: Fully qualified path
        :rtype: str


        """
        if (
            self.__phil_parent__ is None
            or self.__phil_parent__.__phil_name__ is None
            or self.__phil_parent__.__phil_name__ == ""
        ):
            if object_name is None:
                return self.__phil_name__
            elif self.__phil_name__ is None or self.__phil_name__ == "":
                return object_name
            return self.__phil_name__ + "." + object_name
        result = [self.__phil_parent__.__phil_path__(), self.__phil_name__]
        if object_name is not None:
            result.append(object_name)
        return ".".join(result)

    def __phil_path_and_value__(self, object_name):
        """
        Retruns fully qualified path of the object and its value

        :param object_name: Object of the ``scope_extract``
        :type object_name: str
        :return: Fully qualified name and object value
        :rtype: tuple
        """
        return (self.__phil_path__(object_name=object_name), getattr(self, object_name))

    def __setattr__(self, name, value):
        if (
            getattr(self, name, scope_extract_attribute_error)
            is scope_extract_attribute_error
        ):
            pp = self.__phil_path__()
            if pp == "":
                pp = name
            else:
                pp += "." + name
            raise AttributeError(
                'Assignment to non-existing attribute "%s"\n' % pp
                + "  Please correct the attribute name, or to create\n"
                + "  a new attribute use: obj.__inject__(name, value)"
            )
        object.__setattr__(self, name, value)

    def __inject__(self, name, value):
        """
        Creates new member object with ``name`` and ``value``

        :param name: Object name
        :type name:  str
        :param value: Object

        :raises AttributeError: When attribute already exists
        """
        if (
            getattr(self, name, scope_extract_attribute_error)
            is not scope_extract_attribute_error
        ):
            pp = self.__phil_path__()
            if pp == "":
                pp = name
            else:
                pp += "." + name
            raise AttributeError('Attribute "%s" exists already.' % pp)
        object.__setattr__(self, name, value)

    def __phil_join__(self, other):
        """
        Joins other object. The other object can have only subset of attributes

        :param other: Object to be joined in
        :type other: freephil.scope_extract
        """
        for key, other_value in other.__dict__.items():
            if is_reserved_identifier(key):
                continue
            self_value = self.__dict__.get(key, None)
            if self_value is None:
                self.__dict__[key] = other_value
            elif isinstance(self_value, scope_extract_list):
                assert isinstance(other_value, scope_extract_list)
                for item in other_value:
                    if item is not None:
                        self_value.append(item)
                if len(self_value) > 1 and self_value[0] is None:
                    del self_value[0]
            else:
                self_value_phil_join = getattr(self_value, "__phil_join__", None)
                if self_value_phil_join is None:
                    self.__dict__[key] = other_value
                else:
                    self_value_phil_join(other_value)

    def __phil_set__(self, name, optional, multiple, value):
        assert "." not in name
        node = getattr(self, name, scope_extract_attribute_error)
        if not multiple:
            if value is scope_extract_is_disabled:
                value = None
            if (
                node is scope_extract_attribute_error
                or not isinstance(value, scope_extract)
                or not isinstance(node, scope_extract)
            ):
                object.__setattr__(self, name, value)
            else:
                node.__phil_join__(value)
        else:
            if node is scope_extract_attribute_error:
                node = scope_extract_list(optional=optional)
                object.__setattr__(self, name, node)
            if value is not scope_extract_is_disabled and (
                value is not None or optional is not True
            ):
                node.append(value)

    def __phil_get__(self, name):
        assert "." not in name
        return getattr(self, name, scope_extract_attribute_error)

    def __call__(self, **keyword_args):
        call_proxy = self.__phil_call__
        if call_proxy is None:
            raise RuntimeError('scope "%s" is not callable.' % self.__phil_path__())
        if len(keyword_args) == 0:
            return call_proxy.callable(self, **call_proxy.keyword_args)
        effective_keyword_args = dict(call_proxy.keyword_args)
        effective_keyword_args.update(keyword_args)
        try:
            return call_proxy.callable(self, **effective_keyword_args)
        except Exception as e:
            raise RuntimeError(
                f'scope "%s" .call=%s execution: {e.__class__.__name__}: {e!s}%s'
                % (
                    self.__phil_path__(),
                    call_proxy.expression,
                    call_proxy.where_str,
                )
            )


class scope(slots_getstate_setstate):
    """
    Phil object. It should not be created by an user directly, but
    usually by parsing Phil string (see: :func:`freephil.parse`)

    :ivar objects: Actual items of the scope, can be itterated over.
    :vartype objects: list of freephil.scope or freephil.definition

    .. note::
       Nesting depth of the scope is limited by Python recursion limit
       (default 1000).

    Attributes possible from parsing Phil string/file. Attribute levels
    are:

    1. level: ``help`` and ``alias``
    2. level: everything, whose value is not None
    3. level: everything else

    :ivar help: Help entry for the parameter
    :vartype help: str
    :ivar caption: Caption
    :vartype caption: str
    :ivar short_caption: Short caption
    :vartype shot_caption: str
    :ivar optional: Is optional?
    :vartype optional: bool
    :ivar type: Type (see :ref:`phil-type`)
    :ivar multiple: Possible mltiple times? (see :ref:`phil-multiple`)
    :vartype multiple: bool
    :ivar input_size: Input size
    :ivar style:
    :ivar call: A function, if the scope should be callable
    :vartype call: function
    :ivar sequential_format:
    :ivar disable_add:
    :ivar disable_delete:
    :ivar expert_level: Expert level
    :vartype expert_level: int
    :ivar deprecated:
    :ivar alias: Alias

    Other class variables:

    :cvar is_definition: Always ``True``
    :vartype is_definition: bool
    :cvar is_scope: Always ``False``
    :vartype is_scope: bool

    Other instance variables:

    :ivar name:
    :ivar primary_id:
    :ivar primary_parent_scope: Parent scope
    :vartype primary_parent_scope: freephil.scope
    :ivar is_disabled:
    :ivar is_template:
    :ivar where_str:
    :ivar merge_names:
    """

    is_definition = False
    is_scope = True
    deprecated = False

    attribute_names = [
        "style",
        "help",
        "caption",
        "short_caption",
        "optional",
        "call",
        "multiple",
        "sequential_format",
        "disable_add",
        "disable_delete",
        "expert_level",
        "alias",
    ]

    __slots__ = [
        "name",
        "objects",
        "primary_id",
        "primary_parent_scope",
        "is_disabled",
        "is_template",
        "where_str",
        "merge_names",
    ] + attribute_names

    def __init__(
        self,
        name,
        objects=None,
        primary_id=None,
        primary_parent_scope=None,
        is_disabled=False,
        is_template=0,
        where_str="",
        merge_names=False,
        style=None,
        help=None,
        caption=None,
        short_caption=None,
        optional=None,
        call=None,
        multiple=None,
        sequential_format=None,
        disable_add=None,
        disable_delete=None,
        expert_level=None,
        alias=None,
    ):
        self.name = name
        self.objects = objects
        self.primary_id = primary_id
        self.primary_parent_scope = primary_parent_scope
        self.is_disabled = is_disabled
        self.is_template = is_template
        self.where_str = where_str
        self.merge_names = merge_names
        self.style = style
        self.help = help
        self.caption = caption
        self.short_caption = short_caption
        self.optional = optional
        self.call = call
        self.multiple = multiple
        self.sequential_format = sequential_format
        self.disable_add = disable_add
        self.disable_delete = disable_delete
        self.expert_level = expert_level
        self.alias = alias
        if objects is None:
            self.objects = []
        if is_reserved_identifier(name):
            raise RuntimeError(f'Reserved identifier: "{name}"{where_str}')
        if "include" in name.split("."):
            raise RuntimeError('Reserved identifier: "include"%s' % where_str)
        if sequential_format is not None:
            assert isinstance(sequential_format % 0, str)

    def copy(self):
        """
        Copy the object

        :rtype: freephil.scope
        """
        keyword_args = {}
        for keyword in self.__slots__:
            keyword_args[keyword] = getattr(self, keyword)
        return scope(**keyword_args)

    def customized_copy(self, name=None, objects=None):
        """
        Customized object copy, changing name of the object and
        sets new objects.

        :param name: New object name
        :type name: str
        :param objects: New objects
        :return: Customized object copy
        :rtype: freephil.scope
        """
        result = self.copy()
        if name is not None:
            result.name = name
        if objects is not None:
            result.objects = objects
        result.is_template = 0
        return result

    def is_empty(self):
        """
        :return: True, if object is empty
        :rtype: bool
        """
        return len(self.objects) == 0

    def full_path(self):
        """
        Retuns full path to the scope as a string

        :rtype: str
        """
        return full_path(self)

    def alias_path(self):
        """
        Get path alias

        :rtype: str
        """
        return alias_path(self)

    def assign_tmp(self, value, active_only=False):
        if not active_only:
            for object in self.objects:
                object.assign_tmp(value=value)
        else:
            for object in self.objects:
                if self.is_disabled:
                    continue
                object.assign_tmp(value=value, active_only=True)

    def adopt(self, object):
        assert len(object.name) > 0
        primary_parent_scope = self
        name_components = object.name.split(".")
        merge_names = False
        for name in name_components[:-1]:
            child_scope = scope(name=name)
            child_scope.merge_names = merge_names
            primary_parent_scope.adopt(child_scope)
            primary_parent_scope = child_scope
            merge_names = True
        if len(name_components) > 1:
            object.name = name_components[-1]
            object.merge_names = True
        object.primary_parent_scope = primary_parent_scope
        primary_parent_scope.objects.append(object)

    def adopt_scope(self, other):
        """
        Makes other scope member of this parent scope

        :param other: scope to be adopted
        :type other: freephil.scope or object
        """
        assert self is not other, "Cannot adopt own scope"
        for active_object in other.active_objects():
            results = self.get_without_substitution(active_object.full_path())
            if len(results) == 0:
                self.adopt(active_object)
                continue
            for result in results:
                assert result.is_scope == active_object.is_scope
                if result.is_definition:
                    # This parameter is defined in both phil scopes: replace definition
                    # in self with the definition in other.
                    primary_parent_scope = result.primary_parent_scope
                    i = primary_parent_scope.objects.index(result)
                    primary_parent_scope.objects[i] = active_object
                    del result
                else:
                    result.adopt_scope(active_object)

    def change_primary_parent_scope(self, new_value):
        """
        Changes primary parent scope

        :param new_value: New parent scope
        :type new_value: freephil.scope
        :return: Copy of itself with new primary parent
        """

        objects = []
        for object in self.objects:
            obj = object.copy()
            obj.primary_parent_scope = new_value
            if obj.is_scope:
                obj = obj.change_primary_parent_scope(obj)
            objects.append(obj)
        return self.customized_copy(objects=objects)

    def has_attribute_with_name(self, name):
        """
        Checks for argument presence

        :param name: Argument being checked
        :return: True, if attribute exists in the scope
        :rtype: bool
        """
        return name in self.attribute_names

    def assign_attribute(self, name, words, scope_extract_call_proxy_cache):
        assert self.has_attribute_with_name(name)
        if name in ["optional", "multiple", "disable_add", "disable_delete"]:
            value = bool_from_words(words, path="." + name)
        elif name == "expert_level":
            value = int_from_words(words=words, path="." + name)
        elif name == "call":
            value = scope_extract_call_proxy(
                full_path=self.full_path(),
                words=words,
                cache=scope_extract_call_proxy_cache,
            )
        else:
            value = str_from_words(words)
            if name == "style":
                style = value
            elif name == "sequential_format":
                sequential_format = value
                if sequential_format is not None:
                    assert isinstance(sequential_format % 0, str)
        setattr(self, name, value)

    def active_objects(self):
        """
        Iterator over active objects
        """
        for object in self.objects:
            if object.is_disabled:
                continue
            yield object

    def master_active_objects(self):
        names_object = {}
        for object in self.objects:
            if object.is_disabled:
                continue
            master = names_object.setdefault(object.name, object)
            if master is not object:
                if master.multiple:
                    continue
                if object.is_definition:
                    raise RuntimeError(
                        "Duplicate definitions in master"
                        " (first not marked with .multiple=True):\n"
                        "  %s%s\n"
                        "  %s%s"
                        % (
                            master.full_path(),
                            master.where_str,
                            object.full_path(),
                            object.where_str,
                        )
                    )
            yield object

    def show(
        self,
        out=None,
        merged_names=[],
        prefix="",
        expert_level=None,
        attributes_level=0,
        print_width=None,
    ):
        """
        Pretty prints the Phil object

        :param out: If None, prints to ``sys.stdout``, else to the file. The
                    file has to be opened for writing.
        :type out: None or file
        :param merged_names:
        :param prefix: Prefix
        :param expert_level: Expert verbosity
        :type expert_level:  int
        :param attributes_level: Attributes verbosity
        :type attributes_level:  int
        :param print_width: Max. line width
        :type print_width:  int
        :return:
        """
        if self.is_template < 0 and attributes_level < 2:
            return
        if (
            self.expert_level is not None
            and expert_level is not None
            and expert_level >= 0
            and self.expert_level > expert_level
        ):
            return
        if out is None:
            out = sys.stdout
        if print_width is None:
            print_width = default_print_width
        is_proper_scope = False
        if len(self.name) == 0:
            assert len(merged_names) == 0
        elif len(self.objects) > 0 and self.objects[0].merge_names:
            merged_names = merged_names + [self.name]
        else:
            is_proper_scope = True
            if self.is_disabled:
                hash = "!"
            else:
                hash = ""
            out_attributes = io.StringIO()
            show_attributes(
                self=self,
                out=out_attributes,
                prefix=prefix,
                attributes_level=attributes_level,
                print_width=print_width,
            )
            out_attributes = out_attributes.getvalue()
            merged_name = ".".join(merged_names + [self.name])
            merged_names = []
            if len(out_attributes) == 0:
                print(prefix + hash + merged_name, "{", file=out)
            else:
                print(prefix + hash + merged_name, file=out)
                out.write(out_attributes)
                print(prefix + "{", file=out)
            prefix += "  "
        for object in self.objects:
            object.show(
                out=out,
                merged_names=merged_names,
                prefix=prefix,
                expert_level=expert_level,
                attributes_level=attributes_level,
                print_width=print_width,
            )
        if is_proper_scope:
            print(prefix[:-2] + "}", file=out)

    def as_str(
        self, prefix="", expert_level=None, attributes_level=0, print_width=None
    ):
        """
        Returns pretty print as a string.

        :param prefix: Prefix
        :param expert_level: Expert verbosity
        :type expert_level:  int
        :param attributes_level: Attributes verbosity
        :type attributes_level:  int
        :param print_width: Max. line width
        :type print_width:  int
        :rtype: str
        """
        out = io.StringIO()
        self.show(
            out=out,
            prefix=prefix,
            expert_level=expert_level,
            attributes_level=attributes_level,
            print_width=print_width,
        )
        return out.getvalue()

    def _all_definitions(
        self, suppress_multiple, select_tmp, parent, parent_path, result
    ):
        parent_path += self.name + "."
        for object in self.active_objects():
            if suppress_multiple and object.multiple:
                continue
            object._all_definitions(
                suppress_multiple=suppress_multiple,
                select_tmp=select_tmp,
                parent=self,
                parent_path=parent_path,
                result=result,
            )

    def all_definitions(self, suppress_multiple=False, select_tmp=None):
        result = []
        for object in self.active_objects():
            if suppress_multiple and object.multiple:
                continue
            object._all_definitions(
                suppress_multiple=suppress_multiple,
                select_tmp=select_tmp,
                parent=self,
                parent_path="",
                result=result,
            )
        return result

    def get_without_substitution(self, path, alias_path=None):
        if self.is_disabled:
            return []
        if len(self.name) == 0:
            if len(path) == 0:
                return self.objects
        elif (self.name == path) or (self.name == alias_path):
            return [self]
        elif path.startswith(self.name + "."):
            path = path[len(self.name) + 1 :]
        elif alias_path is not None:
            full_path = self.full_path()
            if full_path.startswith(alias_path):
                path = path[len(self.name) + 1 :]
        else:
            return []
        result = []
        for object in self.active_objects():
            result.extend(
                object.get_without_substitution(path=path, alias_path=alias_path)
            )
        return result

    def get(self, path, with_substitution=True, alias_path=None):
        result = scope(
            name="",
            objects=self.get_without_substitution(path=path, alias_path=alias_path),
        )
        if not with_substitution:
            return result
        return result.resolve_variables()

    def resolve_variables(self):
        result = []
        for object in self.active_objects():
            result.append(object.resolve_variables())
        return self.customized_copy(objects=result)

    def lexical_get(self, path, stop_id, search_up=True):
        if path.startswith("."):
            while self.primary_parent_scope is not None:
                self = self.primary_parent_scope
            path = path[1:]
        candidates = []
        for object in self.objects:
            if object.primary_id is not None and object.primary_id >= stop_id:
                break
            if object.is_definition:
                if object.name == path:
                    candidates.append(object)
            elif object.name == path or path.startswith(object.name + "."):
                candidates.append(object)
        while len(candidates) > 0:
            object = candidates.pop()
            if object.name == path:
                return object
            object = object.lexical_get(
                path=path[len(object.name) + 1 :], stop_id=stop_id, search_up=False
            )
            if object is not None:
                return object
        if not search_up:
            return None
        if self.primary_parent_scope is None:
            return None
        return self.primary_parent_scope.lexical_get(path=path, stop_id=stop_id)

    def extract(self, parent=None):
        """
        Extracts the Phil object into Python object.

        :param parent: Set parent Phil object
        :type parent:  freephil.scope
        :return: Python object
        :rtype: freephil.scope_extract
        """
        result = scope_extract(name=self.name, parent=parent, call=self.call)
        for object in self.objects:
            if object.is_template < 0:
                continue
            if object.is_disabled or object.is_template > 0:
                value = scope_extract_is_disabled
            else:
                value = object.extract(parent=result)
            result.__phil_set__(
                name=object.name,
                optional=object.optional,
                multiple=object.multiple,
                value=value,
            )
        return result

    def format(self, python_object):
        """
        Converts Python object into Phil object. It has to be called
        as a member function of the base Phil object to recover Phil metadata.

        :param python_object: Python object to be converted
        :type python_object: freephil.scope_extract
        :return: Phil object
        :rtype:  freephil.scope
        """
        multiple_scopes_done = {}
        result = []
        for object in self.master_active_objects():
            if object.multiple and object.is_scope:
                if object.name in multiple_scopes_done:
                    continue
                multiple_scopes_done[object.name] = False
            if python_object is None:
                result.append(object.format(None))
            elif (python_object is freephil.Auto) or (
                isinstance(python_object, type(freephil.Auto))
            ):
                result.append(object.format(freephil.Auto))
            else:
                if isinstance(python_object, scope_extract):
                    python_object = [python_object]
                for python_object_i in python_object:
                    sub_python_object = python_object_i.__phil_get__(object.name)
                    if sub_python_object is not scope_extract_attribute_error:
                        if not object.multiple:
                            result.append(object.format(sub_python_object))
                        else:
                            if len(sub_python_object) == 0:
                                obj = object.copy()
                                obj.is_template = 1
                                result.append(obj)
                            else:
                                if not multiple_scopes_done.get(object.name, True):
                                    multiple_scopes_done[object.name] = True
                                    obj = object.copy()
                                    obj.is_template = -1
                                    result.append(obj)
                                for sub_python_object_i in sub_python_object:
                                    result.append(object.format(sub_python_object_i))
        return self.customized_copy(objects=result)

    def extract_format(self, source=None):
        """
        Performs extract-format of itself (or source)

        :param source: None, or a scope
        :type source: freephil.scope or None
        :return: Filtered scope by itself
        :rtype: freephil.scope
        """
        if source is None:
            source = self
        return self.format(source.extract())

    def clone(self, python_object, converter_registry=None):
        """
        Clones Python object to new one, filtered through this scope.

        :param python_object: Input Python object
        :type python_object: freephil.scope_extract
        :param converter_registry:
        :return: Filtered Python object
        :rtype: freephil.scope_extract
        """
        return parse(
            input_string=self.format(python_object=python_object).as_str(
                attributes_level=3
            ),
            converter_registry=converter_registry,
        ).extract()

    def fetch(
        self,
        source=None,
        sources=None,
        track_unused_definitions=False,
        diff=False,
        skip_incompatible_objects=False,
    ):
        """
        Combine multiple Phil objects using the base Phil (``self``).
        Returns full Phil object with changes from ``sources`` applied.
        If an arguments occurs multiple times in different sources,
        the first from the list is used. For more details see
        :ref:`phil-fetch`.

        :param source: Input Phil object
        :type source: freephil.scope
        :param sources: Multiple input Phil objects
        :type sources: list of freephil.scope
        :param track_unused_definitions: If ``True``, the function
               returns a tuple, where second member contains entries
               not used in base Phil object
               (see: :ref:`track-unused-definitions`)
        :type track_unused_definitions: bool
        :param diff: If ``True``, equivalent to ``fetch_diff()``
        :type diff: bool
        :param skip_incompatible_objects: Skip incompatible object types
        :type skip_incompatible_objects: bool
        :return: Phil object, or Phil object and object with unprocessed data
        :rtype: freephil.scope or tuple(freephil.scope, list of freephil.object_locator)
        """
        combined_objects = []
        if source is not None or sources is not None:
            assert source is None or sources is None
            combined_objects = []
            if sources is None:
                sources = [source]
            for source in sources:
                assert source.name == self.name
                if source.is_definition:
                    if skip_incompatible_objects:
                        continue
                    raise RuntimeError(
                        "Incompatible parameter objects:"
                        ' scope "%s"%s vs. definition "%s"%s'
                        % (self.name, self.where_str, source.name, source.where_str)
                    )
                combined_objects.extend(source.objects)
        source = self.customized_copy(objects=combined_objects)
        del sources
        if track_unused_definitions:
            source.assign_tmp(value=False, active_only=True)
        result_objects = []
        for master_object in self.master_active_objects():
            if len(self.name) == 0:
                path = master_object.name
            else:
                path = self.name + "." + master_object.name
            alias_path = master_object.alias_path()
            matching_sources = source.get(
                path=path, with_substitution=False, alias_path=alias_path
            )
            if not master_object.multiple:
                if master_object.is_definition:
                    # loop over all matching_sources to support track_unused_definitions
                    result_object = None
                    for matching_source in matching_sources.active_objects():
                        result_object = master_object.fetch(
                            source=matching_source,
                            diff=diff,
                            skip_incompatible_objects=skip_incompatible_objects,
                        )
                else:
                    result_object = master_object.fetch(
                        sources=matching_sources.active_objects(),
                        diff=diff,
                        skip_incompatible_objects=skip_incompatible_objects,
                    )
                    if diff and len(result_object.objects) == 0:
                        result_object = None
                if result_object is not None:
                    result_objects.append(result_object)
                elif (not diff) and (not master_object.deprecated):
                    result_objects.append(master_object.copy())
            else:
                processed_as_str = {}
                result_objs = []
                master_as_str = master_object.extract_format().as_str()
                for from_master, matching in [
                    (True, self.get(path=path, with_substitution=False)),
                    (False, matching_sources),
                ]:
                    for matching_source in matching.active_objects():
                        if matching_source is master_object:
                            continue
                        candidate = master_object.fetch(
                            source=matching_source,
                            diff=diff,
                            skip_incompatible_objects=skip_incompatible_objects,
                        )
                        if diff:
                            if master_object.is_scope:
                                if len(candidate.objects) == 0:
                                    continue
                            elif candidate is None:
                                continue
                        candidate_as_str = master_object.extract_format(
                            source=candidate
                        ).as_str()
                        if candidate_as_str == master_as_str:
                            continue
                        prev_index = processed_as_str.get(candidate_as_str, None)
                        if prev_index is not None:
                            if prev_index == -1:
                                continue
                            result_objs[prev_index] = None
                        if diff and from_master:
                            processed_as_str[candidate_as_str] = -1
                        else:
                            processed_as_str[candidate_as_str] = len(result_objs)
                            result_objs.append(candidate)
                if not diff:
                    obj = master_object.copy()
                    if (
                        master_object.optional is not None
                        and not master_object.optional
                    ):
                        obj.is_template = 0
                    elif len(processed_as_str) == 0:
                        obj.is_template = 1
                    else:
                        obj.is_template = -1
                    result_objects.append(obj)
                del processed_as_str
                for obj in result_objs:
                    if obj is not None:
                        result_objects.append(obj)
                del result_objs
        result = self.customized_copy(objects=result_objects)
        if track_unused_definitions:
            return result, source.all_definitions(select_tmp=False)
        return result

    def fetch_diff(
        self,
        source=None,
        sources=None,
        track_unused_definitions=False,
        skip_incompatible_objects=False,
    ):
        """
        Creates difference Phil object containing only items, which
        differ between the base Phil object and source(s).

        :param source: Input Phil object
        :type source: freephil.scope
        :param sources: Multiple input Phil objects
        :type sources: list of freephil.scope
        :param track_unused_definitions: If ``True``, the function
               returns a tuple, where second member contains entries
               not used in base Phil object
               (see: :ref:`track-unused-definitions`)
        :type track_unused_definitions: bool
        :param diff: If ``True``, equivalent to ``fetch_diff()``
        :type diff: bool
        :param skip_incompatible_objects: Skip incompatible object types
        :type skip_incompatible_objects: bool
        :return: Phil object, or Phil object and object with unprocessed data
        :rtype: freephil.scope or tuple(freephil.scope, list of freephil.object_locator)
        """
        return self.fetch(
            source=source,
            sources=sources,
            track_unused_definitions=track_unused_definitions,
            diff=True,
            skip_incompatible_objects=skip_incompatible_objects,
        )

    def process_includes(
        self, converter_registry, reference_directory, include_stack=None
    ):
        """
        Manually triggers processing of :ref:`phil-includes`

        :param converter_registry:
        :param reference_directory:
        :param include_stack:
        """
        if converter_registry is None:
            converter_registry = default_converter_registry
        if include_stack is None:
            include_stack = []
        result = []
        for object in self.objects:
            if object.is_disabled:
                result.append(object)
            elif object.is_definition:
                if object.name != "include":
                    result.append(object)
                else:
                    object_sub = object.resolve_variables()
                    if len(object_sub.words) < 2:
                        raise RuntimeError(
                            '"include" must be followed by at least two arguments%s'
                            % (object.where_str)
                        )
                    include_type = object_sub.words[0].value.lower()
                    if include_type == "file":
                        if len(object_sub.words) != 2:
                            raise RuntimeError(
                                '"include file" must be followed exactly one argument%s'
                                % (object.where_str)
                            )
                        file_name = object_sub.words[1].value
                        if reference_directory is not None and not os.path.isabs(
                            file_name
                        ):
                            file_name = os.path.join(reference_directory, file_name)
                        result.extend(
                            parse(
                                file_name=file_name,
                                converter_registry=converter_registry,
                                process_includes=True,
                                include_stack=include_stack,
                            ).objects
                        )
                    elif include_type == "scope":
                        if len(object_sub.words) > 3:
                            raise RuntimeError(
                                '"include scope" must be followed one or two arguments,'
                                " i.e. an import path and optionally a phil path%s"
                                % (object.where_str)
                            )
                        import_path = object_sub.words[1].value
                        if len(object_sub.words) > 2:
                            phil_path = object_sub.words[2].value
                        else:
                            phil_path = None
                        result.extend(
                            process_include_scope(
                                converter_registry=converter_registry,
                                include_stack=include_stack,
                                object=object,
                                import_path=import_path,
                                phil_path=phil_path,
                            ).objects
                        )
                    else:
                        raise RuntimeError(
                            "Unknown include type: %s%s"
                            % (include_type, object.where_str)
                        )
            else:
                result.append(
                    object.process_includes(
                        converter_registry=converter_registry,
                        reference_directory=reference_directory,
                        include_stack=include_stack,
                    )
                )
        return self.customized_copy(objects=result)

    def unique(self):
        selection = {}
        result = []
        for i_object, object in enumerate(self.active_objects()):
            selection[object.name] = i_object
        for i_object, object in enumerate(self.active_objects()):
            if selection[object.name] == i_object:
                result.append(object.unique())
        return self.customized_copy(objects=result)

    def command_line_argument_interpreter(
        self, home_scope=None, argument_description=None
    ):
        """
        Creates an interpreter of command line arguments for the scope

        :param home_scope: Parse only within sub-scope
        :type home_scope: freephil.scope
        :param argument_description: Description of arguments source.
               Defaults "command line"
        :type argument_description: str
        :return: Command line interpreter
        :rtype: freephil.command_line.argument_interpreter
        """

        from freephil.command_line import argument_interpreter as _

        return _(
            master_phil=self,
            home_scope=home_scope,
            argument_description=argument_description,
        )


def process_include_scope(
    converter_registry, include_stack, object, import_path, phil_path
):
    imported = _import_python_object(
        import_path=import_path,
        error_prefix="include scope: ",
        target_must_be="; target must be a phil scope object or phil string",
        where_str=object.where_str,
    )
    source_scope = imported.object
    if isinstance(source_scope, str):
        source_scope = parse(
            input_string=source_scope, converter_registry=converter_registry
        )
    elif hasattr(source_scope, "__call__"):
        source_scope = source_scope()
    elif source_scope is None or not isinstance(source_scope, scope):
        if getattr(source_scope, "is_scope", None):
            # Likely a libtbx phil scope, so attempt to convert
            # this to something sensible
            source_scope = adapter.read_libtbx_scope(source_scope)
        else:
            raise RuntimeError(
                'include scope: python object "%s" in module "%s" is not a'
                " freephil.scope instance%s"
                % (imported.path_elements[-1], imported.module_path, object.where_str)
            )
    source_scope = source_scope.process_includes(
        converter_registry=converter_registry,
        reference_directory=None,
        include_stack=include_stack,
    )
    if phil_path is None:
        result = source_scope
    else:
        result = source_scope.get(path=phil_path)
        if len(result.objects) == 0:
            raise RuntimeError(
                'include scope: path "%s" not found in phil scope object "%s"'
                ' in module "%s"%s'
                % (
                    phil_path,
                    imported.path_elements[-1],
                    imported.module_path,
                    object.where_str,
                )
            )
    return result.change_primary_parent_scope(object.primary_parent_scope)


class variable_substitution_fragment(slots_getstate_setstate):

    __slots__ = ["is_variable", "value", "result"]

    def __init__(self, is_variable, value):
        self.is_variable = is_variable
        self.value = value


class variable_substitution_proxy(slots_getstate_setstate):

    __slots__ = ["word", "force_string", "have_variables", "fragments"]

    def __init__(self, word):
        self.word = word
        self.force_string = word.quote_token is not None
        self.have_variables = False
        self.fragments = []
        fragment_value = ""
        char_iter = tokenizer.character_iterator(word.value)
        c = next(char_iter)
        while c is not None:
            if c != "$":
                fragment_value += c
                if c == "\\" and char_iter.look_ahead_1() == "$":
                    fragment_value += next(char_iter)
                c = next(char_iter)
            else:
                self.have_variables = True
                if len(fragment_value) > 0:
                    self.fragments.append(
                        variable_substitution_fragment(
                            is_variable=False, value=fragment_value
                        )
                    )
                    fragment_value = ""
                c = next(char_iter)
                if c is None:
                    word.raise_syntax_error("$ must be followed by an identifier: ")
                if c == "(":
                    while True:
                        c = next(char_iter)
                        if c is None:
                            word.raise_syntax_error('missing ")": ')
                        if c == ")":
                            c = next(char_iter)
                            break
                        fragment_value += c
                    offs = int(fragment_value.startswith("."))
                    if not is_standard_identifier(fragment_value[offs:]):
                        word.raise_syntax_error("improper variable name ")
                    self.fragments.append(
                        variable_substitution_fragment(
                            is_variable=True, value=fragment_value
                        )
                    )
                else:
                    if c not in standard_identifier_start_characters:
                        word.raise_syntax_error("improper variable name ")
                    fragment_value = c
                    while True:
                        c = next(char_iter)
                        if c is None:
                            break
                        if c == ".":
                            break
                        if c not in standard_identifier_continuation_characters:
                            break
                        fragment_value += c
                    self.fragments.append(
                        variable_substitution_fragment(
                            is_variable=True, value=fragment_value
                        )
                    )
                fragment_value = ""
        if len(fragment_value) > 0:
            self.fragments.append(
                variable_substitution_fragment(is_variable=False, value=fragment_value)
            )
        if len(self.fragments) > 1:
            self.force_string = True

    def get_new_words(self):
        if not self.have_variables:
            return [self.word]
        if not self.force_string:
            return self.fragments[0].result
        return [
            tokenizer.word(
                value="".join([fragment.result.value for fragment in self.fragments]),
                quote_token='"',
            )
        ]


def parse(
    input_string=None,
    source_info=None,
    file_name=None,
    converter_registry=None,
    process_includes=False,
    include_stack=None,
):
    """Creates Phil object from a string or a file

    :param input_string: String to be parsed
    :param source_info: Description of the source. Defaults to `file_name`
    :param file_name:  Parse from a file
    :param converter_registry: Custom converters (see :ref:`extending-phil`)
    :param process_includes: Enables processing `include` statement
    :param include_stack:
    :return: Phil object
    :rtype: freephil.scope
    """
    assert source_info is None or file_name is None
    if input_string is None:
        assert file_name is not None
        with open(file_name, encoding="utf-8", errors="ignore") as f:
            input_string = f.read()
    if converter_registry is None:
        converter_registry = default_converter_registry
    result = scope(name="", primary_id=0)
    parser.collect_objects(
        word_iterator=tokenizer.word_iterator(
            input_string=input_string,
            source_info=source_info,
            file_name=file_name,
            list_of_settings=[
                tokenizer.settings(
                    unquoted_single_character_words="{}=",
                    contiguous_word_characters="",
                    comment_characters="#",
                    meta_comment="phil",
                ),
                tokenizer.settings(
                    unquoted_single_character_words="{};", contiguous_word_characters=""
                ),
            ],
        ),
        converter_registry=converter_registry,
        primary_id_generator=count(1),
        primary_parent_scope=result,
    )
    if process_includes:
        if file_name is None:
            file_name_normalized = None
            reference_directory = None
        else:
            file_name_normalized = os.path.normpath(os.path.abspath(file_name))
            reference_directory = os.path.dirname(file_name_normalized)
            if include_stack is None:
                include_stack = []
            elif file_name_normalized in include_stack:
                raise RuntimeError(
                    "Include dependency cycle: %s"
                    % ", ".join(include_stack + [file_name_normalized])
                )
            include_stack.append(file_name_normalized)
        result = result.process_includes(
            converter_registry=converter_registry,
            reference_directory=reference_directory,
            include_stack=include_stack,
        )
        if include_stack is not None:
            include_stack.pop()
    return result


def read_default(
    caller_file_name,
    params_extension=".params",
    converter_registry=None,
    process_includes=True,
):
    params_file_name = os.path.splitext(caller_file_name)[0] + params_extension
    if not os.path.isfile(params_file_name):
        raise RuntimeError("Missing parameter file: %s" % params_file_name)
    return parse(
        file_name=params_file_name,
        converter_registry=converter_registry,
        process_includes=process_includes,
    )


def process_command_line(args, master_string, parse=None):
    """
    Processes command line arguments

    :param args: command line arguments
    :type  args: list of strings
    :param master_string: Phil string; the string is parsed internally
    :type  master_string: str
    :param parse: function to parse ``master_string``. Defaults to
                  :class:`freephil.parse`
    :return: Parsed arguments
    :rtype: freephil.command_line.process
    """
    from freephil import command_line

    return command_line.process(args=args, master_string=master_string, parse=parse)


def find_scope(current_phil, scope_name):
    """
    Finds first occurence of scope within a scope

    :param current_phil: Phil object to be searched
    :type current_phil:  freephil.scope
    :param scope_name: Scope name to be searched for
    :return: First scope occurence
    :rtype: freephil.scope
    """
    i = 0
    while i < len(current_phil.objects):
        full_path = current_phil.objects[i].full_path()
        if full_path == scope_name:
            return current_phil.objects[i]
        elif scope_name.startswith(full_path + "."):
            return find_scope(current_phil.objects[i], scope_name)
        i += 1

    # Should report nothing found?


def change_default_phil_values(
    master_phil_str,
    new_default_phil_str,
    phil_parse=None,
    expert_level=4,
    attributes_level=4,
):
    """
    Function for updating the default values in a PHIL scope

    :param master_phil_str:
    :type master_phil_str:  str
    :param new_default_phil_str:
    :type new_default_phil_str:  str
    :param phil_parse: function for parsing PHIL
                      (optional, defaults to freephil.parse)
    :type phil_parse: function
    :param expert_level: optional, defaults to 4
    :type expert_level: int
    :param attributes_level: optional, defaults to 4
    :type attributes_level: int
    :return: the master_phil_str with the updated default values
    :rtype: str
    :raise Sorry: if unrecognized PHIL parameters are encountered
    :raise RuntimeError: if new value cannot be interpreted (e.g str instead of float)
    """

    if phil_parse is None:
        phil_parse = parse

    master_phil = phil_parse(master_phil_str, process_includes=True)
    new_phil, unused_phil = master_phil.fetch(
        phil_parse(new_default_phil_str, process_includes=True),
        track_unused_definitions=True,
    )
    if len(unused_phil) > 0:
        raise freephil.Sorry(
            "Unrecognized PHIL parameter(s)\n%s"
            % "\n".join([p.__str__() for p in unused_phil])
        )
    new_phil_extract = new_phil.extract()
    modified_phil = master_phil.format(python_object=new_phil_extract)

    return modified_phil.as_str(
        expert_level=expert_level, attributes_level=attributes_level
    )
