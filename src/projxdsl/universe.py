from xdsl.universe import Universe

from projxdsl.dialects import get_all_dialects
from projxdsl.frontend import get_all_frontends
from projxdsl.transforms import get_all_passes

UNIVERSE = Universe(
    all_dialects=get_all_dialects(),
    all_passes=get_all_passes(),
    all_frontends=get_all_frontends(),
)
