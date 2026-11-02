#!/usr/bin/env bash
# Ad-hoc sign dist/UniConv.app and wrap it in a DMG with an /Applications shortcut.
# Usage: bash packaging/macos/build_dmg.sh <version>
set -euo pipefail
VERSION="$1"
APP="dist/UniConv.app"
DMG="dist/UniConv-${VERSION}-macos-arm64.dmg"

# Apple Silicon refuses unsigned code; ad-hoc needs no Apple Developer account.
# --deep also covers the bundled pandoc, ffmpeg and ffprobe in Contents/Frameworks/bin.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # drag-to-install target
hdiutil create -volname "UniConv" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "built $DMG"
