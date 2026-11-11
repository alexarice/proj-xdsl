from collections.abc import Callable

from xdsl.passes import ModulePass


def get_all_passes() -> dict[str, Callable[[], type[ModulePass]]]:
    """Return the list of all available passes."""

    def get_func_inline():
        from projxdsl.transforms.func_inline import FuncInlinePass

        return FuncInlinePass

    def get_simplify_qif():
        from projxdsl.transforms.simplify_qif import SimplifyQifPass

        return SimplifyQifPass

    return {
        "func-inline": get_func_inline,
        "simplify-qif": get_simplify_qif,
    }
