#!/bin/bash

function smart_diff {
  local input1="$1"
  local input2="$2"
  local output_mode="$3"
  local output_file="$4"
  local prompt_replace="$5"

  # Determine if inputs are files or strings
  if [[ -f "$input1" ]]; then
    content1=$(cat "$input1")
  else
    # Properly handle string input with newlines
    content1=$(printf "%b" "$input1")
  fi

  if [[ -f "$input2" ]]; then
    content2=$(cat "$input2")
  else
    # Properly handle string input with newlines
    content2=$(printf "%b" "$input2")
  fi

  # Add line numbers to the first input
  content1_with_linenumbers=$(printf "%s\n" "$content1" | nl -ba)

  # Use a heredoc to avoid string escaping issues in awk
  aligned_content=$(awk '
    BEGIN { 
      split(ENVIRON["content2"], lines, /\n/);
      line_count = length(lines);
    }
    {
      line_num = NR;
      printf "%d\t%s\t%s\n", line_num, $0, (line_num <= line_count ? lines[line_num] : "");
    }' <<<"$content1_with_linenumbers")

  # Handle output based on the specified mode
  case "$output_mode" in
    "file")
      echo "$aligned_content" > "$output_file"
      echo "Aligned content saved to $output_file."
      ;;
    "terminal")
      echo "$aligned_content"
      ;;
    "clipboard")
      echo "$aligned_content" | pbcopy
      echo "Aligned content copied to clipboard."
      ;;
    *)
      echo "Invalid output mode. Use 'file', 'terminal', or 'clipboard'."
      exit 1
      ;;
  esac

  # Optionally prompt to make replacements
  if [[ "$prompt_replace" == "yes" ]]; then
    read -p "Do you want to replace the content of $input1 with the aligned content? (yes/no): " response
    if [[ "$response" == "yes" ]]; then
      echo "$aligned_content" > "$input1"
      echo "Content of $input1 replaced with aligned content."
    fi
  fi
}

# Parse command-line options
while getopts "o:f:p" opt; do
  case $opt in
    o) output_mode="$OPTARG" ;;
    f) output_file="$OPTARG" ;;
    p) prompt_replace="yes" ;;
    *) echo "Usage: $0 [-o output_mode] [-f output_file] [-p] <input1> <input2>"
       echo "  -o output_mode: Specify the output mode ('file', 'terminal', or 'clipboard'). Default is 'terminal'."
       echo "  -f output_file: Specify the output file if output mode is 'file'. Default is 'aligned_output.txt'."
       echo "  -p: Prompt to replace the content of the first input with the aligned content."
       exit 1 ;;
  esac
done
shift $((OPTIND -1))

# Check if two inputs are provided
if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 [-o output_mode] [-f output_file] [-p] <input1> <input2>"
  echo "  -o output_mode: Specify the output mode ('file', 'terminal', or 'clipboard'). Default is 'terminal'."
  echo "  -f output_file: Specify the output file if output mode is 'file'. Default is 'aligned_output.txt'."
  echo "  -p: Prompt to replace the content of the first input with the aligned content."
  exit 1
fi

input1="$1"
input2="$2"

# Set default values for options if not provided
output_mode="${output_mode:-terminal}"
output_file="${output_file:-aligned_output.txt}"
prompt_replace="${prompt_replace:-no}"

# Call the smart_diff function with the provided inputs and options
smart_diff "$input1" "$input2" "$output_mode" "$output_file" "$prompt_replace"