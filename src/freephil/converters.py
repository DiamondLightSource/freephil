# Content in this file falls under the libtbx license

import math
import os

import freephil

from . import tokenizer
from .tokens import (
    is_plain_auto,
    is_plain_none,
    is_standard_identifier,
    tokenize_value_literal,
)


class words_converters:

    phil_type = "words"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        if is_plain_none(words=words):
            return None
        if is_plain_auto(words=words):
            return freephil.Auto
        return words

    def as_words(self, python_object, master):
        if python_object is None:
            return [tokenizer.word(value="None")]
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        for word in python_object:
            assert isinstance(word, tokenizer.word)
        return python_object


def strings_from_words(words):
    if is_plain_none(words=words):
        return None
    if is_plain_auto(words=words):
        return freephil.Auto
    return [word.value for word in words]


def strings_as_words(python_object):
    if python_object is None:
        return [tokenizer.word(value="None")]
    if (python_object is freephil.Auto) or (
        isinstance(python_object, type(freephil.Auto))
    ):
        return [tokenizer.word(value="Auto")]
    words = []
    for value in python_object:
        if is_standard_identifier(value):
            words.append(tokenizer.word(value=value))
        else:
            words.append(tokenizer.word(value=value, quote_token='"'))
    return words


class strings_converters:

    phil_type = "strings"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        return strings_from_words(words)

    def as_words(self, python_object, master):
        return strings_as_words(python_object)


def str_from_words(words):
    if is_plain_none(words=words):
        return None
    if is_plain_auto(words=words):
        return freephil.Auto
    return " ".join([word.value for word in words])


class str_converters:

    phil_type = "str"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        return str_from_words(words=words)

    def as_words(self, python_object, master):
        if python_object is None:
            return [tokenizer.word(value="None")]
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        return [tokenizer.word(value=python_object, quote_token='"')]


class qstr_converters:

    phil_type = "qstr"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        if is_plain_none(words=words):
            return None
        if is_plain_auto(words=words):
            return freephil.Auto
        return " ".join([str(word) for word in words])

    def as_words(self, python_object, master):
        if python_object is None:
            return [tokenizer.word(value="None")]
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        return tokenize_value_literal(
            input_string=python_object, source_info="python_object"
        )


class path_converters(str_converters):

    phil_type = "path"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        path = str_from_words(words=words)
        if path not in (None, freephil.Auto):
            path = os.path.expanduser(path)
        return path


class key_converters(str_converters):

    phil_type = "key"

    def __str__(self):
        return self.phil_type


def bool_from_words(words, path):
    value_string = str_from_words(words)
    if value_string is None:
        return None
    if value_string is freephil.Auto:
        return freephil.Auto
    value_lower = value_string.lower()
    if value_lower in ["false", "no", "off", "0"]:
        return False
    if value_lower in ["true", "yes", "on", "1"]:
        return True
    assert len(words) > 0
    raise RuntimeError(
        'One True or False value expected, %s="%s" found%s'
        % (path, value_string, words[0].where_str())
    )


class bool_converters:

    phil_type = "bool"

    def __str__(self):
        return self.phil_type

    def from_words(self, words, master):
        return bool_from_words(words=words, path=master.full_path())

    def as_words(self, python_object, master):
        if python_object is None:
            return [tokenizer.word(value="None")]
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        if python_object:
            return [tokenizer.word(value="True")]
        else:
            return [tokenizer.word(value="False")]


def number_from_value_string(value_string, words, path):
    if value_string is None:
        return None
    if value_string is freephil.Auto:
        return freephil.Auto
    # similar to libtbx.utils.number_from_string
    # (please review if making changes here)
    value_string_lower_strip = value_string.lower().strip()
    if value_string_lower_strip in ["true", "false"]:
        raise RuntimeError(
            'Error interpreting %s="%s" as a numeric expression%s'
            % (path, value_string, words[0].where_str())
        )
    if value_string_lower_strip == "none":
        return None
    if value_string_lower_strip == "auto":
        return freephil.Auto
    try:
        return int(value_string)
    except Exception:
        pass
    try:
        return eval(value_string, math.__dict__, {})
    except Exception as e:
        raise RuntimeError(
            f'Error interpreting %s="%s" as a numeric expression: {e.__class__.__name__}: {e!s}%s'
            % (path, value_string, words[0].where_str())
        )


def number_from_words(words, path):
    return number_from_value_string(
        value_string=str_from_words(words), words=words, path=path
    )


def numbers_from_words(words, path):
    all_values_string = str_from_words(words)
    if all_values_string is None or all_values_string is freephil.Auto:
        return all_values_string
    while True:
        have_changes = False
        for o, c in ["()", "[]"]:
            while all_values_string.startswith(o) and all_values_string.endswith(c):
                all_values_string = all_values_string[1:-1].strip()
                have_changes = True
        if not have_changes:
            break
    result = []
    for value_string in all_values_string.replace(",", " ").replace(";", " ").split():
        result.append(
            number_from_value_string(value_string=value_string, words=words, path=path)
        )
    return result


def int_from_number(number, words, path):
    if isinstance(number, int):
        return number
    if isinstance(number, float) and round(number) == number:
        return int(number)
    raise RuntimeError(
        'Error interpreting %s="%s" as an integer expression%s'
        % (path, str_from_words(words), words[0].where_str())
    )


def float_from_number(number, words, path):
    if isinstance(number, float):
        return number
    if isinstance(number, int):
        return float(number)
    raise RuntimeError(
        'Error interpreting %s="%s" as a floating-point expression%s'
        % (path, str_from_words(words), words[0].where_str())
    )


def int_from_words(words, path):
    result = number_from_words(words=words, path=path)
    if result is None or result is freephil.Auto:
        return result
    return int_from_number(number=result, words=words, path=path)


def float_from_words(words, path):
    result = number_from_words(words=words, path=path)
    if result is None or result is freephil.Auto:
        return result
    return float_from_number(number=result, words=words, path=path)


class _check_value_base:
    def _check_value(self, value, path_producer, words=None):
        def where_str():
            if words is None:
                return ""
            return words[0].where_str()

        if self.value_min is not None and value < self.value_min:
            raise RuntimeError(
                "%s element is less than the minimum allowed value:"
                " %s < %s%s"
                % (
                    path_producer(),
                    self._value_as_str(value=value),
                    self._value_as_str(value=self.value_min),
                    where_str(),
                )
            )
        if self.value_max is not None and value > self.value_max:
            raise RuntimeError(
                "%s element is greater than the maximum allowed value:"
                " %s > %s%s"
                % (
                    path_producer(),
                    self._value_as_str(value=value),
                    self._value_as_str(value=self.value_max),
                    where_str(),
                )
            )


class number_converters_base(_check_value_base):
    def __init__(self, value_min=None, value_max=None, allow_none=True):
        if value_min is not None and value_max is not None:
            assert value_min <= value_max
        self.value_min = value_min
        self.value_max = value_max
        self.allow_none = allow_none

    def __setstate__(self, state):
        # When unpickling ensure allow_none is set. Entire function is for
        # backwards-compatibility purposes only. 20180308
        self.allow_none = True
        for key, value in state.items():
            setattr(self, key, value)

    def __str__(self):
        kwds = []
        if self.value_min is not None:
            kwds.append("value_min=" + self._value_as_str(value=self.value_min))
        if self.value_max is not None:
            kwds.append("value_max=" + self._value_as_str(value=self.value_max))
        if self.allow_none:
            kwds.append("allow_none=True")
        if len(kwds) != 0:
            return self.phil_type + "(" + ", ".join(kwds) + ")"
        return self.phil_type

    def from_words(self, words, master):
        path = master.full_path()
        value = self._value_from_words(words=words, path=master.full_path())
        if value is None:
            if self.allow_none:
                return value
            else:
                raise RuntimeError("%s cannot be None" % path)
        elif value is freephil.Auto:
            return value
        self._check_value(value=value, path_producer=master.full_path, words=words)
        return value

    def as_words(self, python_object, master):
        if python_object is None:
            if self.allow_none:
                return [tokenizer.word(value="None")]
            else:
                raise RuntimeError("%s cannot be None" % master.full_path())
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        return [tokenizer.word(value=self._value_as_str(value=python_object))]


class int_converters(number_converters_base):

    phil_type = "int"

    def _value_from_words(self, words, path):
        return int_from_words(words=words, path=path)

    def _value_as_str(self, value):
        return "%d" % value


class float_converters(number_converters_base):

    phil_type = "float"

    def _value_from_words(self, words, path):
        return float_from_words(words=words, path=path)

    def _value_as_str(self, value):
        return "%.10g" % value


class numbers_converters_base(_check_value_base):
    def __init__(
        self,
        size=None,
        size_min=None,
        size_max=None,
        value_min=None,
        value_max=None,
        allow_none_elements=False,
        allow_auto_elements=False,
    ):
        assert size is None or (size_min is None and size_max is None)
        if size is not None:
            assert size > 0
            size_min = size
            size_max = size
        else:
            if size_min is not None:
                assert size_min > 0
            if size_max is not None:
                assert size_max > 0
                if size_min is not None:
                    assert size_min <= size_max
        if value_min is not None and value_max is not None:
            assert value_min <= value_max
        self.size_min = size_min
        self.size_max = size_max
        self.value_min = value_min
        self.value_max = value_max
        self.allow_none_elements = allow_none_elements
        self.allow_auto_elements = allow_auto_elements

    def __str__(self):
        kwds = []
        if self.size_min == self.size_max:
            if self.size_min is not None:
                kwds.append("size=%d" % self.size_min)
        else:
            if self.size_min is not None:
                kwds.append("size_min=%d" % self.size_min)
            if self.size_max is not None:
                kwds.append("size_max=%d" % self.size_max)
        if self.value_min is not None:
            kwds.append("value_min=" + self._value_as_str(value=self.value_min))
        if self.value_max is not None:
            kwds.append("value_max=" + self._value_as_str(value=self.value_max))
        if self.allow_none_elements:
            kwds.append("allow_none_elements=True")
        if self.allow_auto_elements:
            kwds.append("allow_auto_elements=True")
        if len(kwds) != 0:
            return self.phil_type + "(" + ", ".join(kwds) + ")"
        return self.phil_type

    def _check_size(self, size, path_producer, words=None):
        def where_str():
            if words is None:
                return ""
            return words[0].where_str()

        if self.size_max is not None and size > self.size_max:
            if self.size_max == self.size_min:
                precise = "exactly %d required"
            else:
                precise = "%d allowed at most"
            raise RuntimeError(
                "Too many values for %s: %d given, %s%s"
                % (path_producer(), size, (precise % self.size_max), where_str())
            )
        if self.size_min is not None and size < self.size_min:
            if self.size_max == self.size_min:
                precise = "exactly"
            else:
                precise = "at least"
            raise RuntimeError(
                "Not enough values for %s: %d given, %s %d required%s"
                % (path_producer(), size, precise, self.size_min, where_str())
            )

    def from_words(self, words, master):
        path = master.full_path()
        numbers = numbers_from_words(words=words, path=path)
        if numbers is None or numbers is freephil.Auto:
            return numbers
        self._check_size(size=len(numbers), path_producer=master.full_path, words=words)

        def where_str():
            if words is None:
                return ""
            return words[0].where_str()

        result = []
        for number in numbers:
            if number is None:
                if self.allow_none_elements:
                    value = number
                else:
                    raise RuntimeError(f"{path} element cannot be None{where_str()}")
            elif number is freephil.Auto:
                if self.allow_auto_elements:
                    value = number
                else:
                    raise RuntimeError(f"{path} element cannot be Auto{where_str()}")
            else:
                value = self._value_from_number(number=number, words=words, path=path)
                self._check_value(
                    value=value, path_producer=master.full_path, words=words
                )
            result.append(value)
        return result

    def as_words(self, python_object, master):
        if python_object is None:
            return [tokenizer.word(value="None")]
        # XXX note that pickling the object will lose the identity of Auto, so
        # we also need to check the type
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        self._check_size(size=len(python_object), path_producer=master.full_path)
        result = []
        for value in python_object:
            self._check_value(value=value, path_producer=master.full_path)
            if value is None:
                if self.allow_none_elements:
                    result.append(tokenizer.word(value="None"))
                else:
                    raise RuntimeError("%s element cannot be None" % master.full_path())
            elif value is freephil.Auto:
                if self.allow_auto_elements:
                    result.append(tokenizer.word(value="Auto"))
                else:
                    raise RuntimeError("%s element cannot be Auto" % master.full_path())
            else:
                result.append(tokenizer.word(value=self._value_as_str(value=value)))
        return result


class ints_converters(numbers_converters_base):

    phil_type = "ints"

    def _value_from_number(self, number, words, path):
        return int_from_number(number=number, words=words, path=path)

    def _value_as_str(self, value):
        return "%d" % value


class floats_converters(numbers_converters_base):

    phil_type = "floats"

    def _value_from_number(self, number, words, path):
        return float_from_number(number=number, words=words, path=path)

    def _value_as_str(self, value):
        return "%.10g" % value


class choice_converters:

    phil_type = "choice"

    def __init__(self, multi=False):
        self.multi = multi

    def __str__(self):
        if self.multi:
            return self.phil_type + "(multi=True)"
        return self.phil_type

    def from_words(self, words, master):
        if is_plain_auto(words=words):
            result = freephil.Auto
        elif self.multi:
            result = []
            for word in words:
                if word.value.startswith("*"):
                    result.append(word.value[1:])
            if len(result) == 0 and master.optional is not None and not master.optional:
                raise RuntimeError(
                    "Unspecified choice for %s:"
                    " at least one choice must be selected%s"
                    % (master.full_path(), words[0].where_str())
                )
        else:
            result = None
            for word in words:
                if word.value.startswith("*"):
                    if result is not None:
                        raise RuntimeError(
                            "Multiple choices for %s;"
                            " only one choice can be selected%s"
                            % (master.full_path(), words[0].where_str())
                        )
                    result = word.value[1:]
            if result is None and (master.optional is not None and not master.optional):
                raise RuntimeError(
                    "Unspecified choice for %s:"
                    " exactly one choice must be selected%s"
                    % (master.full_path(), words[0].where_str())
                )
        return result

    def as_words(self, python_object, master):
        if (python_object is freephil.Auto) or (
            isinstance(python_object, type(freephil.Auto))
        ):
            return [tokenizer.word(value="Auto")]
        assert not self.multi or python_object is not None
        if self.multi:
            use_flags = {value: False for value in python_object}
        n_choices = 0

        def raise_improper_master():
            raise RuntimeError(
                "Improper master choice definition: %s%s"
                % (master.as_str().rstrip(), master.words[0].where_str())
            )

        words = []
        for word in master.words:
            if word.value.startswith("*"):
                value = word.value[1:]
            else:
                value = word.value
            if python_object is not None:
                if not self.multi:
                    if value == python_object:
                        value = "*" + value
                        n_choices += 1
                        if n_choices > 1:
                            raise_improper_master()
                else:
                    if value in use_flags:
                        if use_flags[value]:
                            raise_improper_master()
                        use_flags[value] = True
                        value = "*" + value
                        n_choices += 1
            words.append(tokenizer.word(value=value, quote_token=word.quote_token))
        if not self.multi:
            if n_choices == 0 and (
                (master.optional is not None and not master.optional)
                or python_object is not None
            ):
                raise RuntimeError(
                    "Invalid choice: {}={}".format(
                        master.full_path(), str(python_object)
                    )
                )
        else:
            unused = []
            for value, use_flag in use_flags.items():
                if not use_flag:
                    unused.append(value)
            n = len(unused)
            if n != 0:
                raise RuntimeError(
                    "Invalid {}: {}={}".format(
                        str(self), master.full_path(), str(unused)
                    )
                )
            if n_choices == 0 and (master.optional is not None and not master.optional):
                raise RuntimeError(
                    "Empty list for mandatory {}: {}".format(
                        str(self), master.full_path()
                    )
                )
        return words

    def fetch(self, source_words, master, ignore_errors=False):
        assert not is_plain_none(words=master.words)
        assert not is_plain_auto(words=master.words)
        if is_plain_auto(words=source_words):
            return master.customized_copy(words=[tokenizer.word(value="Auto")])
        flags = {}
        for word in master.words:
            if word.value.startswith("*"):
                value = word.value[1:]
            else:
                value = word.value
            flags[value.lower()] = False
        if (master.optional is not None and not master.optional) or not is_plain_none(
            words=source_words
        ):
            have_quote_or_star = False
            have_plus = False
            for word in source_words:
                if word.quote_token is not None or word.value.startswith("*"):
                    have_quote_or_star = True
                    break
                if word.value.find("+") >= 0:
                    have_plus = True
            process_plus = False
            if not have_quote_or_star and have_plus:
                values = "".join([word.value for word in source_words]).split("+")
                for value in values[1:]:
                    if len(value.strip()) == 0:
                        break
                else:
                    process_plus = True

            def raise_not_a_possible_choice(value):
                raise freephil.Sorry(
                    "Not a possible choice for %s: %s%s\n"
                    % (master.full_path(), value, word.where_str())
                    + "  Possible choices are:\n"
                    + "    "
                    + "\n    ".join([w.value for w in master.words])
                )

            if process_plus:
                for word in source_words:
                    for value in word.value.split("+"):
                        if len(value) == 0:
                            continue
                        if value not in flags:
                            raise_not_a_possible_choice(value)
                        flags[value.lower()] = True
            else:
                for word in source_words:
                    if word.value.startswith("*"):
                        value = word.value[1:]
                        flag = True
                    else:
                        value = word.value
                        if len(source_words) == 1:
                            flag = True
                        else:
                            flag = False
                    if flag and value.lower() not in flags:
                        if ignore_errors:
                            continue
                        else:
                            raise_not_a_possible_choice(value)
                    flags[value.lower()] = flag
        words = []
        for word in master.words:
            if word.value.startswith("*"):
                value = word.value[1:]
            else:
                value = word.value
            if flags[value.lower()]:
                value = "*" + value
            words.append(
                tokenizer.word(
                    value=value,
                    quote_token=word.quote_token,
                    line_number=word.line_number,
                    source_info=word.source_info,
                )
            )
        return master.customized_copy(words=words)
