from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, ClassVar

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.utils.frontend import Frontend

from projxdsl.frontend.parser import ProjParser


@dataclass(frozen=True)
class ProjFrontend(Frontend):
    """Frontend for parsing proj-xdsl surface syntax."""

    name: ClassVar[str] = "proj"

    def parse(self, ctx: Context, input: IO[bytes], input_name: str) -> ModuleOp:
        """Parse proj-xdsl surface syntax into a ModuleOp."""
        source = input.read().decode("utf-8")
        parser = ProjParser(source, input_name)
        return parser.parse_module()


def get_all_frontends() -> dict[str, Callable[[], type[Frontend]]]:
    """Return the list of all available frontends."""

    def get_proj():
        return ProjFrontend

    return {
        "proj": get_proj,
    }
