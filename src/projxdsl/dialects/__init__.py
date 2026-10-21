from collections.abc import Callable

from xdsl.ir import Dialect




def get_all_dialects() -> dict[str, Callable[[], Dialect]]:
    """Returns all available dialects."""

    def get_proj():
        from projxdsl.dialects.proj import Proj

        return Proj

    # Add your dialects here to be discovered by `xdsl-opt`
    return {
        "proj": get_proj,
    }
