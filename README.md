## 2017/08/21 (Tsun-Yi Yang)
+ Fix relu problem
+ Add example convertion file form torch to caffe: convert.lua

## How to convert torch model to caffe model?
```
Step.1
Change the name inside convert.lua

Step.2
th convert.lua
```

# Mocha: Convert torch model to/from caffe model easily
Caffe: load with Python.  
Torch: load with Lua.

Q. How to connect Python & Lua code?  
A. We don't need directly interact Python code with Lua code, which is complex.
We use intermediate file exchange, the model parameters are saved to disk layer
by layer as `.npy` file, and then loaded to caffe/torch separately.

TODO:
- Caffe split layer -> Torch ConcatTable
- PReLU
- More tests
