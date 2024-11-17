from pathlib import Path
from mbpy.utils.type_utils import re_iter

KV_PATTERNS ={
    "json": dict(open="{", close="}", kv_delimeter=":"),
    "ros2": dict(open=" ", close=" ", kv_delimeter=":="),
    "key-value": dict(open=" ", close=" ", kv_delimeter="="),
    "command-line": dict(open="--", close=" ", kv_delimeter=" "),
}

class Parser:
    def __init__(self, close: str = "}", open: str = "{", kv_delimeter="=") -> None:
        self.unprocessed_stack = []
        self.close = close
        self.open = open
        self.kv_delimeter = kv_delimeter
        
        
    def push(self, item: str) -> None:
        """Push an item to the stack."""
        self.unprocessed_stack.append(item)
    def pop(self) -> str:
        """Pop an item from the stack."""
        return self.unprocessed_stack.pop()
    
    def match_close(self, item: str):
        """Match a closing symbol."""
        close_idx = item.find(self.close)
        if close_idx == -1:
            return "", item
        return item[:close_idx], item[close_idx + 1:]
    def rmatch_open(self, item: str):
        """Match an opening symbol."""
        open_idx = item.rfind(self.open)
        if open_idx == -1:
            return item, ""
        return item[:open_idx], item[open_idx + 1:]
    
    def parse(self, item: str) -> None:
        """Parse the stack."""
        self.push(item)
        while self.unprocessed_stack:
            before, after = self.match_close(self.pop())
            if after:
                self.push(after)
            if before:
                before, after = self.rmatch_open(before)
                if before:
                    self.push(before)
                if after:
                    yield re_iter(f"(\w+)(\s*{self.kv_delimeter}\s*)(\w+)", after)
                    


def parse_args_from_string(file: str | Path | bytes | None = None, override_args: str = "") -> dict:
    """Parse arguments from a string or file."""
    override_args = override_args.strip()
    file = Path(str(file)) if isinstance(file, str) else file.decode('utf-8') if isinstance(file,bytes) else str(file)

    if (p := Path(file)).exists():
      contents = p.read_text()
    elif isinstance(file, bytes):
      contents = file.decode("utf-8")
    else:
      contents = str(file)
      
    # Iterate over matches for the various patterns
    json_match = re_iter(r"\{.*\}", contents)
    if arg_list.startswith("{") and arg_list.endswith("}"):  # JSON
        import json

        return json.loads(
    elif arg_string.startswith("key") and ":=" in arg_string:  # ROS2-style
        args_list = arg_string.split()
        pairs = {}
        for arg in args_list:
            key, value = arg.split(":=")
            pairs[key.rstrip(":")] = value
        return pairs
    elif arg_string.startswith("key") and "=" in arg_string:  # Key-value pairs
        args_list = arg_string.split()
        pairs = {}
        for arg in args_list:
            key, value = arg.split("=")
            pairs[key] = value
        return pairs
    elif arg_string.startswith("--") and " " in arg_string:  # Command line
        args_list = arg_string.split()
        pairs = {}
        for i in range(0, len(args_list), 2):
            key = args_list[i].lstrip("-")
            value = args_list[i + 1]
            pairs[key] = value
        return pairs
    elif file_contents is not None:  # File
        if arg_string.endswith(".json"):
            import json

            return json.loads(file_contents)
        elif arg_string.endswith(".yaml"):
            import yaml

            return yaml.safe_load(file_contents)
        elif arg_string.endswith(".ros"):
            args_list = file_contents.split()
            pairs = {}
            for arg in args_list:
                key, value = arg.split(":=")
                pairs[key.rstrip(":")] = value
            return pairs
        else:
            raise ValueError("Unsupported file format")
    elif ":" in arg_string:  # YAML string
        import yaml

        try:
            return yaml.safe_load(arg_string)
        except yaml.YAMLError:
            raise ValueError("Unsupported input format")  # noqa: B904
    else:
        raise ValueError("Unsupported input format")
