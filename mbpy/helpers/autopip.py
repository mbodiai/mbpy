import re
import subprocess
import sys
import time
from mbpy.cmd import arun

async def run_command_with_auto_pip(command,
                              max_retries=5,
                              delay=2,
                              enable_gpt=False):
    retries = 0
    modules_installed = set()
    command_stack = [" ".join(command)]

    while retries < max_retries and command_stack:
        current_command = command_stack.pop()
        try:
            if isinstance(current_command, list):
                raise ValueError("Command must be a string, not a list")
            result = await arun(current_command)
            print(result)
            if "No module named" in result:
                match = re.search(r"No module named ['\"]?(\S+)['\"]?", result)
                if match:
                    missing_module = match.group(1).split(".")[0]
                    if missing_module not in modules_installed:
                        try:
                            print(f"Installing {missing_module}...")
                            result = await arun(f"pip install {missing_module.strip('\'')}")
                            print(result)
                            if not "No module named" in result:
                      
                                modules_installed.add(missing_module)
                                command_stack.append(current_command)  # Retry the original command
                                time.sleep(delay)
                        except subprocess.CalledProcessError:
                            retries += 1
                else:
                    print(f"Error: {result}")
                    return e.returncode

        except subprocess.CalledProcessError as e:
            out = (e.stderr or "") + (e.stdout or "")
            match = re.search(r"No module named ['\"]?(\S+)['\"]?", out)

            if match:
                missing_module = match.group(1).split(".")[0]
                if missing_module not in modules_installed:
                    print(f"Installing {missing_module}...")
                    result = await arun(f"pip install {missing_module.strip('\'')}")
                    print(result)
                    if not "No module named" in result:
                        modules_installed.add(missing_module)
                        command_stack.append(
                            current_command)  # Retry the original command
                        time.sleep(delay)
                    else:
                        retries += 1
            else:
                print(f"Error: {out}")
                return e.returncode

    return 1


if __name__ == "__main__":
    import asyncio
    if len(sys.argv) < 2:
        print("Usage: python3 auto_pip_install.py <command> [args...]")
        sys.exit(1)

    # Extract the command and its arguments from the script arguments
    command = sys.argv[1:]
    exit_code = asyncio.run(run_command_with_auto_pip(command))
    sys.exit(exit_code)
