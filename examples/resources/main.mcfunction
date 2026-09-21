append function ~/root as root:
    print("root =", root)
    print("joined =", root / "a" / "b")
    function root / "child" as child:
        print("child =", child)
        function child / "grand":
            say deep
    function root / "sibling":
        say sibling

loot_table ./loot as LOOT {}
loot_table LOOT / "extra" {}
predicate LOOT / "pred" {}
print("LOOT =", LOOT)
say f"value {LOOT} and {root}"
