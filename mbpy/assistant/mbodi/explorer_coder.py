"""
The rules of BFSS (Breadth-First Search Strategy) as outlined are:
1. Process One Level at a Time: Explore modules, classes, and functions one level deep before moving on to deeper levels. Modules are higher than classes.
2. Directories are Higher-Level Entities: Treat directories as a higher level than individual modules or classes within those directories.
3. Use Tools Appropriately for Each Level:
  • inspect.getmembers: Use this to list members (classes, functions, etc.) of a given module or class at the current level.
  • pyclbr: Useful for exploring classes and functions defined in a module without loading the module fully.
  • pydoc.splitdoc: To split and format docstrings for better readability.
  • os.path and pathlib: Useful for exploring directory structures and identifying modules at the filesystem level.
4. Confirmation at Each Level: After gathering information at a given level, filter out unwanted elements and confirm before proceeding deeper. Split each node into relevant, irrelevant, and

AVOID:
  • I may not have included all relevant signatures or detailed descriptions for each method.
  • I might have missed certain elements or gone too deep without adhering to the specified depth restriction.
  • There might have been a lack of organization or clarity in presenting the results, making it difficult to distinguish between classes, methods, and other elements.
"""
