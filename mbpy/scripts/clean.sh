#!/bin/sh

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
  find . -name "*.py" ! -path "*/.venv/*" ! -path "*/site-packages/*" | while read -r file; do
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
  pyclean -e "*.pyc" --yes . >/dev/null 2>&1 && pyclean -e "__pycache__" --yes . >/dev/null 2>&1
  if [ "$pyc_count" -gt 0 ] || [ "$cache_count" -gt 0 ]; then
    cleaned=1
    printf "Removed %d .pyc files and %d __pycache__ directories\n" "$pyc_count" "$cache_count"
  fi

  remove_and_check() {
    if [ -d "$1" ] && [ "$(ls -A "$1" 2>/dev/null)" ]; then
      count=$(find "$1" -type f | wc -l | tr -d ' ')
      rm -rf "$1"
      if [ $? -eq 0 ]; then
        echo "Removed $1 ($count files)"
        cleaned=1
      fi
    fi
  }

  # Check and clean egg/dist info
  for pattern in *.egg-info *.dist-info *.egg; do
    remove_and_check "./$pattern"
  done

  # Check tmp directory
  if [ -d "./tmp" ]; then
    for pattern in egg-info dist-info egg; do
      find ./tmp -name "*.$pattern" -type d -exec sh -c 'remove_and_check "$1"' _ {} \;
    done
  fi

  # Check build directory
  if [ -d "./build" ]; then
    for pattern in bdist sdist wheel egg lib temp; do
      find ./build -name "*.$pattern" -type d -exec sh -c 'remove_and_check "$1"' _ {} \;
    done
  fi

  # Check dist directory
  if [ -d "./dist" ]; then
    remove_and_check ./dist
  fi
  
  shift
fi

# Handle pattern-based cleaning
if [ -n "$1" ]; then
  output=$(pyclean -e "$1" --yes . 2>&1)
  status=$?
  count=$(echo "$output" | grep -o 'Total [0-9]* files' | awk '{print $2}')
  if [ $status -eq 0 ] && [ -n "$count" ]; then
    echo "Removed $count files matching pattern: $1"
    cleaned=1
  else
    echo "No files to remove matching pattern: $1"
  fi
fi

if [ $cleaned -eq 0 ]; then
  echo "All clean! ✨"
else  
  echo "All artifacts removed."
fi