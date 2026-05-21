#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
./build_macos.sh

APP_PATH="dist/HireFlow.app"
DMG_PATH="dist/HireFlow.dmg"
TMP_DMG="dist/HireFlow-temp.dmg"

rm -f "$DMG_PATH" "$TMP_DMG"
hdiutil create -volname "HireFlow" -srcfolder "$APP_PATH" -ov -format UDZO "$TMP_DMG"
mv "$TMP_DMG" "$DMG_PATH"
echo "Created $DMG_PATH"
