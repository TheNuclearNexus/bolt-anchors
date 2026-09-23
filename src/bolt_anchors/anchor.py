__all__ = [
    "Anchor",
]


class Anchor(str):
    """Runtime value representing a fully resolved resource location.

    Anchors are immutable strings that additionally support joining path
    segments with ``/``. Because they subclass :class:`str`, they can be used
    anywhere a string is accepted, including interpolation and formatting.
    """

    __slots__ = ()

    def __truediv__(self, other: object) -> Anchor:
        return Anchor(f"{self}/{other}")

    def get_canonical_value(self) -> str:
        """Return the canonical resource location."""
        return str(self)
