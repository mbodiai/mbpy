#!/bin/sh

# Install dependencies based on OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if which apt-get &>/dev/null; then
        sudo apt-get update
        sudo apt-get install -y llvm libomp-dev
    elif which yum &>/dev/null; then
        sudo yum update
        sudo yum install -y llvm libomp-devel
    else
        echo "Error: Unsupported package manager"
        return 1
    fi

    # Set Linux-specific flags
    export CC="clang"
    export CXX="clang++"
    export LDFLAGS="-L/usr/lib/llvm-10/lib -L/usr/lib/x86_64-linux-gnu/libomp"
    export CPPFLAGS="-I/usr/lib/llvm-10/include -I/usr/lib/x86_64-linux-gnu/libomp"
    export CFLAGS="-fopenmp"
    export CXXFLAGS="-fopenmp"

elif [[ "$OSTYPE" == "darwin"* ]]; then
    # Check for Homebrew
    if ! command -v brew &> /dev/null; then
        echo "Error: Homebrew is required but not installed"c
        return 1
    fi

    # Install required packages
    for pkg in llvm libomp; do
        if ! brew list $pkg &>/dev/null; then
            echo "Installing $pkg..."
            brew install $pkg
        fi
    done

    export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
    export LDFLAGS="-L/opt/homebrew/opt/llvm/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/llvm/include"
 
else
    echo "Error: Unsupported operating system"
    return 1
fi

