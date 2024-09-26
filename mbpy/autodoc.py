import importlib
import importlib._bootstrap
import logging as log
import re
from pathlib import Path
from typing import Dict, List, Union

import click


def parse_google_docstring(docstring: str) -> Dict[str, str | Dict[str, str] | List[str]]:
    """Parse a Google-style docstring into its components using regex."""
    sections = {"description": "", "args": {}, "returns": "", "examples": []}

    # Extract description
    description_match = re.match(r"(.*?)(?:Args:|Returns:|Examples:|\Z)", docstring, re.DOTALL)
    if description_match:
        sections["description"] = description_match.group(1).strip()

    # Extract args
    args_match = re.search(r"Args:(.*?)(?:Returns:|Examples:|\Z)", docstring, re.DOTALL)
    if args_match:
        args_section = args_match.group(1)
        arg_matches = re.finditer(r"(\w+)\s*:\s*(.+?)(?=\w+\s*:|\Z)", args_section, re.DOTALL)
        for match in arg_matches:
            sections["args"][match.group(1)] = match.group(2).strip()

    # Extract returns
    returns_match = re.search(r"Returns:(.*?)(?:Examples:|\Z)", docstring, re.DOTALL)
    if returns_match:
        sections["returns"] = returns_match.group(1).strip()

    # Extract examples
    examples_match = re.search(r"Examples:(.*)", docstring, re.DOTALL)
    if examples_match:
        sections["examples"] = [line.strip() for line in examples_match.group(1).strip().split("\n") if line.strip()]

    return sections


def generate_feature_list(description: str) -> str:
    """Generate a markdown list of features from the description."""
    features = re.findall(r"- (.*)", description)
    if not features:
        return ""

    markdown = "<p><strong>Key features</strong></p>\n\n<ul>\n"
    for feature in features:
        markdown += f"<li>{feature}</li>\n"
    markdown += "</ul>\n"
    return markdown


def generate_examples(examples: List[str]) -> str:
    """Generate a markdown code block with examples."""
    if not examples:
        return ""

    markdown = "<p><strong>Usage example</strong></p>\n\n<pre><code>\n"
    for example in examples:
        markdown += f"{example}\n"
    markdown += "</code></pre>\n"
    return markdown


def generate_docs(file_path: str, is_package: bool = False, depth=2) -> str:
    """Generate markdown documentation for a given Python file."""
    content = Path(file_path).read_text()

    module_name = Path(file_path).name  # Use .name instead of .stem to include the .py extension

    markdown = f"<details><summary><h2><strong> {module_name}</strong></h2></summary>\n\n"

    # Extract module docstring
    module_doc_match = re.search(r'^("""|\'\'\')(.*?)("""|\'\'\')', content, re.DOTALL | re.MULTILINE)
    if module_doc_match:
        module_doc = module_doc_match.group(2).strip()
        parsed_module_doc = parse_google_docstring(module_doc)
        markdown += f"{parsed_module_doc['description']}\n\n"
        markdown += generate_feature_list(parsed_module_doc["description"])
        markdown += generate_examples(parsed_module_doc["examples"])

        if parsed_module_doc["args"]:
            markdown += f"<details><summary><h{depth+1}>Module Arguments</{depth+1}></summary>\n\n"
            for arg, desc in parsed_module_doc["args"].items():
                markdown += f"- `{arg}`: {desc}\n"
            markdown += "</details>\n\n"

    # Extract classes and functions
    class_matches = re.finditer(r"class\s+(\w+).*?:", content, re.DOTALL)
    func_matches = re.finditer(r"(?<!def\s)(?<!class\s)def\s+(\w+).*?:", content, re.DOTALL)

    classes = []
    functions = []

    for match in class_matches:
        class_name = match.group(1)
        class_content = content[match.start() :]
        class_end = re.search(r"\n(?=\S)", class_content)
        if class_end:
            class_content = class_content[: class_end.start()]

        class_doc_match = re.search(r'("""|\'\'\')(.*?)("""|\'\'\')', class_content, re.DOTALL)
        if class_doc_match:
            class_doc = class_doc_match.group(2).strip()
            parsed_class_doc = parse_google_docstring(class_doc)
            classes.append((class_name, parsed_class_doc, class_content))

    for match in func_matches:
        func_name = match.group(1)
        func_content = content[match.start() :]
        func_end = re.search(r"\n(?=\S)", func_content)
        if func_end:
            func_content = func_content[: func_end.start()]

        func_doc_match = re.search(r'("""|\'\'\')(.*?)("""|\'\'\')', func_content, re.DOTALL)
        if func_doc_match:
            func_doc = func_doc_match.group(2).strip()
            parsed_func_doc = parse_google_docstring(func_doc)
            functions.append((func_name, parsed_func_doc, func_content))

    if classes or functions:
        markdown += "<details open><summary><h3>Contents</h3></summary>\n\n"
        for class_name, _, _ in classes:
            markdown += f"- [class {class_name}](#class-{class_name.lower()})\n"
        for func_name, _, _ in functions:
            markdown += f"- [def {func_name}](#def-{func_name.lower()})\n"
        markdown += "</details>\n\n"

    for class_name, parsed_class_doc, class_content in classes:
        markdown += f"<details><summary><h3><strong>class {class_name}</strong></h3></summary>\n\n"
        markdown += f"{parsed_class_doc['description']}\n\n"
        markdown += generate_feature_list(parsed_class_doc["description"])
        markdown += generate_examples(parsed_class_doc["examples"])

        if parsed_class_doc["args"]:
            markdown += "<details><summary><h4>Arguments</h4></summary>\n\n"
            for arg, desc in parsed_class_doc["args"].items():
                markdown += f"- `{arg}`: {desc}\n"
            markdown += "</details>\n\n"

        # Extract methods
        method_matches = re.finditer(r"def\s+(\w+).*?:", class_content, re.DOTALL)
        for method_match in method_matches:
            method_name = method_match.group(1)
            method_content = class_content[method_match.start() :]
            method_end = re.search(r"\n(?=\S)", method_content)
            if method_end:
                method_content = method_content[: method_end.start()]

            method_doc_match = re.search(r'("""|\'\'\')(.*?)("""|\'\'\')', method_content, re.DOTALL)
            if method_doc_match:
                method_doc = method_doc_match.group(2).strip()
                parsed_method_doc = parse_google_docstring(method_doc)
                markdown += f"<details><summary><h4><strong>def {method_name}</strong></h4></summary>\n\n"
                markdown += f"{parsed_method_doc['description']}\n\n"
                if parsed_method_doc["args"]:
                    markdown += "<details><summary><h5>Arguments</h5></summary>\n\n"
                    for arg, desc in parsed_method_doc["args"].items():
                        markdown += f"- `{arg}`: {desc}\n"
                    markdown += "</details>\n\n"
                if parsed_method_doc["returns"]:
                    markdown += f"<details><summary><h5>Returns</h5></summary>\n\n{parsed_method_doc['returns']}\n</details>\n\n"
                markdown += generate_examples(parsed_method_doc["examples"])
                markdown += "</details>\n\n"
        markdown += "</details>\n\n"

    for func_name, parsed_func_doc, func_content in functions:
        signature = re.search(r"def\s+(\w+\(.*?\))", func_content).group(1)
        markdown += f"<details><summary><h3><strong>def {signature}</strong></h3></summary>\n\n"
        markdown += f"{parsed_func_doc['description']}\n\n"
        if parsed_func_doc["args"]:
            markdown += "<details><summary><h4>Arguments</h4></summary>\n\n"
            for arg, desc in parsed_func_doc["args"].items():
                markdown += f"- `{arg}`: {desc}\n"
            markdown += "</details>\n\n"
        if parsed_func_doc["returns"]:
            markdown += f"<details><summary><h4>Returns</h4></summary>\n\n{parsed_func_doc['returns']}\n</details>\n\n"
        markdown += generate_examples(parsed_func_doc["examples"])
        markdown += "</details>\n\n"

    markdown += "</details>\n\n"
    return markdown


def main(path: str, output_file: str) -> None:
    """Generate markdown documentation for all Python files in a given path."""
    if Path(path).is_file():
        markdown = generate_docs(path)
    elif Path(path).is_dir():
        markdown = f"<details><summary><h1>{Path(path).name}</h2></summary>\n\n"
        contents = Path(path).iterdir()
        contents = [
            file
            for file in contents
            if file.is_file()
            and file.suffix == ".py"
            or (file.is_dir() and not "__pycache__" in str(file))
            or file.suffix == ".ipynb"
            or file.suffix == ".md"
        ]
        markdown += "<h3>Contents</h3>\n\n"
        for file in contents:
            markdown += f"- [{file.name}]({file.name})\n"

        for file in sorted(Path(path).glob("**/*.py")):
            markdown += generate_docs(str(file)) + "\n"
        markdown += "</details>\n\n"
    else:
        spec = importlib.util.find_spec(path)
        if spec is None:
            log.error(f"Invalid path: {path}")
            return None
        module = importlib._bootstrap.module_from_spec(spec)
        return generate_docs(module.__file__)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(markdown)


@click.command()
@click.argument("path", type=str)
@click.argument("output_file", type=str)
def cli(path: str, output_file: str) -> None:
    """Command-line interface for generating markdown documentation.

    Args:
        path (str): The path to the Python file or directory.
        output_file (str): The output file to save the generated markdown.
    """
    main(path, output_file)
    log.info(f"Documentation generated: {output_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        log.info("Usage: python docs2md.py <path> <output_file>")
        sys.exit(1)
    cli(sys.argv[1], sys.argv[2])
