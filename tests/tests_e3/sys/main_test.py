from __future__ import absolute_import
from __future__ import print_function

import ast
import pytest

from e3.sys import RewriteImportNodeTransformer, RewriteImportRule, \
    RewriteNodeError


def test_filtering_import():
    script = """
import a, b, c
import a1, b, c
import a2, a3
from d import l1, l2, c3
from foo.bar.module import name1, name2, name3
from foo.bar2.module import name1, name2, name3
from foo.bar2.module import name2
from foo.bar2.module3 import name1
"""

    node = ast.parse(script, '<string>')
    node = RewriteImportNodeTransformer(
        [
            RewriteImportRule('b'),
            RewriteImportRule('a'),
            RewriteImportRule('.*3'),
            RewriteImportRule('.*\.bar\..*', 'name2')
        ]
    ).visit(node)

    expected = "Module(body=["

    expected += "Import(names=[alias(name='c', asname=None)]),"
    # import a, b, c
    # b and a skipped

    expected += " Import(names=[alias(name='a1', asname=None)," \
                " alias(name='c', asname=None)]),"
    # import a1, b, c => a1, c  -- b is skipped

    expected += " Import(names=[alias(name='a2', asname=None)]),"
    # import a2, a3 => a2 -- a3 is skipped (.*3)

    expected += " ImportFrom(module='d'," \
                " names=[alias(name='l1', asname=None)," \
                " alias(name='l2', asname=None)," \
                " alias(name='c3', asname=None)], level=0),"
    # from d import l1, l2, c3 - not modified

    expected += " ImportFrom(module='foo.bar.module'," \
                " names=[alias(name='name1', asname=None)," \
                " alias(name='name3', asname=None)], level=0),"
    # from foo.bar.module import name1, name2, name3
    # .*\.bar\..* name2 -> name2 is skipped

    expected += " ImportFrom(module='foo.bar2.module'," \
                " names=[alias(name='name1', asname=None), " \
                "alias(name='name2', asname=None), " \
                "alias(name='name3', asname=None)], level=0),"
    # from foo.bar2.module import name1, name2, name3 - not modifed

    expected += " ImportFrom(module='foo.bar2.module'," \
                " names=[alias(name='name2', asname=None)], level=0),"
    # from foo.bar2.module import name2 - not modified

    expected += " ImportFrom(module='foo.bar2.module3'," \
                " names=[], level=0)])"
    # from foo.bar2.module3 import name1 -- module matching .*3
    assert ast.dump(node) == expected

    node2 = ast.parse(script, '<string>')
    with pytest.raises(RewriteNodeError) as err:
        node2 = RewriteImportNodeTransformer(
            [
                RewriteImportRule(
                    'a',
                    action=RewriteImportRule.RuleAction.reject),
                RewriteImportRule('b'),
                RewriteImportRule('.*3'),
                RewriteImportRule('.*\.bar\..*', 'name2')
            ]
        ).visit(node2)
        # verify that import a is rejected
    assert "Import(names=[alias(name='a', asname=None)," \
           " alias(name='b', asname=None)," \
           " alias(name='c', asname=None)])" in err.value.message

    node3 = ast.parse(script, '<string>')
    with pytest.raises(RewriteNodeError) as err3:
        node3 = RewriteImportNodeTransformer(
            [
                RewriteImportRule('a'),
                RewriteImportRule('b'),
                RewriteImportRule('.*3'),
                RewriteImportRule(
                    '.*\.bar\..*', 'name2',
                    action=RewriteImportRule.RuleAction.reject)
            ]
        ).visit(node3)
    # verify that from foo.bar.module import name2 is rejected
    assert "module='foo.bar." in err3.value.message
