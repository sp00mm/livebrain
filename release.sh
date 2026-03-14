#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

read_version() {
    python3 -c "import json; print(json.load(open('version.json'))['version'])"
}

bump_version() {
    local current="$1"
    local part="$2"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$current"

    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
        *) echo "Invalid bump type: $part (use patch, minor, or major)"; exit 1 ;;
    esac

    echo "${major}.${minor}.${patch}"
}

write_version() {
    python3 -c "
import json
data = json.load(open('version.json'))
data['version'] = '$1'
with open('version.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
}

BUMP=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bump) BUMP="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

VERSION=$(read_version)

if [[ -n "$BUMP" ]]; then
    OLD_VERSION="$VERSION"
    VERSION=$(bump_version "$VERSION" "$BUMP")
    write_version "$VERSION"
    echo "Bumped version to ${VERSION}"

    WEBSITE_HTML="${SCRIPT_DIR}/../website/index.html"
    if [[ -f "$WEBSITE_HTML" ]]; then
        sed -i '' "s/Livebrain-${OLD_VERSION}.dmg/Livebrain-${VERSION}.dmg/g" "$WEBSITE_HTML"
        echo "Updated website download links to ${VERSION}"
    fi
fi

echo ""
echo "Building Livebrain v${VERSION}..."
echo ""

./build.sh

echo ""
echo "==================================="
echo "Release Summary"
echo "==================================="
echo "Version:  ${VERSION}"
echo "DMG:      ${SCRIPT_DIR}/Livebrain-${VERSION}.dmg"
echo ""
echo "Next steps:"
echo "  1. Upload DMG to server:  cd ../scripts && ./deploy-app.sh"
echo "  2. Server version.json will be updated automatically by deploy-app.sh"
echo ""
