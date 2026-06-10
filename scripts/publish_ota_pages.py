#!/usr/bin/env python3
"""Preflight and publish MotionSmith Sparkle OTA payloads to the Pages repo.

This script centralizes the cross-repository GitHub Pages publishing logic that
would otherwise be repeated in release workflows. It deliberately keeps the
release gates strict: credentials must be scoped to ``AlanSynn/motionsmith``,
the appcast must validate before publication, and the live appcast plus assets
must be reachable over HTTPS after push.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
for import_path in (SCRIPT_DIR, SRC_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import check_ota_reachability  # noqa: E402

from automataii.utils.update_config import (  # noqa: E402
    DEFAULT_APPCAST_URL,
    MOTIONSMITH_PAGES_BRANCH,
    MOTIONSMITH_PAGES_REPO,
    UPDATE_SITE_BASE_URL,
    validate_signed_appcast,
)

GITHUB_API_VERSION = "2022-11-28"
GITHUB_KNOWN_HOSTS = (
    "github.com ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
    "github.com ecdsa-sha2-nistp256 "
    "AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7"
    "opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=",
    "github.com ssh-rsa "
    "AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL"
    "9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/"
    "BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YE"
    "FXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMj"
    "A2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FN"
    "yeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQ"
    "pTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj"
    "0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=",
)


class PagesPublishError(RuntimeError):
    """Raised when OTA Pages publication cannot proceed safely."""


@dataclass(frozen=True)
class GitAuth:
    """Git authentication context for the target Pages repository."""

    remote_url: str
    env: dict[str, str]


def check_token_push_permission(token: str, repo: str = MOTIONSMITH_PAGES_REPO) -> None:
    """Fail unless the token can push to the target repository."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            loaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise PagesPublishError(f"MOTIONSMITH_PAGES_TOKEN cannot access {repo}: HTTP {exc.code}") from exc
    permissions = loaded.get("permissions") if isinstance(loaded, dict) else None
    if not isinstance(permissions, dict) or not (
        permissions.get("push") or permissions.get("admin")
    ):
        raise PagesPublishError(f"MOTIONSMITH_PAGES_TOKEN must have push/admin permission on {repo}.")
    print("MotionSmith Pages token has push/admin permission.")


def configure_git_auth(
    env: Mapping[str, str] | None = None,
    *,
    repo: str = MOTIONSMITH_PAGES_REPO,
    temp_dir: Path,
    check_token_permission: bool = False,
) -> GitAuth:
    """Configure HTTPS token or SSH deploy-key auth without mutating global git config."""
    source_env = env or os.environ
    command_env = os.environ.copy()
    command_env.update(source_env)

    token = source_env.get("MOTIONSMITH_PAGES_TOKEN", "").strip()
    deploy_key = source_env.get("MOTIONSMITH_PAGES_DEPLOY_KEY", "")
    command_env.pop("MOTIONSMITH_PAGES_TOKEN", None)
    command_env.pop("MOTIONSMITH_PAGES_DEPLOY_KEY", None)

    if token:
        if check_token_permission:
            check_token_push_permission(token, repo)
        git_config = temp_dir / "gitconfig"
        git_config.write_text(
            f'[url "https://x-access-token:{token}@github.com/"]\n'
            "\tinsteadOf = https://github.com/\n",
            encoding="utf-8",
        )
        command_env["GIT_CONFIG_GLOBAL"] = str(git_config)
        return GitAuth(
            remote_url=f"https://github.com/{repo}.git",
            env=command_env,
        )

    if deploy_key.strip():
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        known_hosts = ssh_dir / "known_hosts"
        ensure_github_known_hosts(known_hosts)
        key_file = temp_dir / "motionsmith_pages_deploy_key"
        key_file.write_text(deploy_key.rstrip("\n") + "\n", encoding="utf-8")
        key_file.chmod(0o600)
        command_env["GIT_SSH_COMMAND"] = (
            f"ssh -i {key_file} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
        )
        return GitAuth(
            remote_url=f"git@github.com:{repo}.git",
            env=command_env,
        )

    raise PagesPublishError(
        "Set either MOTIONSMITH_PAGES_TOKEN or MOTIONSMITH_PAGES_DEPLOY_KEY "
        f"to publish OTA payloads to {repo}."
    )


def ensure_github_known_hosts(path: Path) -> None:
    """Append pinned GitHub host keys if they are not already present."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    with path.open("a", encoding="utf-8") as handle:
        for host_key in GITHUB_KNOWN_HOSTS:
            if host_key not in existing:
                handle.write(host_key + "\n")


def preflight_pages_access(args: argparse.Namespace) -> None:
    """Clone the target Pages repo and dry-run a write to prove permissions."""
    with tempfile.TemporaryDirectory(prefix="motionsmith-pages-preflight-") as temp_name:
        temp_dir = Path(temp_name)
        auth = configure_git_auth(
            repo=args.repo,
            temp_dir=temp_dir,
            check_token_permission=True,
        )
        clone_dir = temp_dir / "motionsmith"
        run_git(["clone", "--depth", "1", "--branch", args.branch, auth.remote_url, str(clone_dir)], auth.env)
        run_git(["config", "user.email", "action@github.com"], auth.env, cwd=clone_dir)
        run_git(["config", "user.name", "GitHub Action"], auth.env, cwd=clone_dir)
        run_git(
            ["commit", "--allow-empty", "-m", "Preflight MotionSmith Pages write access [skip ci]"],
            auth.env,
            cwd=clone_dir,
        )
        run_git(["push", "--dry-run", "origin", f"HEAD:{args.branch}"], auth.env, cwd=clone_dir)


def publish_pages_payload(args: argparse.Namespace) -> None:
    """Validate, copy, commit, push, and live-check the OTA payload."""
    payload_dir = args.payload_dir
    appcast_path = payload_dir / "appcast.xml"
    validation = validate_signed_appcast(
        appcast_path,
        expected_artifact_name=args.expected_artifact,
        expected_version=args.version,
        expected_url_prefix=args.expected_url_prefix,
        payload_dir=payload_dir,
    )
    if not validation.passed:
        for error in validation.errors:
            print(f"::error::{error}", file=sys.stderr)
        raise PagesPublishError("Generated appcast failed validation before Pages publication.")

    with tempfile.TemporaryDirectory(prefix="motionsmith-pages-publish-") as temp_name:
        temp_dir = Path(temp_name)
        auth = configure_git_auth(repo=args.repo, temp_dir=temp_dir)
        clone_dir = temp_dir / "motionsmith"
        run_git(["clone", "--depth", "1", "--branch", args.branch, auth.remote_url, str(clone_dir)], auth.env)
        copy_payload(payload_dir, clone_dir)
        run_git(["config", "user.email", "action@github.com"], auth.env, cwd=clone_dir)
        run_git(["config", "user.name", "GitHub Action"], auth.env, cwd=clone_dir)
        run_git(["add", "-A"], auth.env, cwd=clone_dir)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=clone_dir,
            env=auth.env,
            check=False,
        )
        if diff.returncode == 0:
            print("MotionSmith Pages payload already up to date.")
        elif diff.returncode == 1:
            run_git(["commit", "-m", f"Publish MotionSmith OTA payload {args.version}"], auth.env, cwd=clone_dir)
            run_git(["push", "origin", args.branch], auth.env, cwd=clone_dir)
        else:
            diff.check_returncode()

    ok, results = check_ota_reachability.retry_check(
        args.appcast_url,
        retries=args.retries,
        delay=args.delay,
        timeout=args.timeout,
    )
    for result in results:
        status = "OK" if result.ok else "FAIL"
        detail = "" if result.ok else f": {result.error}"
        print(f"{status} {result.url}{detail}")
    if not ok:
        raise PagesPublishError("Published OTA appcast or referenced assets are not reachable.")


def copy_payload(payload_dir: Path, destination_dir: Path) -> None:
    """Copy payload files into the Pages repository root without deleting unrelated site files."""
    if not payload_dir.exists():
        raise PagesPublishError(f"Payload directory does not exist: {payload_dir}")
    for source in payload_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(payload_dir)
        destination = destination_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def run_git(
    args: list[str],
    env: Mapping[str, str],
    *,
    cwd: Path | None = None,
) -> None:
    """Run a git command with the prepared auth environment."""
    subprocess.run(["git", *args], cwd=cwd, env=dict(env), check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=MOTIONSMITH_PAGES_REPO)
    parser.add_argument("--branch", default=MOTIONSMITH_PAGES_BRANCH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Dry-run target Pages repo write access.")
    preflight.set_defaults(func=preflight_pages_access)

    publish = subparsers.add_parser("publish", help="Publish a validated OTA payload.")
    publish.add_argument("--payload-dir", type=Path, required=True)
    publish.add_argument("--version", required=True)
    publish.add_argument("--expected-artifact", default="MotionSmith-macos-universal2.dmg")
    publish.add_argument("--expected-url-prefix", default=UPDATE_SITE_BASE_URL)
    publish.add_argument("--appcast-url", default=DEFAULT_APPCAST_URL)
    publish.add_argument("--retries", type=int, default=18)
    publish.add_argument("--delay", type=float, default=10.0)
    publish.add_argument("--timeout", type=float, default=20.0)
    publish.set_defaults(func=publish_pages_payload)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (OSError, PagesPublishError, subprocess.CalledProcessError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
