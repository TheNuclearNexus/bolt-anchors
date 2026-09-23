# A plain bolt variable holding a location can be used directly as a name.
FOO = ~/foo

function FOO:
    say plain

# `{...}` interpolates the value and appends path segments.
function {FOO}/bar:
    say interpolated

# The same syntax works with anchors bound by `as`.
append function ~/anchor as a:
    function {a}/child as c:
        print(c)
        say child
