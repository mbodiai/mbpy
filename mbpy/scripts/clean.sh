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
  pyclean -e "**/*.pyc" --yes . && pyclean -e "**/__pycache__" --yes . && echo "Removed all .pyc files"
 remove_and_check() {
    if [ -d "$1" ] && [ "$(ls -A "$1")" ]; then
      rm -rf "$1"
      echo "Removed $1"
      cleaned=1
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

fi

if [ $cleaned -eq 0 ]; then
  echo "No artifacts found."
else
  echo "All artifacts removed."
fi