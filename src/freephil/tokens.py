# Content in this file falls under the libtbx license

from . import tokenizer

standard_identifier_start_characters = set()
for c in "_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
    standard_identifier_start_characters.add(c)
standard_identifier_continuation_characters = set(standard_identifier_start_characters)
for c in ".0123456789":
    standard_identifier_continuation_characters.add(c)


def is_standard_identifier(string):
    if len(string) == 0:
        return False
    if string[0] not in standard_identifier_start_characters:
        return False
    for c in string[1:]:
        if c not in standard_identifier_continuation_characters:
            return False
    sub_strings = string.split(".")
    if len(sub_strings) > 1:
        for sub in sub_strings:
            if not is_standard_identifier(sub):
                return False
    return True


def is_plain_none(words):
    return (
        len(words) == 1
        and words[0].quote_token is None
        and words[0].value.lower() == "none"
    )


def is_plain_auto(words):
    return (
        len(words) == 1
        and words[0].quote_token is None
        and words[0].value.lower() == "auto"
    )


def tokenize_value_literal(input_string, source_info):
    return list(
        tokenizer.word_iterator(
            input_string=input_string,
            source_info=source_info,
            list_of_settings=[tokenizer.settings(contiguous_word_characters="")],
        )
    )
