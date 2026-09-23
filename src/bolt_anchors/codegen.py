__all__ = [
    "AnchorCodegen",
]


from dataclasses import dataclass

from bolt import Accumulator
from mecha import Visitor, rule

from .ast import AstAnchor


@dataclass
class AnchorCodegen(Visitor):
    """Codegen extension that materializes anchors as runtime values."""

    @rule(AstAnchor)
    def anchor(self, node: AstAnchor, acc: Accumulator) -> list[str]:
        result = acc.make_variable()
        acc.statement(f"{result} = {acc.helper('Anchor', repr(str(node.value)))}")
        return [result]
