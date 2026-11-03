from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, ClassVar

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.utils.frontend import Frontend

from projxdsl.frontend.cst_parser import ProjCSTParser
from projxdsl.frontend.typechecker import TypeChecker


@dataclass(frozen=True)
class ProjFrontend(Frontend):
    """Frontend for parsing proj-xdsl surface syntax."""

    name: ClassVar[str] = "proj"

    def parse(self, ctx: Context, input: IO[bytes], input_name: str) -> ModuleOp:
        """Parse proj-xdsl surface syntax into a ModuleOp."""
        source = input.read().decode("utf-8")

        # First pass: Parse to CST
        cst_parser = ProjCSTParser(source, input_name)
        cst = cst_parser.parse_module()

        # Second pass: Type check CST and emit IR
        typechecker = TypeChecker()
        return typechecker.check_module(cst)


def get_all_frontends() -> dict[str, Callable[[], type[Frontend]]]:
    """Return the list of all available frontends."""

    def get_proj():
        return ProjFrontend

    return {
        "proj": get_proj,
    }
