# `torch_ttnn` Module

The `torch_ttnn` module has a `backend` function, which can used with the `torch.compile()` function.

```python
import torch
import torch_ttnn

# A torch Module
class FooModule(torch.Module):
    ...
# Create a module
module = FooModule()
# Compile the module, with ttnn backend
ttnn_module = torch.compile(module, torch_ttnn.backend)
# Running inference
ttnn_module(input_data)
```



# Tracer
The tracer dump the information of fx graph such as node's op_name and shape.

For example, you can run this script to parse the information
```
PYTHONPATH=`pwd` python3 tools/stat_torchvision.py
ls stat/raw
```

By default, the result will be stored at `stat/raw`, and you can run this script to generate the report
```
python3 tools/generate_report.py
ls stat/
```
Now the `stat/` folder have these report
 - `fw_node_count.csv`
 - `bw_node_count.csv`
 - `fw_total_output_size_dist/`
 - `bw_total_output_size_dist/`

The `node_count.csv` show the node with `op_type` appear in the fx graph. This report can help analyze the frequency of op type appear in the graph.

The `total_output_size_dist/` statistics the `op_type`'s output_size distribution from all fx graph recored in `stat/raw`. This report can help analyze the memory footprint durning the calculation of `op_type`.

 - Notice: the default `output_shapes` in `tools/stat_torchvision.py` is `[1,3,224,224]`, which has dependency with `total_output_size_dist/` report.