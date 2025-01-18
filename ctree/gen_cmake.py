import asyncio
import toml




def generate_cmake():
    # Parse the pyproject.toml
    config = toml.load("pyproject.toml")

    # Extract configurations
    data = {
        "project_name": config["build"]["project_name"],
        "cpp_standard": config["build"]["cpp_standard"],
        "output_name": config["build"]["output_name"],
        "source_files": config["sources"]["files"],
        "include_dirs": config["includes"]["directories"],
    }
    from jinja2 import Environment, FileSystemLoader

    # Load and render the Jinja template
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("CMakeLists.jinja")
    cmake_content = template.render(data)

    # Write the rendered content to CMakeLists.txt
    with open("CMakeLists.txt", "w") as cmake_file:
        cmake_file.write(cmake_content)

    print("CMakeLists.txt generated successfully!")


if __name__ == "__main__":
    generate_cmake()




async def buildcpp():
    # Run CMake
    cmake_process = await asyncio.create_subprocess_shell(
    """mkdir build && cd build
        cmake ..
        cmake --build .
""",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await cmake_process.communicate()
    out = out.decode()
    err = err.decode()
    print(f"Output:\n {out}\n\n {'\nError:\n ' + err if err else ''}")


    print("C++ project built successfully!")
if __name__ == "__main__":
    generate_cmake()
