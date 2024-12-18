#!/bin/sh
get_install_cmd() {
    if [ "$(uname -s)" = "Darwin" ]; then
        # Mac OS X platform
        if ! command -v brew >/dev/null 2>&1; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install "$1"
    elif [ "$(uname -s | cut -c1-5)" = "Linux" ]; then
        # GNU/Linux platform
        if ! command -v apt >/dev/null 2>&1; then
            echo "Error: apt package manager not found"
            exit 1
        fi
        sudo apt install -y "$1"
    else
        echo "Unsupported operating system"
        exit 1
    fi
}

# Install conan
echo "Installing conan..."
get_install_cmd "conan"

# Verify installation
if command -v conan > /dev/null 2>&1; then
    echo "Conan installed successfully"
    conan --version
else
    echo "Failed to install conan"
    exit 1
fi