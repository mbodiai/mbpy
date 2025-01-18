# from tree_sitter import Language, Parser
# from pathlib import Path
# import logging
# import os

# # Configure logging
# logging.basicConfig(level=logging.INFO)

# # Path to the built Python shared library
# so_path = Path("~/tree-sitter-languages/python.so").expanduser()

# # Verify that the shared library exists
# if not so_path.exists():
#     raise FileNotFoundError(f"{so_path} does not exist. Please build the language library first.")

# # Initialize the Language object for Python
# try:
#     PYTHON_LANGUAGE = Language(str(so_path), "python")
#     logging.info("Python Language loaded successfully.")
# except Exception as e:
#     logging.error("Failed to initialize Language object.", exc_info=True)
#     raise

# # Initialize the Parser and set the language to Python
# parser = Parser()
# parser.set_language(PYTHON_LANGUAGE)


# def parse_file(file_path):
#     with open(file_path, "rb") as f:
#         code = f.read()
#     tree = parser.parse(code)
#     return tree, code


# def extract_functions(node, code, functions):
#     if node.type == "function_definition":
#         func_name = code[
#             node.child_by_field_name("name").start_byte : node.child_by_field_name("name").end_byte
#         ].decode("utf-8")
#         functions.append(func_name)
#     for child in node.children:
#         extract_functions(child, code, functions)


# def extract_classes(node, code, classes):
#     if node.type == "class_definition":
#         class_name = code[
#             node.child_by_field_name("name").start_byte : node.child_by_field_name("name").end_byte
#         ].decode("utf-8")
#         classes.append(class_name)
#     for child in node.children:
#         extract_classes(child, code, classes)


# def traverse_directory(directory):
#     python_files = []
#     for root, _, files in os.walk(directory):
#         for file in files:
#             if file.endswith(".py"):
#                 python_files.append(os.path.join(root, file))
#     return python_files


# def main(directory):
#     python_files = traverse_directory(directory)
#     logging.info(f"Found {len(python_files)} Python files in '{directory}'.")

#     for file_path in python_files:
#         logging.info(f"Parsing file: {file_path}")
#         try:
#             tree, code = parse_file(file_path)
#             root_node = tree.root_node

#             # Extract Functions
#             functions = []
#             extract_functions(root_node, code, functions)

#             # Extract Classes
#             classes = []
#             extract_classes(root_node, code, classes)

#             # Display the extracted information
#             print(f"\nFile: {file_path}")
#             print("Classes:")
#             for cls in classes:
#                 print(f"  - {cls}")
#             print("Functions:")
#             for func in functions:
#                 print(f"  - {func}")

#         except Exception as e:
#             logging.error(f"Failed to parse {file_path}", exc_info=True)


# if __name__ == "__main__":
#     import sys

#     if len(sys.argv) != 2:
#         print("Usage: python directory_parser.py <directory_path>")
#         sys.exit(1)

#     target_directory = sys.argv[1]
#     main(target_directory)
