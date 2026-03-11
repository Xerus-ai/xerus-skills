#!/bin/bash
# Bootstrap: Copy skill folders from xerushub source into repo root
# Usage: ./scripts/bootstrap.sh [source_dir]
#
# Only copies folders that have both xerushub.json AND SKILL.md.
# Skill folders live at repo root (not in a skills/ subdirectory)
# so the submodule path marketplace/skills/{slug}/ resolves correctly.
# Run once to populate the repo, then manage skills via git.

SOURCE="${1:-D:/openBot/xerus/xerushub_skills}"
DEST="."

if [ ! -d "$SOURCE" ]; then
    echo "Source directory not found: $SOURCE"
    exit 1
fi

mkdir -p "$DEST"

count=0
skipped=0

for dir in "$SOURCE"/*/; do
    slug=$(basename "$dir")

    # Must have both xerushub.json and SKILL.md
    if [ ! -f "$dir/xerushub.json" ] || [ ! -f "$dir/SKILL.md" ]; then
        skipped=$((skipped + 1))
        continue
    fi

    # Copy entire folder
    mkdir -p "$DEST/$slug"
    cp -r "$dir"/* "$DEST/$slug/" 2>/dev/null
    cp "$dir/xerushub.json" "$DEST/$slug/" 2>/dev/null

    count=$((count + 1))

    if [ $((count % 50)) -eq 0 ]; then
        echo "Progress: $count copied, $skipped skipped"
    fi
done

echo "Done: $count skills copied, $skipped skipped (missing xerushub.json or SKILL.md)"
echo "Next: review skills/ folder, remove unwanted, git add, git push"
