## Building the Project

To build the project and compile Cython extensions, simply run:

```bash
python setup.py build_ext --inplace
```

This command will automatically detect and compile all `.pyx` files in the discovered packages.