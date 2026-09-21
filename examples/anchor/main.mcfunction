anchor demo:foo as foo:
    print("foo =", foo)
    say moved scope
    function ~/bar as bar:
        print("bar =", bar)
        say nested at bar
    function foo / "baz" as baz:
        print("baz =", baz)
        say nested at baz

anchor demo:bar:
    function ~/foo as foo:
        print("foo =", foo)
