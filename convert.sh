#!/bin/bash

# Function to escape JSON special characters
escape_json() {
    local input="$1"
    input="${input//\\/\\\\}"   # Escape backslashes
    input="${input//\"/\\\"}"   # Escape double quotes
    input="${input//$/\\$}"     # Escape dollar signs
    input="${input//$'\n'/\\n}" # Escape newlines
    echo "$input"
}

# Function to extract all options sections (sections ending with 'options:')
extract_all_options() {
    local help_output="$1"
    # Extract all sections that end with 'options:', case-insensitive
    echo "$help_output" | awk '
        BEGIN {IGNORECASE=1}
        /options:/ {flag=1; next}
        /^[A-Za-z ]+:/ && !/options:/ {flag=0}
        flag
    '
}

# Function to parse options from an options section
parse_options() {
    local options_section="$1"
    local options=()
    local current_option=""

    while IFS= read -r line; do
        # If the line starts with '-', it's a new option
        if [[ $line =~ ^[[:space:]]*(-{1,2}[^\ ]+) ]]; then
            # Save the previous option
            if [[ -n "$current_option" ]]; then
                options+=("$current_option")
            fi
            # Start a new option
            current_option="$(echo "$line" | sed 's/^[[:space:]]*//')"
        elif [[ $line =~ ^[[:space:]]{2,}(.*) && -n "$current_option" ]]; then
            # Continuation of the previous option
            current_option+=" $(echo "${BASH_REMATCH[1]}" | sed 's/^ *//')"
        fi
    done <<< "$options_section"

    # Add the last option
    if [[ -n "$current_option" ]]; then
        options+=("$current_option")
    fi

    # Remove empty entries
    options=("${options[@]/#/}")
    # Output options
    echo "${options[@]}"
}

# Function to extract the Commands section
extract_commands_section() {
    local help_output="$1"
    # Extract lines between 'Commands:' or 'Subcommands:' and the next section
    echo "$help_output" | awk '
        BEGIN {IGNORECASE=1}
        /^Commands:/ || /^Subcommands:/ {flag=1; next}
        /^[A-Za-z ]+:/ && flag {flag=0}
        flag
    '
}

# Function to parse subcommands
parse_subcommands() {
    local commands_section="$1"
    local subcommands=()

    while IFS= read -r line; do
        # Match lines that start with a word (subcommand) followed by multiple spaces
        if [[ $line =~ ^[[:space:]]*([a-zA-Z0-9_-]+)[[:space:]]{2,}(.*) ]]; then
            subcommands+=("${BASH_REMATCH[1]}")
        fi
    done <<< "$commands_section"

    # Remove duplicates
    unique_subcommands=($(printf "%s\n" "${subcommands[@]}" | sort -u))
    echo "${unique_subcommands[@]}"
}

# Recursive function to convert help to JSON
convert_help_to_json() {
    local cmd="$1"
    local level="$2"
    local max_depth=5

    if [[ "$level" -ge "$max_depth" ]]; then
        echo "\"max_depth_reached\": true"
        return
    fi

    # Run the help command
    help_output=$($cmd --help 2>/dev/null)
    if [[ $? -ne 0 ]]; then
        echo "\"error\": \"Failed to run '$cmd --help'\""
        return
    fi

    # Extract description: first paragraph
    description=$(echo "$help_output" | awk 'BEGIN{RS=""} NR==1 {print $0}' | tr '\n' ' ' | sed 's/  */ /g')
    description=$(escape_json "$description")

    # Extract all options sections and parse options
    all_options_sections=$(extract_all_options "$help_output")
    parsed_options=$(parse_options "$all_options_sections")

    # Build JSON options array
    json_options="["
    for opt in "${parsed_options[@]}"; do
        opt_escaped=$(escape_json "$opt")
        json_options+="\"$opt_escaped\","
    done
    # Remove trailing comma if any
    json_options=${json_options%,}
    json_options+="]"

    # Extract Commands section and parse subcommands
    commands_section=$(extract_commands_section "$help_output")
    subcommands=($(parse_subcommands "$commands_section"))

    # Start constructing JSON
    echo "{"
    echo "\"command\": \"$(escape_json "$cmd")\","
    echo "\"description\": \"$description\","
    echo "\"options\": $json_options,"

    # Handle subcommands
    if [[ ${#subcommands[@]} -gt 0 ]]; then
        echo "\"subcommands\": ["
        local first=1
        for subcmd in "${subcommands[@]}"; do
            if [[ $first -ne 1 ]]; then
                echo ","
            fi
            first=0
            # Recursively get details for each subcommand
            subcmd_json=$(convert_help_to_json "$cmd $subcmd" $((level + 1)))
            echo "{"
            echo "\"name\": \"$(escape_json "$subcmd")\","
            echo "\"details\": $subcmd_json"
            echo "}"
        done
        echo "]"
    else
        echo "\"subcommands\": []"
    fi

    echo "}"
}

# Entry point
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <command>"
    exit 1
fi

# Start the conversion with the initial command and level 0
convert_help_to_json "$1" 