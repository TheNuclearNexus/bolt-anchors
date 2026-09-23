from pathlib import Path

import pytest
from beet import run_beet

BEET = """
require:
  - bolt
  - bolt_anchors
data_pack:
  load: src
pipeline:
  - mecha
"""


@pytest.fixture
def build(tmp_path: Path):
    def _build(source: str, resource: str = "data/test/function/main.mcfunction"):
        path = tmp_path / "src" / resource
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        (tmp_path / "beet.yml").write_text(BEET)
        return run_beet(directory=tmp_path)

    return _build


def test_anchor_declaration(build):
    with build("function ~/hello as hello:\n    say hi\n") as ctx:
        assert "test:main/hello" in ctx.data.functions
        assert ctx.data.functions["test:main/hello"].text == "say hi\n"


def test_anchor_reused_across_resource_types(build):
    source = (
        "loot_table ./technical/loot as LOOT {}\n"
        'loot_table LOOT / "extra" {}\n'
        'predicate LOOT / "check" {}\n'
    )
    with build(source) as ctx:
        assert set(ctx.data.loot_tables) == {
            "test:technical/loot",
            "test:technical/loot/extra",
        }
        assert set(ctx.data.predicates) == {"test:technical/loot/check"}


def test_nested_anchors_resolve_against_enclosing_declaration(build):
    source = (
        "append function ~/root as root:\n"
        '    function root / "child" as child:\n'
        '        function child / "grand":\n'
        "            say deep\n"
    )
    with build(source) as ctx:
        assert "test:main/root/child/grand" in ctx.data.functions
        assert ctx.data.functions["test:main/root/child/grand"].text == "say deep\n"


def test_anchor_expression_value(build):
    source = "function ~/root as root:\n    say f\"{root / 'a' / 'b'}\"\n"
    with build(source) as ctx:
        assert ctx.data.functions["test:main/root"].text == "say test:main/root/a/b\n"


def test_anchor_command_moves_scope(build):
    source = (
        "anchor demo:foo as foo:\n"
        "    print('foo =', foo)\n"
        "    say moved scope\n"
        "    function ~/bar as bar:\n"
        "        print('bar =', bar)\n"
        "        say bar\n"
        '    function foo / "baz" as baz:\n'
        "        print('baz =', baz)\n"
        "        say baz\n"
    )
    with build(source) as ctx:
        assert "demo:foo" not in ctx.data.functions
        assert ctx.data.functions["demo:foo/bar"].text == "say demo:foo/bar\n"
        assert ctx.data.functions["demo:foo/baz"].text == "say demo:foo/baz\n"
        assert ctx.data.functions["test:main"].text == "say moved scope\n"


def test_anchor_command_body_runs_like_top_level(build):
    source = (
        "anchor demo:foo as foo:\n"
        "    x = 42\n"
        "    print('x =', x)\n"
        '    loot_table foo / "loot" {}\n'
    )
    with build(source) as ctx:
        assert "demo:foo/loot" in ctx.data.loot_tables


def test_nested_anchor_commands(build):
    source = (
        "anchor ./a as A:\n"
        '    anchor A / "b" as B:\n'
        "        function ~/inner as inner:\n"
        "            say inner\n"
        '        function B / "leaf":\n'
        "            say leaf\n"
        "\n"
        "anchor ~/rel as REL:\n"
        '    function REL / "x":\n'
        "        say rel\n"
    )
    with build(source) as ctx:
        assert "test:a/b/inner" in ctx.data.functions
        assert "test:a/b/leaf" in ctx.data.functions
        assert ctx.data.functions["test:a/b/leaf"].text == "say leaf\n"
        assert "test:main/rel/x" in ctx.data.functions


def test_plain_interpolated_declaration(build):
    # Regression: a bound location used directly as a declaration name is an
    # interpolation and must not be treated as an anchor name.
    source = "FOO = ~/foo\nfunction FOO:\n    say hi\n"
    with build(source) as ctx:
        assert ctx.data.functions["test:main/foo"].text == "say hi\n"


def test_interpolated_path_extension(build):
    source = "FOO = ~/foo\nfunction {FOO}/bar:\n    say bar\n"
    with build(source) as ctx:
        assert ctx.data.functions["test:main/foo/bar"].text == "say bar\n"


def test_interpolated_path_extension_with_anchor(build):
    source = (
        "append function ~/anchor as a:\n"
        "    function {a}/child as c:\n"
        "        print(c)\n"
        "        say child\n"
    )
    with build(source) as ctx:
        assert ctx.data.functions["test:main/anchor/child"].text == "say child\n"


def test_anchor_runtime_value(build):
    source = (
        "append function ~/foo as foo:\n"
        '    say f"{type(foo).__name__}"\n'
        '    say f"path {foo}/bar"\n'
    )
    with build(source) as ctx:
        assert ctx.data.functions["test:main/foo"].text == (
            "say Anchor\nsay path test:main/foo/bar\n"
        )


def test_plain_bolt_still_works(build):
    source = (
        "def double(x):\n"
        "    return x\n"
        "\n"
        "function demo:hello\n"
        "function ~/plain:\n"
        "    say plain\n"
    )
    with build(source) as ctx:
        assert "test:main/plain" in ctx.data.functions
        assert ctx.data.functions["test:main/plain"].text == "say plain\n"
        assert ctx.data.functions["test:main"].text == "function demo:hello\n"
