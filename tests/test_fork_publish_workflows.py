"""Forks must not run jobs that push to upstream registries or releases.

The Docker image names and the Electron release job target debpalash's
GHCR, Docker Hub, and GitHub Releases. A fork's GITHUB_TOKEN cannot publish
there, but the jobs still try. The guard is the repository name, not a
secret check.
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_UPSTREAM = "github.repository == 'debpalash/VoiceStudio'"


def _job_conditions(workflow: Path) -> dict[str, str | None]:
    """Map each top-level job name to its job-level ``if``, if any."""
    conditions: dict[str, str | None] = {}
    current: str | None = None
    in_jobs = False
    for line in workflow.read_text(encoding="utf-8").splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" "):
            break
        if (
            line.startswith("  ")
            and not line.startswith("   ")
            and line.rstrip().endswith(":")
            and not line.lstrip().startswith("#")
        ):
            current = line.strip()[:-1]
            conditions[current] = None
            continue
        if current is not None and line.startswith("    if:"):
            conditions[current] = line.split("if:", 1)[1].strip()
    return conditions


def test_docker_publish_jobs_run_only_on_upstream():
    conditions = _job_conditions(_REPO / ".github/workflows/docker.yml")
    assert conditions["build-and-push"] == _UPSTREAM
    assert conditions["build-and-push-rocm"] == _UPSTREAM


def test_electron_release_job_runs_only_on_upstream():
    conditions = _job_conditions(_REPO / ".github/workflows/electron-release.yml")
    assert conditions["release"] == _UPSTREAM
    # Packaging uploads workflow artifacts with --publish never. It does not
    # create a GitHub Release or push a registry image.
    assert conditions["package"] is None
