import toml

def generate_cmake():
    # Parse the pyproject.toml
    config = toml.load("pyproject.toml")

    # Extract configurations
    project_name = config["build"]["project_name"]
    cpp_standard = config["build"]["cpp_standard"]
    output_name = config["build"]["output_name"]
    source_files = config["sources"]["files"]
    include_dirs = config["includes"]["directories"]

    # Generate CMakeLists.txt content
    cmake_content = f"""
cmake_minimum_required(VERSION 3.15)
project({project_name} LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD {cpp_standard})
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
set(SOURCES
    {"\n    ".join(source_files)}
)

# Include directories
include_directories(
    {"\n    ".join(include_dirs)}
)

# Add executable
add_executable({output_name} ${{SOURCES}})
"""

    # Write the content to CMakeLists.txt
    with open("CMakeLists.txt", "w") as cmake_file:
        cmake_file.write(cmake_content)
    print("CMakeLists.txt generated successfully!")

if __name__ == "__main__":
    generate_cmake()
