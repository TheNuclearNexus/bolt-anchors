# Bolt Anchors

> Name resource locations and build nested paths in [bolt](https://github.com/mcbeet/beet/tree/main/packages/bolt).

Bolt anchors let you bind a resource declaration to an identifier with the `as`
clause. The anchor can then be used as a value or extended with `/` to build
nested resource locations.

## Installation

```bash
pip install bolt-anchors
```

## Configuration

Add the plugin to your `beet.yml`/`beet.json` after `bolt`.

```yaml
pipeline:
  - mecha

require:
  - bolt
  - bolt_anchors
```

## Usage

Bind an anchor when declaring any resource. The anchor holds the fully resolved
resource location of the declaration.

```mcfunction
append function ~/foo as foo:
    print(foo)
    function foo / "bar":
        say foo bar
```

`foo` holds the fully resolved resource location of the declaration (relative to
the current file and the enclosing declarations). It can be extended into a
nested resource location, used as a value, and reused to declare or call other
resources. Anchors work for any resource type and any path depth.

```mcfunction
loot_table ./technical/loot as LOOT {}
print(LOOT)
```

### Interpolated paths

Any location value can be interpolated with `{...}` and extended with `/`
segments. This also works for plain bolt variables that hold a location.

```mcfunction
FOO = ~/foo

function FOO:          # demo:foo
    say plain

function {FOO}/bar:    # demo:foo/bar
    say interpolated
```

Anchors support the same syntax, as well as the `foo / "bar"` shorthand.

```mcfunction
append function ~/anchor as a:
    function {a}/"quoted"/child as c:
        print(c)
        say child
```

Anchors can be used as values, interpolated into strings, and reused when
declaring or calling other resources.

```mcfunction
function ~/utils as utils:
    function utils / "math" / "add":
        scoreboard players add @s points 1

advancement ./tech/root as ROOT {}
predicate ROOT / "check" {}
say f"prefix is {utils}"
function utils / "math" / "add"
```

### Moving the path scope

The `anchor` command changes the current path scope without creating a resource.
Nested locations and anchors inside its block resolve against the new location.

```mcfunction
anchor demo:foo as foo:
    function ~/bar as bar:
        print(bar) # demo:foo/bar
    function foo / "baz" as baz:
        print(baz) # demo:foo/baz
```

The block itself emits no file. Commands and statements inside an `anchor` block
are treated like regular top-level code and are inlined into the current file,
while any resource declarations create files relative to the new scope.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check
```
