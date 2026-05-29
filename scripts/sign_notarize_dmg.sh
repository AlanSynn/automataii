#!/usr/bin/env bash
set -euo pipefail

# Sign and notarize an existing DMG (and the .app inside it).
#
# Usage:
#   scripts/sign_notarize_dmg.sh \\
#     --dmg dist/Automataii-macos-x86_64.dmg \\
#     [--app-name "AutomataII"] \\
#     [--sign "Developer ID Application: Your Name (TEAMID)"] \\
#     [--out dist/Automataii-macos-x86_64-signed.dmg] \\
#     [--only-notarize-dmg] [--skip-dmg-notarize]
#
# Required for notarization (environment variables):
#   APPLE_NOTARY_PROFILE is required. Store it with
#   xcrun notarytool store-credentials before running this script.
#
# Notes:
# - If you only want to notarize the DMG (and not re-sign/repack the app), use --only-notarize-dmg.
# - For full pipeline (sign app -> notarize app -> staple -> rebuild DMG -> notarize DMG -> staple),
#   provide --sign and ensure APPLE_NOTARY_PROFILE is available.

DMG=""
APP_NAME=""
SIGN_ID=""
OUT_DMG=""
ONLY_NOTARIZE_DMG=0
SKIP_DMG_NOTARIZE=0

error() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO]  $*"; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dmg) DMG=${2:-}; shift 2 ;;
    --app-name) APP_NAME=${2:-}; shift 2 ;;
    --sign) SIGN_ID=${2:-}; shift 2 ;;
    --out) OUT_DMG=${2:-}; shift 2 ;;
    --only-notarize-dmg) ONLY_NOTARIZE_DMG=1; shift ;;
    --skip-dmg-notarize) SKIP_DMG_NOTARIZE=1; shift ;;
    -h|--help)
      sed -n '1,60p' "$0" | sed 's/^# \|^#\!.*$//g' ; exit 0 ;;
    *) error "Unknown option: $1" ;;
  esac
done

[[ -n "$DMG" ]] || error "--dmg <path.dmg> is required"
[[ -f "$DMG" ]] || error "DMG not found: $DMG"

ensure_tools() {
  command -v xcrun >/dev/null 2>&1 || error "xcrun not found (install Xcode Command Line Tools)"
  command -v hdiutil >/dev/null 2>&1 || error "hdiutil not found (macOS required)"
}

ensure_notary_creds() {
  [[ -n "${APPLE_NOTARY_PROFILE:-}" ]] || error "APPLE_NOTARY_PROFILE is required for notarization"
}

submit_for_notarization() {
  local target_path=$1
  ensure_notary_creds
  info "Submitting for notarization with APPLE_NOTARY_PROFILE..."
  xcrun notarytool submit "$target_path" \
    --keychain-profile "$APPLE_NOTARY_PROFILE" \
    --wait
}

notarize_and_staple_dmg() {
  local dmg_path=$1
  submit_for_notarization "$dmg_path"
  info "Stapling DMG..."
  xcrun stapler staple "$dmg_path"
}

if [[ $ONLY_NOTARIZE_DMG -eq 1 ]]; then
  ensure_tools
  notarize_and_staple_dmg "$DMG"
  info "Done (DMG notarized and stapled): $DMG"
  exit 0
fi

# Full pipeline
ensure_tools
[[ -n "$SIGN_ID" ]] || error "--sign <Developer ID Application: ...> is required for full pipeline"

MOUNT_DIR=$(mktemp -d "$(basename "$0").mount.XXXXXX")
WORK_DIR=$(mktemp -d "$(basename "$0").work.XXXXXX")
cleanup() {
  set +e
  if mount | grep -q "on $MOUNT_DIR \\("; then
    hdiutil detach "$MOUNT_DIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$MOUNT_DIR" "$WORK_DIR"
}
trap cleanup EXIT

info "Mounting DMG..."
hdiutil attach -nobrowse -noverify -mountpoint "$MOUNT_DIR" "$DMG" >/dev/null

if [[ -z "$APP_NAME" ]]; then
  APP_PATH=$(find "$MOUNT_DIR" -maxdepth 1 -name "*.app" -print -quit)
  [[ -n "$APP_PATH" ]] || error "No .app found in DMG. Provide --app-name"
else
  APP_PATH="$MOUNT_DIR/$APP_NAME.app"
  [[ -d "$APP_PATH" ]] || error "App not found in DMG: $APP_PATH"
fi

APP_BASENAME=$(basename "$APP_PATH" .app)
OUT_DMG=${OUT_DMG:-"${DMG%.dmg}-signed.dmg"}

info "Copying app from DMG to work dir..."
rsync -a "$APP_PATH" "$WORK_DIR/"

APP_LOCAL="$WORK_DIR/$APP_BASENAME.app"

info "Signing app..."
ENTITLEMENTS="$PROJECT_ROOT/packaging/macos/entitlements.plist"
if [[ -f "$ENTITLEMENTS" ]]; then
  codesign --deep --force --options runtime --entitlements "$ENTITLEMENTS" --sign "$SIGN_ID" --timestamp "$APP_LOCAL"
else
  codesign --deep --force --options runtime --sign "$SIGN_ID" --timestamp "$APP_LOCAL"
fi

info "Verifying signature..."
codesign --verify --deep --strict --verbose=2 "$APP_LOCAL"

info "Zipping app for notarization..."
APP_ZIP="$WORK_DIR/$APP_BASENAME.zip"
ditto -c -k --keepParent "$APP_LOCAL" "$APP_ZIP"

info "Submitting app zip for notarization..."
submit_for_notarization "$APP_ZIP"

info "Stapling app..."
xcrun stapler staple "$APP_LOCAL"

info "Creating new DMG: $OUT_DMG"
hdiutil create -volname "$APP_BASENAME" -srcfolder "$APP_LOCAL" -ov -format UDZO "$OUT_DMG" >/dev/null

info "Signing DMG..."
codesign --force --sign "$SIGN_ID" --timestamp "$OUT_DMG"
codesign --verify --verbose=2 "$OUT_DMG"

if [[ $SKIP_DMG_NOTARIZE -eq 0 ]]; then
  notarize_and_staple_dmg "$OUT_DMG"
else
  info "Skipping DMG notarization as requested"
fi

info "Success! New DMG: $OUT_DMG"
