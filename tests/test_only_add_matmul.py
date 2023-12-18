import torch
import torch_ttnn
import unittest
from torch_ttnn import ttnn


class AddModule(torch.nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x, y):
        return x + y

    def input_shapes(self):
        return [(4, 4), (4, 4)]


class MatmulModule(torch.nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x, y):
        return torch.matmul(x, y)

    def input_shapes(self):
        return [(3, 4), (4, 5)]


# Nested module for demonstration, verify nested modules work
class AddMatmulModule(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.mm = MatmulModule()

    def forward(self, x, y):
        m = torch.add(x, y)
        return self.mm(m, m)

    def input_shapes(self):
        return [(4, 4), (4, 4)]


class TestModules(unittest.TestCase):
    def setUp(self):
        # Open device 0
        self.device: ttnn.Device = ttnn.open(0)

    def tearDown(self):
        # Close the device
        ttnn.close(self.device)

    def test_add(self):
        m = AddModule()
        input_shapes = m.input_shapes()
        inputs = [torch.rand(shape, dtype=torch.bfloat16) for shape in input_shapes]
        result_before = m.forward(*inputs)
        option = torch_ttnn.TorchTtnnOption(device=self.device)
        # The compilation is lazy, so we need to run forward once to trigger the compilation
        m = torch.compile(m, backend=torch_ttnn.backend(option))
        result_after = m.forward(*inputs)
        option.out_fx_graph.print_tabular()
        
        # Check the graph has be rewritten and contain ttnn ops
        nodes = list(option.out_fx_graph.nodes)
        self.assertTrue(nodes[6].target == ttnn.add)
        self.assertTrue(nodes[6].args[0].target == ttnn.to_device)
        self.assertTrue(nodes[6].args[0].args[0].target == ttnn.from_torch)
        self.assertTrue(nodes[7].target == ttnn.from_device)
        self.assertTrue(nodes[8].target == ttnn.to_torch)
        # Check inference result
        self.assertTrue(torch.allclose(result_before, result_after))

    def test_matmul(self):
        m = MatmulModule()
        input_shapes = m.input_shapes()
        inputs = [torch.rand(shape, dtype=torch.bfloat16) for shape in input_shapes]
        result_before = m.forward(*inputs)
        option = torch_ttnn.TorchTtnnOption(device=self.device)
        # The compilation is lazy, so we need to run forward once to trigger the compilation
        m = torch.compile(m, backend=torch_ttnn.backend(option))
        result_after = m.forward(*inputs)
        option.out_fx_graph.print_tabular()

        # Check the graph has be rewritten and contain ttnn ops
        nodes = list(option.out_fx_graph.nodes)
        self.assertTrue(nodes[6].target == ttnn.matmul)
        self.assertTrue(nodes[6].args[0].target == ttnn.to_device)
        self.assertTrue(nodes[6].args[0].args[0].target == ttnn.from_torch)
        self.assertTrue(nodes[7].target == ttnn.from_device)
        self.assertTrue(nodes[8].target == ttnn.to_torch)
        # Check inference result
        self.assertTrue(torch.allclose(result_before, result_after))


    def test_add_and_matmul(self):
        m = AddMatmulModule()
        input_shapes = m.input_shapes()
        inputs = [torch.rand(shape, dtype=torch.bfloat16) for shape in input_shapes]
        result_before = m.forward(*inputs)
        option = torch_ttnn.TorchTtnnOption(device=self.device)
        # The compilation is lazy, so we need to run forward once to trigger the compilation
        m = torch.compile(m, backend=torch_ttnn.backend(option))
        result_after = m.forward(*inputs)
        option.out_fx_graph.print_tabular()

        # Check the graph has be rewritten and contain ttnn ops
        nodes = list(option.out_fx_graph.nodes)
        self.assertTrue(nodes[6].target == ttnn.add)
        self.assertTrue(nodes[6].args[0].target == ttnn.to_device)
        self.assertTrue(nodes[6].args[0].args[0].target == ttnn.from_torch)
        self.assertTrue(nodes[7].target == ttnn.matmul)
        self.assertTrue(nodes[8].target == ttnn.from_device)
        self.assertTrue(nodes[9].target == ttnn.to_torch)
        # Check inference result
        self.assertTrue(torch.allclose(result_before, result_after))


if __name__ == "__main__":
    unittest.main()