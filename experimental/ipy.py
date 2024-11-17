import ast
import json
import os
import platform
import subprocess
import threading
import time
import traceback
import webbrowser
from importlib import resources
from embdata.utils import smart_import
import matplotlib.pyplot as plt
import pandas as pd
import requests
from anthropic import Anthropic, APIConnectionError, APIError
from datasets import Dataset, DatasetDict

# from firecrawl import FirecrawlApp
# from flask import Flask, render_template_string
# from huggingface_hub import login
from IPython import get_ipython
from IPython.core.magic import Magics, line_magic, magics_class
from IPython.display import Audio, DisplayHandle, FileLink, FileLinks, IFrame, VimeoVideo, display
from mbodied.agents.language import LanguageAgent
from rich.console import Console
from rich.table import Table
from typing_extensions import TypedDict

    #   - `_repr_html_`: return raw HTML as a string, or a tuple (see below).
    #   - `_repr_json_`: return a JSONable dict, or a tuple (see below).
    #   - `_repr_jpeg_`: return raw JPEG data, or a tuple (see below).
    #   - `_repr_png_`: return raw PNG data, or a tuple (see below).
    #   - `_repr_svg_`: return raw SVG data as a string, or a tuple (see below).
    #   - `_repr_latex_`: return LaTeX commands in a string surrounded by "$",
    #                     or a tuple (see below).
    #   - `_repr_mimebundle_`: return a full mimebundle containing the mapping
    #                          from all mimetypes to data.
    #                          Use this for any mime-type not listed above.
console = Console()

# User-specific configuration
HF_USERNAME = "sebbyjp"
HF_ORG = "mbodiai"
UPLOAD_INTERVAL = 300  # 5 minutes
REPO_NAME = "runtime_history"
UPLOAD_MODE = "append"  # Options: "new_version", "overwrite", "append"
MAX_VERSIONS = 10  # Only used if UPLOAD_MODE is "new_version"

# Initialize API clients
HF_TOKEN = os.environ.get("HF_WRITE")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

if not HF_TOKEN:
    raise ValueError("HF_WRITE environment variable is not set.")
if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY environment variable is not set.")
if not SERPER_API_KEY:
    raise ValueError("SERPER_API_KEY environment variable is not set.")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY environment variable is not set.")

login(HF_TOKEN, add_to_git_credential=True, write_permission=True)
firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# Load commands from a JSON file
COMMANDS = json.loads(resources.open_text("auto", "commands.json"))

# Load tools from a JSON file
TOOLS = json.loads(resources.open_text("auto", "tools.json"))

# Initialize performance data storage
performance_data = []

# Initialize module usage tracking
module_usage = {}
history = []

tries_left = 10
lang = LanguageAgent()

@magics_class
class AIShellMagics(Magics):
    @line_magic
    def aihelp(self, line):
        """Display help for all available commands."""
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="magenta")
        table.add_column("Usage", style="yellow")
        
        for cmd, details in COMMANDS.items():
            table.add_row(cmd, details['description'], details['usage'])
        
        console.print(table)

    @line_magic
    def ask(self,line):
        """Ask GPT-4 a question using the OpenAI API and save the interaction history."""
        if not line:
            raise ValueError("Please provide a question or prompt.")
        global tries_left
        response: str = lang.act(line)
        console.print(response)
        if '```' in response and "run it" in line.lower():
            start = response.find('```')
            end = response[start].find('```')
            response = response[:end+1]
            # Call the appropriate tool
            tool_result, result_code = self.execute_tool("execute_python_in_sandbox", {"code":response})
            console.print('\n tool result: \n' + tool_result)
            
            if result_code:
                if tries_left > 0:
                    tries_left -= 1
                    self.ask(line)
                else:
                    console.print("Max tries reached.")
       

    @line_magic
    def show_history(self, line):
        """Show the history of queries and responses."""
        if not history:
            console.print("[bold red]No history available.[/bold red]")
            return

        for i, entry in enumerate(history, start=1):
            console.print(f"[bold blue]Query {i}:[/bold blue] {entry['query']}")
            console.print(f"[bold green]Response {i}:[/bold green] {entry['response']}\n")

    @line_magic
    def performance(self, line):
        """Display performance data and visualizations."""
        df = pd.DataFrame(performance_data)
        
        # Create histogram
        fig = px.histogram(df, x="execution_time", nbins=20, title="Execution Time Distribution")
        fig.show()
        
        # Display summary statistics
        display(HTML(df.describe().to_html()))
        
        # Display module usage
        module_df = pd.DataFrame.from_dict(module_usage, orient='index', columns=['count'])
        module_df = module_df.sort_values('count', ascending=False)
        display(HTML(module_df.head(10).to_html()))

    @line_magic
    def search_function(self, line):
        """Search for performance data of a specific function."""

        df = pd.DataFrame(performance_data)
        results = df[df['code'].str.contains(line, case=False, na=False)]
        display(HTML(results.to_html()))

    @line_magic
    def websearch(self,line):
        """Perform a web search using Serper or scrape a URL using Firecrawl."""
        if not line:
            raise ValueError("Please provide a search query or URL.")


        try:
            if line.startswith('http://') or line.startswith('https://'):
                # Scrape the URL using Firecrawl
                response = requests.post(
                    'https://api.firecrawl.com/scrape',
                    json={"url": line},
                    headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"}
                )
                response.raise_for_status()
                scraped_data = response.json()
                console.print(f"[bold green]Scraped content from {line}:[/bold green]")
                console.print(scraped_data.get('markdown', 'No markdown content available'))
            else:
               
                url = "https://google.serper.dev/search"

                payload = json.dumps({
                "q": line
                })
                headers = {
                'X-API-KEY': '72ef1dd8dd00890c850539312874405e4a7c6aac',
                'Content-Type': 'application/json'
                }

                response = requests.request("POST", url, headers=headers, data=payload)

                search_results = response.json()
                table = Table(title=f"Web Search Results for: {line}")
                table.add_column("Title", style="cyan")
                table.add_column("URL", style="magenta")
                table.add_column("Snippet", style="green")

                for result in search_results.get('organic', [])[:5]:
                    table.add_row(
                        result.get('title', 'N/A'),
                        result.get('link', 'N/A'),
                        result.get('snippet', 'N/A')
                    )

                console.print(table)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"An error occurred during the web search or scraping: {str(e)}")

    @line_magic
    def ask_claude(self, line):
        """Ask Claude a question and get a response."""
        if not line:
            raise ValueError("Please provide a question for Claude.")

        try:
            response = anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1024,
                temperature=0,
                system="You are Claude, an AI assistant created by Anthropic to be helpful, harmless, and honest. You are currently being called from within an IPython environment.",
                messages=[{"role": "user", "content": line}],
            )
            
            console.print("[bold green]Claude's response:[/bold green]")
            console.print(response.content[0].text)

        except APIConnectionError as e:
            raise ConnectionError(f"Failed to connect to Anthropic API: {str(e)}")
        except APIError as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while calling Claude: {str(e)}")

    @line_magic
    def mistral_tools(self, line):
        global history
        """Ask Mistral a question and allow it to use tools."""
        if not line:
            raise ValueError("Please provide a question for Mistral.")
        class Message(TypedDict):
            role: str
            content: str
        try:
            messages = history + [
                Message(role="user", content=line)
            ]

            chat_response = mistral_client.chat(
                model="mistral-large-latest",
                messages=messages,
                tools=TOOLS
            )

            for choice in chat_response.choices:
                content = choice.message.content
                if content:
                    console.print("[bold green]Mistral's response:[/bold green]")
                    console.print(content)
                    
                tool_calls = choice.message.tool_calls
                if tool_calls:
                    for tool_call in tool_calls:
                        console.print(f"[bold yellow]Mistral is calling the {tool_call.function.name} tool:[/bold yellow]")
                        console.print(tool_call.function.arguments)
                        
                        # Call the appropriate tool
                        tool_result,result_code = self.execute_tool(tool_call.function.name, json.loads(tool_call.function.arguments))
                        
                        # Send the tool result back to Mistral
                        messages.append(complete(role="assistant", content=content))
                        messages.append(ChatMessage(role="tool", content=tool_result, tool_call_id=tool_call.id))
                        
                        chat_response = mistral_client.chat(
                            model="mistral-large-latest",
                            messages=messages,
                            tools=TOOLS
                        ).choices[-1].message.content
                        console.print(f"[bold green]Mistral's response: {content}[/bold green]")

            history = messages + [ChatMessage(role="assistant", content=content)]

        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while calling Mistral: {str(e)}")

    @line_magic
    def claude_tools(self, line):
        """Ask Claude a question and allow it to use tools."""
        if not line:
            raise ValueError("Please provide a question for Claude.")

        try:
           
            claude_tools = []
            for t in TOOLS:
                func = t['function']
                func["input_schema"] = func["parameters"]
                claude_tools.append(func)
            
            response = anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1024,
                temperature=0,
                system="You are Claude, an AI assistant created by Anthropic to be helpful, harmless, and honest. You are currently being called from within an IPython environment.",
                messages=[{"role": "user", "content": line}],
                tools=claude_tools,
            )
            for content in response.content:
                if content.type == 'text':
                    console.print("[bold green]Claude's response:[/bold green]")
                    console.print(content.text)
                elif content.type == 'tool_use':
                    console.print(f"[bold yellow]Claude is calling the {content.name} tool:[/bold yellow]")
                    console.print(content.input)
                    
                    # Call the appropriate tool
                    tool_result = self.execute_tool(content.name, json.loads(content.input))
                    history = [{"role": "user", "content": line},
                                  {"role": "assistant", "content": "Calling " + content.name + " with " + content.input},
                                  {"role": "tool", "tool_call_id": content.id, "name": content.name, "content": tool_result}]
                    # Send the tool result back to Claude
                    response = anthropic_client.messages.create(
                        model="claude-3-5-sonnet-20240620",
                        max_tokens=1024,
                        temperature=0,
                        system="You are Claude, an AI assistant created by Anthropic to be helpful, harmless, and honest. You are currently being called from within an IPython environment.",
                        messages=history,
                        tools=claude_tools,
                    )

        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while calling Claude: {str(e)}")

    def execute_tool(self, tool_name, arguments):
        if tool_name == "execute_python_in_sandbox":
            try:
                result = eval(arguments["code"])
                return result, 0
            except Exception as e:
                return f"error: {e}\n {traceback.format_exc()}", 1
        elif tool_name == "web_search":
            try:
                url = "https://google.serper.dev/search"
                payload = json.dumps({
                    "q": arguments['query'],
                    "num": arguments.get('num_results', 5)
                })
                headers = {
                    'X-API-KEY': SERPER_API_KEY,
                    'Content-Type': 'application/json'
                }
                response = requests.post(url, headers=headers, data=payload)
                return response.text
            except Exception as e:
                return f"Error performing web search: {str(e)}"
        else:
            return f"Unknown tool: {tool_name}"

    @line_magic
    def append_bashrc(self, line):
        """Append a line to the user's .bashrc file."""
        if not line:
            raise ValueError("Please provide the line to append to .bashrc")

        bashrc_path = os.path.expanduser("~/.bashrc")
        try:
            with open(bashrc_path, "a") as bashrc:
                bashrc.write(f"\n{line}\n")
            console.print(f"[bold green]Successfully appended to .bashrc:[/bold green] {line}")
        except IOError as e:
            raise IOError(f"Failed to append to .bashrc: {str(e)}")

    @line_magic
    def copy_last_output(self, line):
        """Copy the last output to the clipboard."""
        ip = get_ipython()
        last_output = ip.user_ns['Out'].get(ip.execution_count-1)
        
        if last_output is None:
            raise ValueError("No output from the last execution to copy")

        try:
            import pyperclip
            pyperclip.copy(str(last_output))
            console.print("[bold green]Last output copied to clipboard.[/bold green]")
        except pyperclip.PyperclipException as e:
            raise RuntimeError(f"Failed to copy to clipboard: {str(e)}")

    @line_magic
    def envvar(self, line):
        """Set or get environment variables."""
        if '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()
            console.print(f"[green]Set environment variable:[/green] {key}={value}")
        elif line:
            value = os.environ.get(line.strip(), "Not set")
            console.print(f"[blue]{line}[/blue] = {value}")
        else:
            for key, value in os.environ.items():
                console.print(f"[blue]{key}[/blue] = {value}")

    @line_magic
    def plot(self, line):
        """Create a quick plot of data."""
        try:
            data = eval(line, get_ipython().user_ns)
            plt.figure(figsize=(10, 6))
            plt.plot(data)
            plt.title(f"Plot of {line}")
            plt.show()
        except Exception as e:
            raise ValueError(f"Failed to plot data: {str(e)}")

    
    def convert_to_pandas(self, dataset):
        """Convert a datasets.Dataset to a pandas DataFrame."""
        # Convert dataset to pandas DataFrame
        df = dataset.to_pandas()

        # Flatten nested columns if any
        for column in df.columns:
            if isinstance(df[column].iloc[0], list) or isinstance(df[column].iloc[0], dict):
                df = df.explode(column).reset_index(drop=True)
                if isinstance(df[column].iloc[0], dict):
                    df = pd.concat(
                        [df.drop(columns=[column]), df[column].apply(pd.Series)], axis=1
                    )
        return df


    @line_magic
    def analyze(self, line):
        """Perform quick data analysis."""
        convert_to_pandas = self.convert_to_pandas
        try:
            # Evaluate the line to get the variable
            data = eval(line, get_ipython().user_ns)

            if isinstance(data, pd.DataFrame):
                console.print("[bold]DataFrame Info:[/bold]")
                console.print(data.info())
                console.print("\n[bold]DataFrame Description:[/bold]")
                console.print(data.describe())
            elif isinstance(data, pd.Series):
                console.print("[bold]Series Info:[/bold]")
                console.print(data.describe())
            elif isinstance(data, Dataset):
                console.print("[bold]Dataset Info:[/bold]")
                console.print(f"Number of rows: {data.num_rows}")
                console.print(f"Number of columns: {len(data.column_names)}")

                # Convert to pandas DataFrame
                df = convert_to_pandas(data)

                # Limit to first 100 rows for analysis
                df = df.head(100)

                console.print("\n[bold]First few rows:[/bold]")
                console.print(df.head())
                console.print("\n[bold]DataFrame Description:[/bold]")
                console.print(df.describe())
            elif isinstance(data, DatasetDict):
                for key, dataset in data.items():
                    console.print(f"\n[bold]Dataset: {key}[/bold]")
                    console.print(f"Number of rows: {dataset.num_rows}")
                    console.print(f"Number of columns: {len(dataset.column_names)}")

                    # Convert to pandas DataFrame
                    df = convert_to_pandas(dataset)

                    # Limit to first 100 rows for analysis
                    df = df.head(100)

                    console.print("\n[bold]First few rows:[/bold]")
                    console.print(df.head())
                    console.print("\n[bold]DataFrame Description:[/bold]")
                    console.print(df.describe())
            else:
                raise ValueError(
                    "Input must be a pandas DataFrame, Series, datasets.Dataset, or datasets.DatasetDict"
                )
        except Exception as e:
            raise ValueError(f"Failed to analyze data: {str(e)}")

    @line_magic
    def execute_command(self, line):
        """Execute a guessed command or suggest the most appropriate one."""
        best_match, details = guess_command(line)

        if best_match:
            console.print(f"[bold green]Executing command:[/bold green] {best_match}")
            console.print(f"[italic]{details['description']}[/italic]")

            # Execute the command
            getattr(self, best_match)(line)
        else:
            console.print("[bold yellow]No matching command found.[/bold yellow]")
            console.print("You can use %aihelp to see available commands.")


def guess_command(input_text):
    """Use simple string matching to guess the most appropriate command."""
    best_match = None
    highest_score = 0

    for cmd, details in COMMANDS.items():
        # Calculate a simple similarity score based on word overlap
        input_words = set(input_text.lower().split())
        description_words = set(details["description"].lower().split())
        score = len(input_words.intersection(description_words))

        if score > highest_score:
            highest_score = score
            best_match = cmd

    return best_match, COMMANDS[best_match] if best_match else None


def upload_to_hub():
    """Upload performance data to Hugging Face Hub."""
    global performance_data
    global console
    global HF_USERNAME
    global REPO_NAME
    import pandas as pd

    from datasets import Dataset
    
    
    df = pd.DataFrame(performance_data)
    repo_id = f"{HF_ORG}/{REPO_NAME}"
    dataset = Dataset.from_pandas(df)
    try:
        dataset.push_to_hub(repo_id, private=True,config_name=HF_USERNAME, token=HF_TOKEN)

  
    
        console.print(f"[bold green]Performance data uploaded to Hugging Face Hub: https://huggingface.co/datasets/{HF_ORG}/{REPO_NAME}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error uploading performance data to Hugging Face Hub: {str(e)}[/bold red]")
        console.print(f"[bold red]{traceback.format_exc()}[/bold red]")
        
# def periodic_upload():
#     """Periodically upload performance data to Hugging Face Hub."""
#     while True:
#         time.sleep(UPLOAD_INTERVAL)
#         upload_to_hub()

# def track_module_usage(code):
#     """Track module usage in the executed code."""
#     try:
#         tree = ast.parse(code)
#         for node in ast.walk(tree):
#             if isinstance(node, ast.Import):
#                 for alias in node.names:
#                     module_usage[alias.name] = module_usage.get(alias.name, 0) + 1
#             elif isinstance(node, ast.ImportFrom):
#                 module_usage[node.module] = module_usage.get(node.module, 0) + 1
#     except:
#         pass  # If parsing fails, we just skip module tracking for this code

# def track_module_usage(code):
#     """Track module usage in the executed code."""
#     try:
#         tree = ast.parse(code)
#         for node in ast.walk(tree):
#             if isinstance(node, ast.Import):
#                 for alias in node.names:
#                     module_usage[alias.name] = module_usage.get(alias.name, 0) + 1
#             elif isinstance(node, ast.ImportFrom):
#                 module_usage[node.module] = module_usage.get(node.module, 0) + 1
#     except:
#         pass  # If parsing fails, we just skip module tracking for this code


def custom_transformer(lines):
    ipython = get_ipython()
    code = "".join(lines).strip()
    if code:
        py_error = None
        sh_error = None

        start_time = time.time()


        # Try to execute as Python code
        try:
            result = eval(compile(ast.parse(code), "<string>", "exec"), ipython.user_ns)

            execution_time = time.time() - start_time
            console.print(
                f"[bold green]Execution time:[/bold green] {execution_time:.6f} seconds"
            )

            # Store performance data
            performance_data.append(
                {
                    "code": code,
                    "execution_time": execution_time,
                    "type": "python",
                    "timestamp": time.time(),
                    "python_version": platform.python_version(),
                    "os": platform.system(),
                    "modules_used": list(set(module_usage.keys())),
                }
            )
            return lines + ["# Output: " + str(result)]  # Python code executed successfully
        except Exception as e:
            py_error = str(e)
            tb = traceback.format_exc()
        # If Python execution fails, try as a shell command
        try:
            start_time = time.time()
            process = subprocess.run(
                code, shell=True, check=True, capture_output=True, text=True
            )
            execution_time = time.time() - start_time
            if process.stdout:
                console.print(process.stdout)  # Print the shell command output using rich
                console.print(
                    f"[bold green]Execution time:[/bold green] {execution_time:.6f} seconds"
                )
            if hasattr(process, "sterr") and process.sterr:
                console.print(f"[bold red]Shell error:[/bold red] {process.stderr}")
    
            # Store performance data
            performance_data.append(
                {
                    "code": code,
                    "execution_time": execution_time,
                    "type": "shell",
                    "timestamp": time.time(),
                    "python_version": platform.python_version(),
                    "os": platform.system(),
                    "modules_used": [],
                }
            )

            return lines + ["# Output: " + process.stdout]  # Shell command executed successfully
        except subprocess.CalledProcessError as e:
            sh_error = e.stderr
            tb = ""

        # If both Python and shell execution fail, use AI to guess the command
        if py_error and sh_error:
            console.print(f"[bold red]Python error:[/bold red] {py_error}")
            console.print(f"[bold red]Shell error:[/bold red] {sh_error}")

            best_match, details = guess_command(code)
            if best_match:
                console.print(
                    f"[bold green]Did you mean to use the '{best_match}' command?[/bold green]"
                )
                console.print(f"[italic]{details['description']}[/italic]")
                console.print(f"Usage: {details['usage']}")
                if details.get("example"):
                    console.print(f"Example: {details['example']}")
            else:
                console.print("[bold yellow]No matching command found.[/bold yellow]")
            console.print(tb)
    return lines  # If no execution or all failed, return the original lines


def load_ipython_extension(ipython):
    ipython.register_magics(AIShellMagics)
    ipython.input_transformers_post.append(custom_transformer)

