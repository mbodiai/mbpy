TOOLS = [{
    'type': 'function',
    'function': {
        'name': 'execute_python',
        'description': 'Execute Python code',
        'parameters': {
            'type': 'object',
            'properties': {
                'code': {
                    'type': 'string',
                    'description': 'The Python code to execute',
                },
            },
            'required': ['code'],
        },
    },
},
{
    'type': 'function',
    'function': {
        'name': 'run_shell_command',
        'description': 'Run a shell command',
        'parameters': {
            'type': 'object',
            'properties': {
                'command': {
                    'type': 'string',
                    'description': 'The shell command to run',
                },
            },
            'required': ['command'],
        },
    },
},
{
    'type': 'function',
    'function': {
        'name': 'pip_install',
        'description': 'Install a Python package using pip',
        'parameters': {
            'type': 'object',
            'properties': {
                'package': {
                    'type': 'string',
                    'description': 'The name of the package to install',
                },
            },
            'required': ['package'],
        },
    },
},
{
    'type': 'function',
    'function': {
        'name': 'dispatch_coding_assistant',
        'description': 'Dispatch coding assistant',
        'parameters': {
            'type': 'object',
            'properties': {
                'instruction': {
                    'type': 'string',
                    'description': 'The instruction to dispatch to the coding assistant',
                },
                'subtask1': {
                    'type': 'string',
                    'description': 'The first subtask to dispatch to the coding assistant',
                },
                'subtask2': {
                    'type': 'string',
                    'description': 'The second subtask to dispatch to the coding assistant',
                },
                'subtask3': {
                    'type': 'string',
                    'description': 'The third subtask to dispatch to the coding assistant',
                },
                'subtask4': {
                    'type': 'string',
                    'description': 'The fourth subtask to dispatch to the coding assistant',
                },
            },
            'required': ['instruction'],
        },
    },
},
{
    'type': 'function',
    'function': {
        'name': 'execute_code_with_markdown',
        'description': 'Execute code blocks and return non-code parts',
        'parameters': {
            'type': 'object',
            'properties': {
                'code': {
                    'type': 'string',
                    'description': 'The code blocks to execute'
                    'and return non-code parts',
                },
            },
            'required': ['code'],
        },
    },
},

]


def extract_code_inside_backticks(text: str) -> tuple[list[str], list[str]]:
    r"""Extracts code blocks and non-code parts from a string of text.

    Args:
        text (str): The text to extract code blocks from.

    Returns:
        tuple: A tuple containing two lists - code blocks and non-code parts.

    Example:
        text = "This is a test string. ```python\nprint('Hello, World!')\n```"
        code_blocks, non_code_parts = extract_code_inside_backticks(text)
        print(code_blocks)
        print(non_code_parts)
    """
    code_blocks = []
    non_code_parts = []
    backtick_sequence = '```'
    start = text.find(backtick_sequence)
    last_end = 0

    while start != -1:
        end = text.find(backtick_sequence, start + len(backtick_sequence))
        if end == -1:
            break  # No closing backticks found
        non_code_parts.append(text[last_end:start].strip())
        code_block = text[start + len(backtick_sequence) : end].strip()
        # Remove language specification like 'python' if present
        if code_block.startswith('python'):
            code_block = code_block[len('python') :].strip()
        code_blocks.append(code_block)
        last_end = end + len(backtick_sequence)
        start = text.find(backtick_sequence, last_end)

    non_code_parts.append(text[last_end:].strip())

    return code_blocks, non_code_parts


import subprocess
import sys
import tempfile

from mbodi.main import main as coder_main
from mbpy.commands import run


def run_shell_command(command: str) -> dict[str, str]:
    try:
        output = run(command)
        return {
            'stdout': output,
            'stderr': "",
            'returncode': 0,
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'returncode': -1,
        }

def pip_install(package: str) -> dict[str, str]:
    try:
        output = run(f"pip install {package}")
        return {
            'stdout': output,
            'stderr': '',
            'returncode': 0,
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'returncode': -1,
        }

def dispatch_coding_assistant(instruction: str, subtask1: str | None = None, subtask2: str | None = None, 
                              subtask3: str | None = None, subtask4: str | None = None) -> dict[str, str]:


    
    try:

      subtasks = [{
        "instruction": si,
        "result": run('mbodi --yes --auto-test --test-cmd `pytest tests` --input_history_file hist{i}.txt --chat-history-file chat{i}.txt --msg {instruction}'.format(i=i, instruction=instruction))
      } for i,si in enumerate([subtask1, subtask2, subtask3, subtask4]) if si is not None]
      
      return {
          'stdout': '\n'.join([s['result'] for s in subtasks]),
          'stderr': '',
          'returncode': 0,
      }
    except Exception as e:
      return {
          'stdout': '',
          'stderr': str(e),
          'returncode': -1,
      }
def execute_code_with_markdown(code: str) -> dict[str, str]:
    code_blocks, non_code_parts = extract_code_inside_backticks(code)
    for code in code_blocks:
        result = execute_python(code)
        if result['returncode'] != 0:
            return result
    return {'stdout': '\n'.join(non_code_parts), 'stderr': '', 'returncode': 0}

def execute_python(code: str) -> dict[str, str]:
    try:
        # Write the code to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file_name = temp_file.name
            temp_file.write(code)

        # Execute the script and capture stderr and stdout
        result = subprocess.run([sys.executable, temp_file_name], capture_output=True, text=True, check=False)

        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'returncode': -1,
        }
    finally:
        # Clean up the temporary file
        import os

        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)


#     """
# code, text = extract_code_inside_backticks(code)
# code = '\n'.join(code)
# Save code to file
# with open("script.py", "w") as file:
#     file.write(code)

# Execute the script and capture stderr and stdout
# result = subprocess.run([sys.executable, "script.py"], capture_output=True, text=True, check=False)
# return {
#     "stdout": result.stdout,
#     "stderr": result.stderr,
#     "returncode": result.returncode,
#     # "text": text + ["\n" + "Code executed successfully" if result.returncode == 0 else "Error executing code"],
# }

# # Example usage
# if __name__ == "__main__":
#     text = """some text not code but text```python
# import sys
# print("Hello, World!")
# print("Arguments passed:", sys.argv)```
# more text
#     """
#     code_blocks = extract_code_inside_backticks(text)
#     for code in code_blocks:
#         fetch_and_execute(code)
