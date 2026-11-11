from collections.abc import Callable

from xdsl.passes import ModulePass


def get_all_passes() -> dict[str, Callable[[], type[ModulePass]]]:
    """Return the list of all available passes."""

    def get_func_inline():
        from projxdsl.transforms.func_inline import FuncInlinePass

        return FuncInlinePass

    def get_hoist_from_qif():
        from projxdsl.transforms.hoist_classical import HoistFromQifPass

        return HoistFromQifPass

    def get_split_qif():
        from projxdsl.transforms.split_qif import SplitQifPass

        return SplitQifPass

    return {
        "func-inline": get_func_inline,
        "hoist-from-qif": get_hoist_from_qif,
        "split-qif": get_split_qif,
    }
