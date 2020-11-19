# Content in this file falls under the libtbx license

import pickle

from freephil import tokenizer


def test_basic():
    tests = [
        ["", []],
        ["resname=a and chain=b", ["resname", "=", "a", "and", "chain", "=", "b"]],
        ["resname a and chain b", ["resname", "a", "and", "chain", "b"]],
        [
            "resname resname and chain chain",
            ["resname", "resname", "and", "chain", "chain"],
        ],
        ['resname "a b"', ["resname", "a b"]],
        ["resname a", ["resname", "a"]],
        ["resname ala and backbone", ["resname", "ala", "and", "backbone"]],
        ["resname ala or backbone", ["resname", "ala", "or", "backbone"]],
        ["name x and x > 10", ["name", "x", "and", "x", ">", "10"]],
        [
            "((expr or expr) and expr)",
            ["(", "(", "expr", "or", "expr", ")", "and", "expr", ")"],
        ],
        ["resname and and chain b", ["resname", "and", "and", "chain", "b"]],
        ["resname ( and chain b", ["resname", "(", "and", "chain", "b"]],
        ['resname "(" and chain b', ["resname", "(", "and", "chain", "b"]],
        [
            "all_hydrophobic_within(5) and resname ALA",
            ["all_hydrophobic_within", "(", "5", ")", "and", "resname", "ALA"],
        ],
        ["something(a, b)", ["something", "(", "a", ",", "b", ")"]],
        ["something(a b)", ["something", "(", "a", "b", ")"]],
        ['something("a""b")', ["something", "(", "a", "b", ")"]],
        ["resname 'a \\\\'", ["resname", "a \\"]],
        ["resname 'a'", ["resname", "a"]],
        ["resname '\"'", ["resname", '"']],
        ["resname '\"\\''", ["resname", "\"'"]],
        ['resname "\'\\""', ["resname", "'\""]],
        ["name o1'", ["name", "o1'"]],
        ['name """o1\'"""', ["name", "o1'"]],
        ['name """o1\n  o2\'"""', ["name", "o1\n  o2'"]],
        ['name """o1\\\n  o2\'"""', ["name", "o1  o2'"]],
    ]
    for input_string, expected_result in tests:
        print(input_string)
        result = [
            word.value for word in tokenizer.word_iterator(input_string=input_string)
        ]
        print(result)
        if expected_result is not None:
            assert result == expected_result
        print()


def test_pickle():
    o = tokenizer.word(value="hello")
    l = pickle.loads(pickle.dumps(o))
    assert l.value == "hello"
    o = tokenizer.settings(meta_comment="%")
    l = pickle.loads(pickle.dumps(o))
    assert l.meta_comment == "%"
    o = tokenizer.word_iterator(input_string="all")
    l = pickle.loads(pickle.dumps(o))
    assert l.char_iter.input_string == "all"
