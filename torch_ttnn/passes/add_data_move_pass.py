import torch
import ttnn
from torch.fx.passes.infra.pass_base import PassBase, PassResult


def is_function_call(node) -> bool:
    if not isinstance(node, torch.fx.node.Node):
        return False
    return node.op == "call_function"


# For operations limitations
# See https://github.com/tenstorrent-metal/tt-metal/blob/main/ttnn/README.md?plain=1#L19
def is_tt_compute(node) -> bool:
    if not is_function_call(node):
        return False
    return node.target in set(
        [
            ttnn.add,
            ttnn.matmul,
            ttnn.sub,
            ttnn.mul,
            ttnn.softmax,
            ttnn.tanh,
            ttnn.reshape,
            ttnn.permute,
        ]
    )


def is_tt_data_move(node) -> bool:
    if not is_function_call(node):
        return False
    return node.target in [
        ttnn.from_device,
        ttnn.to_device,
        ttnn.from_torch,
        ttnn.to_torch,
    ]


def is_tt(node):
    return is_tt_compute(node) or is_tt_data_move(node)


def should_add_data_move_in(src_node, dst_node) -> bool:
    if isinstance(src_node, (int, float, list, tuple)):
        return False
    return is_tt_compute(dst_node) and not is_tt(src_node)


def should_add_data_move_out(src_node, dst_node) -> bool:
    return is_tt_compute(src_node) and not is_tt(dst_node)


def insert_node_between(src_node, dst_idx, dst_node, new_nodes):
    """
    Insert new_node between src_node and dest_node's dst_idx-th arg

    If dst_node is output, the args is stored in dst_node.args[0], and it is a tuple,
    so we need to check if dst_node is output and handle it separately.
    """
    new_nodes[0].update_arg(0, src_node)
    if dst_node.op != "output":
        dst_node.update_arg(dst_idx, new_nodes[-1])
    else:
        old_arg = dst_node.args[0]
        new_arg = list(old_arg)
        new_arg[dst_idx] = new_nodes[-1]
        dst_node.update_arg(0, tuple(new_arg))


def try_add_data_move_in(src_node, dst_idx, dst_node, device) -> bool:
    if not should_add_data_move_in(src_node, dst_node):
        return False

    g = dst_node.graph
    with g.inserting_before(dst_node):
        from_torch = g.call_function(ttnn.from_torch, (src_node,))
        to_device = g.call_function(ttnn.to_device, (from_torch, device))

    insert_node_between(src_node, dst_idx, dst_node, [from_torch, to_device])
    return True


def try_add_data_move_out(src_node, dst_idx, dst_node) -> bool:
    if not should_add_data_move_out(src_node, dst_node):
        return False

    g = dst_node.graph
    with g.inserting_before(dst_node):
        from_device = g.call_function(ttnn.from_device, (src_node,))
        row_major_layout = g.call_function(
            ttnn.to_layout, (from_device, DummyTtnnRowMajorLayout())
        )
        to_torch = g.call_function(ttnn.to_torch, (row_major_layout,))

    insert_node_between(src_node, dst_idx, dst_node, [from_device, to_torch])
    return True


# See https://docs.google.com/document/d/1r2D4AagoeTRjEmXFnWzzafaWQkf-8hlIbX2ze-JAUFo/edit#heading=h.zad9rwqjv6cr
class DummyDevice:
    def __repr__(self):
        return f"ttnn_Specified_Device"


class DummyTtnnRowMajorLayout:
    def __repr__(self):
        return f"ttnn_ROW_MAJOR_LAYOUT"


class AddDataMovePass(PassBase):
    def call(self, gm: torch.fx.GraphModule):
        modified = False
        device = DummyDevice()
        i = 0
        nodes = list(gm.graph.nodes)
        for node in nodes:
            args = node.args[0] if node.op == "output" else node.args
            for idx, arg in enumerate(args):
                if try_add_data_move_in(arg, idx, node, device):
                    i += 1
                if try_add_data_move_out(arg, idx, node):
                    i += 1

        modified = i > 0
        return PassResult(gm, modified)
