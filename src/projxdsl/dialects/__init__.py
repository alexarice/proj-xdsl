from collections.abc import Callable

from xdsl.ir import Dialect


def get_all_dialects() -> dict[str, Callable[[], Dialect]]:
    """Returns all available dialects."""

    def get_proj():
        from projxdsl.dialects.proj import Proj

        return Proj

    def get_angle():
        from projxdsl.dialects.angle import Angle

        return Angle

    # Add your dialects here to be discovered by `xdsl-opt`
    return {
        "proj": get_proj,
        "angle": get_angle,
    }
