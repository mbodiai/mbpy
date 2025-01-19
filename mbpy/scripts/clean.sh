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
  exit 0
fi

cleaned=0

if [ "$1" = "-a" ] || [ "$1" = "--all" ]; then
  # Clean compiled Python files
  find . -name "*.py" ! -path "*/.venv/*" ! -path "*/site-packages/*" | while read -r file; do
    base_name="${file%.py}"
    if [ -f "${base_name}.c" ]; then
      echo "Found and removing: ${base_name}.c"
      rm -f "${base_name}.c" "${base_name}.cpp"
      echo "Removed ${base_name}.c and ${base_name}.cpp"
      cleaned=1
    fi
  done
  find . -name "*build/" ! -path "*/.venv/*" ! -path "*/site-packages/*" | while read -r file; do
    echo "Found and removing: $file"
    rm -rf "$file"
    cleaned=1
  done

  # Remove object and shared files
  obj_files=$(find . -type f \( -name "*.o" -o -name "*.so" \) ! -path "*/.venv/*" ! -path "*/site-packages/*")
  if [ -n "$obj_files" ]; then
    echo "Removing object and shared files..."
    echo "$obj_files" | wc -l | awk '{print $1 " files removed"}'
    echo "$obj_files" | xargs rm -f
    cleaned=1
  fi

  # Clean pyc and __pycache__
  pyc_count=$(find . -type f -name "*.pyc" ! -path "*/.venv/*" ! -path "*/site-packages/*" | wc -l)
  cache_count=$(find . -type d -name "__pycache__" ! -path "*/.venv/*" ! -path "*/site-packages/*" | wc -l)
  if [ "$pyc_count" -gt 25 ] || [ "$cache_count" -gt 3 ]; then
    
    echo "Removing $pyc_count .pyc files and $cache_count __pycache__ directories"
    pyclean -e "*.pyc" --yes . >/dev/null 2>&1
    pyclean -e "__pycache__" --yes . >/dev/null 2>&1
    cleaned=1
  fi

  # Remove egg-info, dist-info, etc.
  egg_dirs=$(find . -type d \( -name "*.egg-info" -o -name "*.dist-info" \) ! -path "*/.venv/*" ! -path "*/site-packages/*")
  if [ -n "$egg_dirs" ]; then
    echo "$egg_dirs" | wc -l | awk '{print $1 " directories removed"}'
    echo "$egg_dirs" | xargs rm -rf
    cleaned=1
  fi

  # Clean build, dist, and tmp directories
  for dir in build dist tmp; do
    if [ -d "./$dir" ]; then
      file_count=$(find "./$dir" -type f | wc -l)
      echo "Removing $dir with $file_count files"
      rm -rf "./$dir"
      cleaned=1
    fi
  done

  shift
fi

# Handle pattern-based cleaning
if [ -n "$1" ]; then
  files=$(find . -type f -name "$1" ! -path "*/.venv/*" ! -path "*/site-packages/*")
  count=$(echo "$files" | grep -v '^$' | wc -l)
  if [ "$count" -gt 1 ]; then
    echo "$files" | xargs rm -f
    echo "Removed $count files matching pattern: $1"
    cleaned=1
  fi
fi

# Final check for cleaning status
if [ $cleaned -eq 0 ]; then
  echo "All clean! ✨"
else
  echo "All artifacts removed."
fi