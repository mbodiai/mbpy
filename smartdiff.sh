#!/usr/bin/env bash

# Script: apply_diff_interactively.sh
# Description: Interactively apply each hunk from a diff file.
# Usage: ./apply_diff_interactively.sh [diff_file]
#        If no diff_file is provided, the script reads from standard input.

set -e

# Function to display usage information
usage() {
    echo "Usage: $0 [diff_file]"
    echo "If no diff_file is provided, the script reads from standard input."
}

# Check for help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
    exit 0
fi

# Read diff from file or stdin
if [ -n "$1" ]; then
    DIFF_FILE="$1"
    if [ ! -f "$DIFF_FILE" ]; then
        echo "Error: File '$DIFF_FILE' does not exist."
        exit 1
    fi
else
    DIFF_FILE=$(mktemp)
    if ! cat > "$DIFF_FILE"; then
        echo "Failed to read from stdin."
        exit 1
    fi
fi

# Temporary directory to store individual hunks
TMP_DIR=$(mktemp -d 2>/dev/null)
if [[ ! "$TMP_DIR" || ! -d "$TMP_DIR" ]]; then
    echo "Failed to create temporary directory."
    exit 1
fi
trap 'rm -rf "$TMP_DIR" "$DIFF_FILE"' EXIT

# Check if csplit supports the -b option
if csplit --help 2>&1 | grep -q -- '-b'; then
    # csplit supports -b option
    csplit -f "$TMP_DIR/hunk_" -b '%03d.diff' "$DIFF_FILE" '/^@@/' '{*}' >/dev/null 2>&1
else
    # csplit does not support -b option
    csplit -f "$TMP_DIR/hunk_" "$DIFF_FILE" '/^@@/' '{*}' >/dev/null 2>&1
    # Rename output files to add .diff extension
    for file in "$TMP_DIR"/hunk_*; do
        mv "$file" "$file.diff"
    done
fi

# Check if any hunks were found
if [ ! -e "$TMP_DIR/hunk_00.diff" ]; then
    echo "No hunks found in the diff."
    exit 0
fi

# Iterate over each hunk file
for hunk_file in "$TMP_DIR"/hunk_*.diff; do
    # Display the hunk
    echo "==============================="
    echo "Hunk: $(basename "$hunk_file")"
    echo "==============================="
    cat "$hunk_file"
    echo "Apply this hunk? [y/n/q]"

    # Prompt the user
    while true; do
        echo -n "> "
        read -r choice
        case "$choice" in
            [Yy]* )
                # Apply the hunk
                if patch -p0 < "$hunk_file" >/dev/null 2>&1; then
                    echo "Hunk applied successfully."
                else
                    echo "Failed to apply hunk. Skipping."
                fi
                break
                ;;
            [Nn]* )
                echo "Hunk skipped."
                break
                ;;
            [Qq]* )
                echo "Quitting."
                exit 0
                ;;
            * )
                echo "Please answer y (yes), n (no), or q (quit)."
                ;;
        esac
    done
    echo ""
done

echo "All hunks processed."