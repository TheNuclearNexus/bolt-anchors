from beet import Context
from bolt import Runtime
from mecha import Mecha

from .parse import (
    AnchorBlockParser,
    AnchorContext,
    AnchorIdentifierParser,
    AnchorRootParser,
    ResourceNameParser,
)

__all__ = ["beet_default"]

RESOURCE_NAME_PARSERS = (
    "command:argument:minecraft:function",
    "command:argument:minecraft:resource_location",
)

BLOCK_PARSERS = (
    "command:argument:mecha:nested_root",
    "command:argument:mecha:nested_json",
)

# `anchor <resource_location> [as <identifier>]:` moves the path scope and can
# bind the location to an identifier without creating a resource.
ANCHOR_COMMANDS = {
    "type": "root",
    "children": {
        "anchor": {
            "type": "literal",
            "children": {
                "name": {
                    "type": "argument",
                    "parser": "minecraft:resource_location",
                    "children": {
                        "commands": {
                            "type": "argument",
                            "parser": "mecha:nested_root",
                            "executable": True,
                        }
                    },
                }
            },
        }
    },
}


def beet_default(ctx: Context):
    ctx.inject(Runtime)
    mc = ctx.inject(Mecha)

    context = AnchorContext(mc.database)
    spec = mc.spec

    spec.add_commands(ANCHOR_COMMANDS)

    for name in RESOURCE_NAME_PARSERS:
        if parser := spec.parsers.get(name):
            spec.parsers[name] = ResourceNameParser(parser, context, spec)

    for name in BLOCK_PARSERS:
        if parser := spec.parsers.get(name):
            spec.parsers[name] = AnchorBlockParser(parser, context)

    if parser := spec.parsers.get("bolt:identifier"):
        spec.parsers["bolt:identifier"] = AnchorIdentifierParser(parser, context)

    # Inline anchor bodies at parse time so that the cached ast already reflects
    # the moved path scope and statements are evaluated like regular code.
    if parser := spec.parsers.get("root"):
        spec.parsers["root"] = AnchorRootParser(parser)
