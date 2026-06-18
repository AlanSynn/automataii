from __future__ import annotations

from pathlib import Path


def _auto_release_dispatches_when(release_bot_token_present: bool) -> bool:
    return not release_bot_token_present


def _release_plain_step_runs_when(
    *, event_name: str, publish_external: bool, ota_smoke_passed: bool
) -> bool:
    return event_name == "push" or (
        event_name == "workflow_dispatch" and publish_external and not ota_smoke_passed
    )


def _release_ota_step_runs_when(*, event_name: str, ota_smoke_passed: bool) -> bool:
    return event_name == "workflow_dispatch" and ota_smoke_passed


def test_auto_release_workflow_bumps_and_dispatches_signed_release() -> None:
    workflow = Path(".github/workflows/auto-release.yml").read_text(encoding="utf-8")

    assert "branches:\n      - main" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "github-actions[bot]" in workflow
    assert "Preflight production signing secrets" in workflow
    assert "Missing production signing secret(s)" in workflow
    assert "APPLE_APP_SPECIFIC_PASSWORD" in workflow
    assert '["git", "tag", "--list", "v*"]' in workflow
    assert "re.fullmatch" in workflow
    assert "max(versions)" in workflow
    assert "[minor]" in workflow
    assert "patch += 1" in workflow
    assert "minor += 1" in workflow
    assert "git tag -a" in workflow
    assert 'git commit -m "chore(release): ${RELEASE_TAG}"' in workflow
    assert "[skip ci]" not in workflow
    assert "release_via_tag_push=true" in workflow
    assert "steps.preflight.outputs.release_via_tag_push != 'true'" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "gh workflow run release.yml" in workflow
    assert "-f publish_external=true" in workflow
    assert "-f ota_smoke_passed=false" in workflow
    assert "secrets.RELEASE_BOT_TOKEN || github.token" in workflow


def test_auto_release_has_one_release_owner_per_token_mode() -> None:
    workflow = Path(".github/workflows/auto-release.yml").read_text(encoding="utf-8")
    docs = Path("docs/deployment.md").read_text(encoding="utf-8")

    assert "RELEASE_BOT_TOKEN: ${{ secrets.RELEASE_BOT_TOKEN }}" in workflow
    assert "release_via_tag_push=true" in workflow
    assert "release_via_tag_push=false" in workflow
    assert "if: ${{ steps.preflight.outputs.release_via_tag_push != 'true' }}" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "GH_TOKEN: ${{ secrets.RELEASE_BOT_TOKEN || github.token }}" not in workflow
    assert "PAT-created tag push triggers `release.yml`" in docs
    assert "explicit dispatch is skipped to avoid duplicate releases" in docs


def test_release_trigger_matrix_has_one_owner_for_auto_release_modes() -> None:
    auto_release = Path(".github/workflows/auto-release.yml").read_text(encoding="utf-8")
    release = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "if: ${{ steps.preflight.outputs.release_via_tag_push != 'true' }}" in auto_release
    assert (
        "if: ${{ github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && !inputs.ota_smoke_passed) }}"
        in release
    )
    assert "Reject built-in OTA publish for split macOS DMGs" in release
    assert "use publish-ota.yml for OTA after the release asset exists" in release

    github_token_owner_count = int(_auto_release_dispatches_when(False)) + int(False)
    pat_owner_count = int(_auto_release_dispatches_when(True)) + int(
        _release_plain_step_runs_when(
            event_name="push", publish_external=True, ota_smoke_passed=False
        )
    )
    manual_ota_owner_count = int(
        _release_plain_step_runs_when(
            event_name="workflow_dispatch", publish_external=True, ota_smoke_passed=True
        )
    )

    assert github_token_owner_count == 1
    assert pat_owner_count == 1
    assert manual_ota_owner_count == 0


def test_release_workflow_separates_github_release_from_ota_publish() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "description: 'Publish GitHub Release'" in workflow
    assert "validate-release-ref:" in workflow
    assert "Release version must be vX.Y.Z" in workflow
    assert "needs: validate-release-ref" in workflow
    assert "needs.validate-release-ref.outputs.version" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "actions/setup-python@v4" not in workflow
    assert "GitHub release notarization requires APPLE_ID" in workflow
    assert "xcrun notarytool store-credentials" in workflow
    assert "MOTIONSMITH_OTA_ENABLED" not in workflow
    assert "Reject built-in OTA publish for split macOS DMGs" in workflow
    assert "macos-dmg-*/*" in workflow
    assert "inputs.publish_external && inputs.ota_smoke_passed" in workflow
    assert "Create Release with OTA payload" not in workflow
    assert "Create Release" in workflow
    assert (
        "github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && inputs.publish_external)"
        in workflow
    )
    assert "sparkle-appcast-payload/**" not in workflow
    assert "tag_name: ${{ needs.validate-release-ref.outputs.version }}" in workflow
    assert "Publish OTA payload to MotionSmith Pages repository" not in workflow
