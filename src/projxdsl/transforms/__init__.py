from collections.abc import Callable

from xdsl.passes import ModulePass


def get_all_passes() -> dict[str, Callable[[], type[ModulePass]]]:
    """Return the list of all available passes."""

    def get_func_inline():
        from projxdsl.transforms.func_inline import FuncInlinePass

        return FuncInlinePass

    return {
        "func-inline": get_func_inline,
    }
