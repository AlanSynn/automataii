# MotionSmith build and OTA deployment

MotionSmith has two production release lanes:

1. **Full CI release** (`.github/workflows/release.yml`) builds all platforms in GitHub Actions. This requires macOS signing and notarization secrets in Actions.
2. **Local build + deploy-only OTA** (`.github/workflows/publish-ota.yml`) assumes the macOS DMG was already built, signed, notarized, and uploaded to a GitHub Release. Actions then verifies that DMG, generates the Sparkle appcast, uploads generated OTA metadata to the Release, and can publish the OTA payload to MotionSmith Pages.

Use lane 2 when GitHub Actions does not have `MACOS_CERT_P12` / `MACOS_CERT_PASSWORD` but the local machine can already sign and notarize.

## Secrets and local `.env`

Never commit secret values. `.env` is ignored and should hold local-only values.

### Local build values

```bash
APPLE_TEAM_ID=...
APPLE_NOTARY_PROFILE=MotionSmith
MACOS_SIGN_IDENTITY="Developer ID Application: ..."
SPARKLE_PUBLIC_ED_KEY=...
```

`SPARKLE_PUBLIC_ED_KEY` must be the public key that the released app embeds. The deploy-only workflow compares the downloaded DMG's `SUPublicEDKey` to the configured Actions public key before signing an appcast.

### GitHub Actions secrets for deploy-only OTA

Required for `.github/workflows/publish-ota.yml`:

- `SPARKLE_PRIVATE_ED_KEY` for appcast signing
- `SPARKLE_PUBLIC_ED_KEY` for downloaded DMG metadata verification
- either `MOTIONSMITH_PAGES_DEPLOY_KEY` plus `MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT`, or `MOTIONSMITH_PAGES_TOKEN`, when `publish_pages=true`

Recommended Actions variable:

- `MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT`

The fingerprint is not private material, but keeping it in Actions variables and `.env` avoids hardcoding operator-specific key metadata in tracked code.

### Additional GitHub Actions secrets for full CI build

Required only for `.github/workflows/release.yml` full build:

- `MACOS_CERT_P12`
- `MACOS_CERT_PASSWORD`
- `KEYCHAIN_PASSWORD`
- `MACOS_SIGN_IDENTITY`
- `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` for GitHub-hosted notarization, or a usable pre-provisioned notary profile on a self-hosted runner
- `WINDOWS_CERT_PFX` as a base64-encoded Windows code-signing PFX
- `WINDOWS_CERT_PASSWORD` for the Windows PFX
- `WINDOWS_SIGNTOOL_PATH` only if the Windows runner cannot find `signtool.exe` from the Windows SDK/PATH
- `SPARKLE_PUBLIC_ED_KEY`
- `SPARKLE_PRIVATE_ED_KEY` if publishing OTA in the same workflow

Manual `workflow_dispatch` runs with `publish_external=false` use `WINDOWS_CERT_PFX` when a
GitHub-secret Windows certificate is present. If it is missing, they can fall back to a public,
test-only self-signed Windows certificate. That proves the Windows build/sign/run path on
`windows-latest` and checks the Authenticode signature is present, but a self-signed certificate is not a trusted public release signature.
Those non-publishing smoke runs skip the signed macOS DMG job so Windows evidence can be collected
without Apple signing secrets. Tagged releases and `publish_external=true` runs still require the
macOS signing/notarization secrets.

## Local signed Windows build

Windows releases are built on Windows because PyInstaller is not a cross-compiler. The release
artifact is a zip with signed `MotionSmith.exe` at the zip root:

```powershell
$env:WINDOWS_CERT_PASSWORD = "..."
make build-windows WINDOWS_CERTIFICATE=windows-cert.pfx

# Equivalent direct command:
uv sync --group build
uv run python scripts/build_windows.py --sign --certificate windows-cert.pfx --cert-password-env WINDOWS_CERT_PASSWORD --verify-signature
```

Expected artifact:

```text
dist/MotionSmith-windows.zip
```

For GitHub Actions, store `WINDOWS_CERT_PFX` as base64 PFX content and
`WINDOWS_CERT_PASSWORD` as the PFX password. Production/tagged releases fail before upload if
either secret is missing, so unsigned Windows artifacts are not published by accident. Production
builds also run SignTool trust-chain verification. The Windows job expands the signed zip and runs
`MotionSmith.exe --scenario blueprint-export` on the Windows runner before uploading the artifact.
After upload, a separate Windows runner downloads the `windows-release` artifact, extracts it,
runs the root `MotionSmith.exe --scenario blueprint-export`, and verifies the manifest. This proves
the same zip runs away from the build machine without a separate installer.
The bundled WinSparkle download is SHA256-verified before its DLL is staged and signed.

## Windows user run path

For nearby users or research participants:

1. Download `MotionSmith-windows.zip` from the GitHub Actions artifact or Release.
2. Extract the zip.
3. Double-click `MotionSmith.exe`.

Do not run `MotionSmith.exe` from inside the zipped folder; extract the zip first. Self-signed
research/test certificates can still trigger Windows SmartScreen; use a CA-issued
`WINDOWS_CERT_PFX` for a smoother trusted public release.

## Local signed/notarized macOS build

Build a production DMG locally with the same Sparkle public key that will be configured in Actions:

```bash
set -a
source .env
set +a

uv sync --group dev
uv run python scripts/build_macos.py \
  --arch universal2 \
  --sign "$MACOS_SIGN_IDENTITY" \
  --notarize \
  --verify-release \
  --strict-distribution
```

Expected universal artifact:

```text
dist/MotionSmith-macos-universal2.dmg
```

If you intentionally build a different architecture, pass that exact asset name to the deploy-only workflow.

## Upload local DMG to a GitHub Release

GitHub Actions `workflow_dispatch` cannot directly receive a local binary upload. Upload the locally built DMG to a GitHub Release first:

```bash
VERSION=v0.1.1
DMG=dist/MotionSmith-macos-universal2.dmg

# Create the release if it does not exist.
gh release create "$VERSION" "$DMG" \
  --repo AlanSynn/automataii \
  --target main \
  --generate-notes

# Or update an existing release asset.
gh release upload "$VERSION" "$DMG" \
  --repo AlanSynn/automataii \
  --clobber
```

Optional release notes can be uploaded as a separate `.html` / `.htm` asset and passed as `release_notes_asset_name` to the workflow. Use exact asset names only; glob patterns are rejected. Release notes must not be archives or DMGs because the OTA workflow stages and signs only one verified DMG.

## GitHub Actions deploy-only OTA

After the DMG exists as a release asset, run:

```bash
gh workflow run publish-ota.yml \
  --repo AlanSynn/automataii \
  -f version=v0.1.1 \
  -f dmg_asset_name=MotionSmith-macos-universal2.dmg \
  -f publish_pages=true \
  -f ota_smoke_passed=true
```

The workflow will:

1. Download the exact named DMG release asset.
2. Reject non-DMG DMG inputs, glob-style asset names, non-HTML release notes, and ambiguous staging if any extra `.dmg` file is present after all optional assets are downloaded.
3. Install pinned Sparkle 2.9.3.
4. Verify the downloaded DMG is signed, notarized, strict-distribution-ready, and OTA-ready via `scripts/verify_macos_release.py`.
5. Mount the DMG and compare the app's `SUPublicEDKey` to the configured `SPARKLE_PUBLIC_ED_KEY`.
6. Generate a signed `appcast.xml` using Sparkle's official `generate_appcast`.
7. Validate version, HTTPS URL prefix, EdDSA signature presence, and local payload references.
8. Upload generated OTA metadata, excluding the DMG, back to the GitHub Release.
9. If `publish_pages=true`, preflight write access to `AlanSynn/motionsmith` and publish the payload to Pages.
10. Check live HTTPS reachability for the published appcast and assets.

Keep `ota_smoke_passed=false` until the candidate local build and update path have been tested. The flag is a deliberate manual release gate and attests that the configured Sparkle public/private keys are intended for this release.

## Fully local OTA publication

If Actions is unavailable, the same existing scripts can publish from the local machine.

```bash
set -a
source .env
set +a

VERSION=v0.1.1
DMG=dist/MotionSmith-macos-universal2.dmg
PAYLOAD=signed-appcast-local

python3 scripts/install_sparkle.py --output-dir .sparkle > .sparkle-env
SPARKLE_GENERATE_APPCAST=$(awk -F= '/^generate_appcast=/{print $2}' .sparkle-env)

python3 scripts/verify_macos_release.py "$DMG" \
  --require-notarization \
  --strict-distribution \
  --require-ota \
  --expected-appcast-url https://alansynn.com/motionsmith/appcast.xml

python3 scripts/generate_appcast.py production \
  --artifact "$DMG" \
  --output-dir "$PAYLOAD" \
  --download-url-prefix https://alansynn.com/motionsmith/ \
  --link https://alansynn.com/motionsmith/ \
  --expected-artifact "$(basename "$DMG")" \
  --expected-version "$VERSION" \
  --sparkle-generate-appcast "$SPARKLE_GENERATE_APPCAST" \
  --private-key-env SPARKLE_PRIVATE_ED_KEY

python3 scripts/validate_appcast.py "$PAYLOAD/appcast.xml" \
  --expected-artifact "$(basename "$DMG")" \
  --expected-version "$VERSION" \
  --expected-url-prefix https://alansynn.com/motionsmith/ \
  --payload-dir "$PAYLOAD"

# Use either a Pages deploy key or a token with push/admin permission.
export MOTIONSMITH_PAGES_TOKEN="$(gh auth token)"
python3 scripts/publish_ota_pages.py preflight
python3 scripts/publish_ota_pages.py publish \
  --payload-dir "$PAYLOAD" \
  --version "$VERSION" \
  --expected-artifact "$(basename "$DMG")" \
  --expected-url-prefix https://alansynn.com/motionsmith/ \
  --appcast-url https://alansynn.com/motionsmith/appcast.xml
```

Use the local path only after confirming the DMG is signed, notarized, and built with the configured `SPARKLE_PUBLIC_ED_KEY`.

## Current operational notes

- Pages deployment credentials are configured for Actions.
- Sparkle EdDSA signing and public verification credentials are configured for Actions.
- Full CI macOS signing/notarization remains blocked until `MACOS_CERT_P12`, `MACOS_CERT_PASSWORD`, `KEYCHAIN_PASSWORD`, `MACOS_SIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, and `APPLE_APP_SPECIFIC_PASSWORD` are available in Actions.
- GitHub-hosted macOS runners create a fresh temporary notary profile per run; profile-only notarization without Apple ID credentials is not supported for public releases.
- The deploy-only workflow does not need Apple signing/notarization secrets because it never builds the app.

## Automatic GitHub release on push

Pushes to `main` run `.github/workflows/auto-release.yml`:

- default bump: `0.0.1` patch (`v0.1.0` -> `v0.1.1`)
- bigger bump: include `[minor]`, `#minor`, `release: minor`, or `bump: minor` in the commit message (`v0.1.9` -> `v0.2.0`)
- the workflow commits the new `pyproject.toml` version and creates `vX.Y.Z`
- without `RELEASE_BOT_TOKEN`, it explicitly dispatches `release.yml` because GitHub suppresses most workflow runs caused by `GITHUB_TOKEN`
- with `RELEASE_BOT_TOKEN`, the PAT-created tag push triggers `release.yml`, so explicit dispatch is skipped to avoid duplicate releases
- if production signing secrets are missing, it fails before changing `pyproject.toml` or creating a tag

`release.yml` builds the GitHub Release in Actions for strict `vX.Y.Z` tags only. It only publishes the Sparkle/Pages OTA payload when `ota_smoke_passed=true`; auto push releases dispatch with `ota_smoke_passed=false`.

Required production signing secrets before public releases can pass:

- macOS: `MACOS_CERT_P12`, `MACOS_CERT_PASSWORD`, `KEYCHAIN_PASSWORD`, `MACOS_SIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, and `APPLE_APP_SPECIFIC_PASSWORD`; `APPLE_NOTARY_PROFILE` is optional and defaults to `MotionSmithNotary`
- Windows: CA-issued `WINDOWS_CERT_PFX` and `WINDOWS_CERT_PASSWORD`
- Optional if branch protection blocks the built-in token: `RELEASE_BOT_TOKEN` with contents/tag-push permission
