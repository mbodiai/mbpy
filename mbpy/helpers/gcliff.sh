# # For conventional commits, grouped by type
# git log --format="%s" | grep -E "^(feat|fix|docs|refactor|test):" | sort -k1,1 -t":"

# # For a more detailed changelog with dates
# git log --pretty=format:"### %ad%n* %s" --date=short

# # For commits since last tag
# # git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"* %s"

# git log --pretty=format:"%ad | %s" --date=short | awk -F'|' '{ printf("* %s - %s\n", $1, $2) }'

# #!/bin/bash

echo "# Git Changes Overview"
echo "## Modified Modules"
echo

# Show changed directories
echo "### Changed Directories"
git log --name-only --pretty=format: | sort -u | awk -F/ '{print $1}' | sort -u | sed 's/^/* /'

echo "\n## Recent Changes by Type"

# Conventional commits breakdown
echo "\n### Features"
git log --format="%s" | grep "^feat" | sed 's/^/* /'

echo "\n### Bug Fixes"
git log --format="%s" | grep "^fix" | sed 's/^/* /'

echo "\n### Documentation Needs"
# Files changed without corresponding doc changes
git log --name-only --pretty=format: | grep -v "\.md$" | sort -u | sed 's/^/* /'

echo "\n## Stats"
# Show commit statistics
git shortlog -sn --no-merges

echo "\n## Most Changed Files"
git log --pretty=format: --name-only | sort | uniq -c | sort -rg | head -10 | sed 's/^/* /'