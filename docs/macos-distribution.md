# macOS Direct Distribution

MotionSmith can be distributed outside the Mac App Store with Developer ID signing,
Apple notarization, ticket stapling, and strict release verification.

## Prerequisites

- macOS with Xcode command line tools.
- Developer ID Application certificate in the signing keychain.
- For universal2 releases, a universal2 Python environment and universal2 binary dependencies.
- Apple notarization credentials.

## Store Notarization Credentials

Preferred local flow:

```bash
make store-notary-profile \
  PROFILE=MotionSmith \
  APPLE_ID=developer@example.com \
  APPLE_TEAM_ID=TEAMID
```

`notarytool` prompts securely for the app-specific password when
`APPLE_APP_SPECIFIC_PASSWORD` is omitted. After storing the profile, run release builds with:

```bash
APPLE_NOTARY_PROFILE=MotionSmith \
make build-macos \
  SIGN_ID="Developer ID Application: Example (TEAMID)"
```

For repeatable local releases, keep only non-secret defaults in the project
`.env`:

```bash
APPLE_NOTARY_PROFILE="MotionSmith"
APPLE_TEAM_ID="TEAMID"
APPLE_ID="developer@example.com"
MACOS_SIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
```

The app-specific password remains in the macOS Keychain profile created by
`notarytool`; do not store it in `.env`.

To verify that the local keychain profile is available before starting a long
release build:

```bash
xcrun notarytool history --keychain-profile "MotionSmith"
```

If this reports `No Keychain password item found for profile`, create the
profile with `make store-notary-profile` first. The profile name is local to the
Mac/keychain where it was stored.

Automated notarization submits only with `APPLE_NOTARY_PROFILE`; the raw
app-specific password is never passed to `notarytool submit`. CI can still store
a temporary keychain profile during the job from `APPLE_ID`, `APPLE_TEAM_ID`,
and `APPLE_APP_SPECIFIC_PASSWORD`, then run the release command with
`APPLE_NOTARY_PROFILE`.

## Release Gate

macOS build targets are distribution targets. Local development should use
`uv run automataii`; if you invoke a `make build-macos*` target, it is expected
to produce a Developer ID signed, notarized, stapled, strictly verified release
artifact.

The repeatable universal release entrypoint is:

```bash
make build-macos          # or equivalently: make release-macos
```

`make build-macos` calls `scripts/release_macos.py`, which loads `.env`, uses
`.venv-universal2` for child `uv` commands by default, preflights the
`notarytool` keychain profile, builds a universal2 DMG, signs it with Developer
ID, notarizes/staples both the app and DMG, runs strict release verification,
mounts the DMG, copies the app out, and runs a packaged smoke scenario.

The convenience build targets route through the same notarized release
automation:

- `make build`
- `make build-macos`
- `make build-macos-native`
- `make build-macos-arm64`
- `make build-macos-x86_64`
- `make release-macos` (alias for `build-macos`)

They do not produce unsigned distributable DMGs. For local development, run the
app directly instead:

```bash
uv run automataii
```

`make build` follows the same rule on macOS and defaults to the universal2
signed + notarized release. Test-only dry runs can print the command sequence,
but release builds do not expose notarization, strict-verification, profile
preflight, or mounted-smoke bypass flags.

The generated DMG is a branded Finder window, not a bare app folder. It includes:

- `MotionSmith.app`
- an `Applications` symlink for drag-and-drop install
- a generated HiDPI background using `resources/icons/AppIcon.png`
- the app icon as the DMG volume icon when `resources/icons/AppIcon.icns` exists

The background is generated during the build, so logo refreshes are picked up by
the next release without committing regenerated binary artwork.

Useful variants:

```bash
# Print the exact commands without running the long build.
make build-macos OPTS="--dry-run"

# Override the signing identity without editing .env.
make build-macos SIGN_ID="Developer ID Application: Example (TEAMID)"

# Re-run strict verification on an existing artifact.
make verify-macos-release \
  ARTIFACT=dist/MotionSmith-macos-universal2.dmg \
  OPTS="--expected-arch universal2 --require-notarization --strict-distribution"
```

`--strict-distribution` keeps the release failed until recursive universal2
Mach-O checks, dependency-closure checks, app signing, DMG container signing,
Gatekeeper assessment, and stapled app/DMG ticket validation pass. The release
script also writes a checksum manifest at
`dist/MotionSmith-macos-universal2-release-manifest.json` and evidence under
`.omx/evidence/macos-release-*`. A signed-but-unstapled DMG is not considered
ready for another Mac.

## References

- Apple Developer ID: https://developer.apple.com/developer-id/
- Apple notarization workflow: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution
- Apple custom notarization workflow: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution/customizing_the_notarization_workflow
