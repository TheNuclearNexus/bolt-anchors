__all__ = [
    "AstAnchor",
]


from dataclasses import dataclass
from typing import Any

from bolt import AstValue


@dataclass(frozen=True, slots=True)
class AstAnchor(AstValue):
    """Ast node representing a named resource location anchor.

    The anchor holds the fully resolved resource location of the declaration it
    was created from. When used as a value it behaves like a plain string.
    """

    value: Any = ""
