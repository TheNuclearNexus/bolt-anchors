__all__ = [
    "ANCHOR_COMMAND_IDENTIFIER",
    "AnchorBlockParser",
    "AnchorCommandTransformer",
    "AnchorContext",
    "AnchorIdentifierParser",
    "AnchorRootParser",
    "ResourceNameParser",
]


import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Any

from bolt.ast import AstFormatString, AstInterpolation
from bolt.parse import IDENTIFIER_PATTERN
from bolt.pattern import STRING_PATTERN
from mecha import (
    AstChildren,
    AstCommand,
    AstNode,
    AstResourceLocation,
    AstRoot,
    CommandSpec,
    CompilationDatabase,
    MutatingReducer,
    Parser,
    delegate,
    get_stream_scope,
    rule,
)
from mecha.contrib.nested_location import AstNestedLocation
from mecha.contrib.relative_location import resolve_relative_location
from mecha.utils import JsonQuoteHelper
from tokenstream import Token, TokenStream, set_location

from .ast import AstAnchor

ANCHOR_COMMAND_IDENTIFIER = "anchor:name:commands"

IDENTIFIER_REGEX = re.compile(IDENTIFIER_PATTERN)

# Children that indicate that the current resource location argument introduces
# a resource declaration with a body.
DECLARATION_CHILDREN = {"commands", "content"}


class AnchorContext:
    """Tracks anchors and declaration roots while parsing a compilation unit."""

    def __init__(self, database: CompilationDatabase):
        self.database = database
        self._unit: Any = None
        self._bases: list[str] = []
        self._anchored: list[bool] = []
        self._scopes: list[dict[str, AstAnchor]] = [{}]
        self._pending: tuple[tuple[str, ...], str, bool] | None = None

    def reset_if_needed(self):
        unit = self.database.current
        if unit is not self._unit:
            self._unit = unit
            self._bases.clear()
            self._anchored.clear()
            self._scopes = [{}]
            self._pending = None

    def file_root(self) -> str | None:
        unit = self.database.current
        if unit is None:
            return None
        return self.database[unit].resource_location

    def current_root(self) -> str | None:
        if self._bases:
            return self._bases[-1]
        return self.file_root()

    @contextmanager
    def scope(self) -> Iterator[dict[str, AstAnchor]]:
        self._scopes.append({})
        try:
            yield self._scopes[-1]
        finally:
            self._scopes.pop()

    @contextmanager
    def declaration(self, base: str, anchored: bool = False) -> Iterator[None]:
        with self.scope():
            self._bases.append(base)
            self._anchored.append(anchored or self.is_anchored())
            try:
                yield
            finally:
                self._anchored.pop()
                self._bases.pop()

    def is_anchored(self) -> bool:
        return any(self._anchored)

    def bind(self, identifier: str, anchor: AstAnchor):
        self._scopes[-1][identifier] = anchor

    def lookup(self, identifier: str) -> AstAnchor | None:
        for scope in reversed(self._scopes):
            if anchor := scope.get(identifier):
                return anchor
        return None

    def set_pending(self, name_scope: tuple[str, ...], base: str, anchored: bool):
        self._pending = (name_scope, base, anchored)

    def take_pending(self, name_scope: tuple[str, ...]) -> tuple[str, bool] | None:
        pending = self._pending
        if pending is None or pending[0] != name_scope:
            return None
        self._pending = None
        return pending[1], pending[2]


def is_declaration_name(spec: CommandSpec, scope: tuple[str, ...]) -> bool:
    """Return whether the given argument scope introduces a resource declaration."""
    tree = spec.tree.get(scope)
    if tree is None or not tree.children:
        return False
    return any(name in DECLARATION_CHILDREN for name in tree.children)


def resolve_nested_location(
    node: AstNestedLocation, context: AnchorContext
) -> AstResourceLocation:
    """Resolve a nested location against the current declaration root."""
    root = context.current_root()
    if root is None:
        raise node.emit_error(
            ValueError("Can't resolve nested location without a root.")
        )

    namespace, resolved = resolve_relative_location(
        node.path, root, include_root_file=True
    )
    resource_location = AstResourceLocation(
        is_tag=node.is_tag, namespace=namespace, path=resolved
    )
    return set_location(resource_location, node)


def canonical_location(node: AstResourceLocation, context: AnchorContext) -> str:
    """Return the fully resolved resource location of a name node."""
    if isinstance(node, AstNestedLocation):
        return resolve_nested_location(node, context).get_canonical_value()
    return node.get_canonical_value()


ANCHOR_SYNTAX = {
    "literal": None,
    "identifier": IDENTIFIER_PATTERN,
    "string": STRING_PATTERN,
    "number": r"(?:0|[1-9]\d*)(?:\.\d+)?",
    "slash": r"/",
}

INTERPOLATION_SYNTAX = {
    **ANCHOR_SYNTAX,
    "curly": r"\{|\}",
}


def parse_segments(stream: TokenStream, quote_helper: JsonQuoteHelper) -> list[str]:
    """Parse `/` separated path segments."""
    segments: list[str] = []

    while stream.get(("slash", "/")):
        segment = stream.expect_any("string", "identifier", "number")
        if segment.match("string"):
            segments.append(quote_helper.unquote_string(segment))
        else:
            segments.append(segment.value)

    return segments


def parse_anchor_path(
    stream: TokenStream,
    context: AnchorContext,
    quote_helper: JsonQuoteHelper,
) -> tuple[str, Token] | None:
    """Parse an anchor followed by any number of path segments."""
    with stream.syntax(**ANCHOR_SYNTAX):
        token = stream.peek()

        if token is None or not isinstance(token.value, str):
            return None
        if not IDENTIFIER_REGEX.fullmatch(token.value):
            return None

        anchor = context.lookup(token.value)
        if anchor is None:
            return None

        start = stream.expect()
        value = str(anchor.value)

        for segment in parse_segments(stream, quote_helper):
            value = f"{value}/{segment}"

        return value, start


@dataclass
class ResourceNameParser:
    """Parser for resource declaration names that supports anchors."""

    parser: Parser
    context: AnchorContext
    spec: CommandSpec
    quote_helper: JsonQuoteHelper = field(default_factory=JsonQuoteHelper)

    def __call__(self, stream: TokenStream) -> AstNode:
        self.context.reset_if_needed()

        node = self.parse_anchor(stream)
        if node is None:
            node = self.parse_interpolation(stream)
        if node is None:
            node = self.parser(stream)

        scope = get_stream_scope(stream)
        if not is_declaration_name(self.spec, scope):
            return node

        # Interpolated names are resolved by bolt during evaluation, so there is
        # no static location to bind or extend here.
        if not isinstance(node, AstResourceLocation):
            return node

        anchored = scope[0] == "anchor"

        if (anchored or self.context.is_anchored()) and isinstance(
            node, AstNestedLocation
        ):
            node = resolve_nested_location(node, self.context)

        base = canonical_location(node, self.context)

        with stream.checkpoint() as commit:
            if stream.get(("literal", "as")):
                with stream.syntax(identifier=IDENTIFIER_PATTERN):
                    token = stream.expect("identifier")
                self.context.bind(
                    token.value, set_location(AstAnchor(value=base), token)
                )
                commit()

        self.context.set_pending(scope, base, anchored)
        return node

    def parse_anchor(self, stream: TokenStream) -> AstResourceLocation | None:
        result = parse_anchor_path(stream, self.context, self.quote_helper)
        if result is None:
            return None

        value, start = result
        node = AstResourceLocation.from_value(value)
        return set_location(node, start, stream.current)

    def parse_interpolation(self, stream: TokenStream) -> AstResourceLocation | None:
        """Parse an interpolated location such as `{FOO}/bar`."""
        with stream.syntax(**INTERPOLATION_SYNTAX):
            open_brace = stream.get(("curly", "{"))
            if not open_brace:
                return None

            with stream.ignore("whitespace"):
                value = delegate("bolt:expression", stream)

            stream.expect(("curly", "}"))
            segments = parse_segments(stream, self.quote_helper)

        # Anchors are static, so keep the result a plain resource location.
        if isinstance(value, AstAnchor):
            location = str(value.value)
            for segment in segments:
                location = f"{location}/{segment}"
            node = AstResourceLocation.from_value(location)
            return set_location(node, open_brace, stream.current)

        if segments:
            fmt = "{}" + "".join(f"/{segment}" for segment in segments)
            value = AstFormatString(fmt=fmt, values=AstChildren([value]))

        node = AstInterpolation(converter="resource_location", value=value)
        return set_location(node, open_brace, stream.current)


@dataclass
class AnchorIdentifierParser:
    """Parser for identifiers that resolves anchors to their resource location."""

    parser: Parser
    context: AnchorContext
    quote_helper: JsonQuoteHelper = field(default_factory=JsonQuoteHelper)

    def __call__(self, stream: TokenStream) -> AstNode:
        self.context.reset_if_needed()

        result = parse_anchor_path(stream, self.context, self.quote_helper)
        if result is not None:
            value, start = result
            node = AstAnchor(value=value)
            return set_location(node, start, stream.current)

        return self.parser(stream)


@dataclass
class AnchorBlockParser:
    """Parser that manages the anchor scope of a resource declaration body."""

    parser: Parser
    context: AnchorContext

    def __call__(self, stream: TokenStream) -> Any:
        self.context.reset_if_needed()

        scope = get_stream_scope(stream)
        pending = self.context.take_pending(scope[:-1])

        if pending is None:
            return self.parser(stream)

        base, anchored = pending

        with self.context.declaration(base, anchored):
            return self.parser(stream)


@dataclass
class AnchorCommandTransformer(MutatingReducer):
    """Inlines the body of `anchor` commands into the surrounding root."""

    @rule(AstRoot)
    def anchor_commands(self, node: AstRoot) -> AstRoot:
        changed = False
        commands: list[AstCommand] = []

        for command in node.commands:
            if (
                isinstance(command, AstCommand)
                and command.identifier == ANCHOR_COMMAND_IDENTIFIER
                and command.arguments
                and isinstance(body := command.arguments[-1], AstRoot)
            ):
                commands.extend(body.commands)
                changed = True
                continue

            commands.append(command)

        if changed:
            return replace(node, commands=AstChildren(commands))

        return node


@dataclass
class AnchorRootParser:
    """Parser that inlines `anchor` commands right after parsing."""

    parser: Parser
    transformer: AnchorCommandTransformer = field(
        default_factory=AnchorCommandTransformer
    )

    def __call__(self, stream: TokenStream) -> Any:
        node = self.parser(stream)
        if isinstance(node, AstRoot):
            return self.transformer(node)
        return node
