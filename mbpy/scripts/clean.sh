#!/usr/bin/env sh
mbclean_usage() {
  printf "Usage: mbclean [OPTION]... [PATTERN]...\n"
  printf "Remove all artifacts from the current directory.\n"
  printf "Options:\n"
  printf "  -h, --help\t\tDisplay this help and exit\n"
  printf "  -a, --all\t\tRemove all artifacts\n"
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  mbclean_usage
fi
cleaned=0
if [ "$1" = "-a" ] || [ "$1" = "--all" ]; then
  for file in ./**/*.py; do
    case "$file" in
    */.venv/*) continue ;;
    */site-packages/*) continue ;;
    esac
    base_name="${file%.py}"
    if [ -f "${base_name}.c" ]; then
      rm -f "${base_name}.c"
      rm -f "${base_name}.cpp"
      echo "Removed ${base_name}.c"
      cleaned=1
    fi
  done
  find . -type f \( -name "*.o" -o -name "*.so" \) ! -path "*/.venv/*" ! -path "*/site-packages/*" -delete

  pyc_count=$(find . -type f -name "*.pyc" ! -path "*/.venv/*" ! -path "*/site-packages/*" | wc -l)
  cache_count=$(find . -type d -name "__pycache__" ! -path "*/.venv/*" ! -path "*/site-packages/*" | wc -l)
  pyclean -e "**/*.pyc" --yes . >/dev/null 2>&1 && pyclean -e "**/__pycache__" --yes . >/dev/null 2>&1
  if ! [ $pyc_count -eq 0 ] || ! [ $cache_count -eq 0 ]; then
    cleaned=1
    [ $? -eq 0 ] && printf "Removed %d .pyc files and %d __pycache__ directories\n" "$pyc_count" "$cache_count"
  fi
  remove_and_check() {
    if [ -d "$1" ] && [ "$(ls -A "$1")" ]; then
      count=$(find "$1" -type f | wc -l | tr -d ' ') # trim spaces
      rm -rf "$1"
      if [ $? -eq 0 ]; then
        echo "Removed $1 ($count files)"
        cleaned=1
      else
        echo "No files to remove in $1"
      fi
    fi
  }

  remove_and_check ./*.egg-info
  remove_and_check ./dist
  remove_and_check ./build/*bdist.*
  remove_and_check ./build/**sdist.*
  remove_and_check ./build/**wheel.*
  remove_and_check ./build/**egg.*
  remove_and_check ./build/**lib.*
  remove_and_check ./build/**temp.*
  shift
fi

count=0
if [ -n "$1" ]; then
  output=$(pyclean -e "$1" --yes . 2>&1)
  status=$?
  count=$(echo "$output" | grep -o 'Total [0-9]* files' | awk '{print $2}')
  [ $status -eq 0 ] && echo "Removed $count files matching pattern: $1" || echo "No files to remove matching pattern: $1"
  [ $count -gt 0 ] && cleaned=1
fi

if [ $cleaned -eq 0 ]; then
  echo "All clean! ✨"
else
  echo "All artifacts removed."
fi
