"""Static checks of the GitHub Actions workflows (no network, runs in milliseconds).

They encode lessons from real failures: a CLI flag that the script does not accept, a long job
without a timeout or whose artifact upload is skipped when the step fails, a matrix that aborts
all siblings on the first failure, and an artifact or branch that one workflow reads but no
workflow produces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def load(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def steps(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(job, st) for job, j in doc["jobs"].items() for st in j.get("steps", [])]


def commands(doc: dict[str, Any]) -> list[str]:
    return [st["run"] for _, st in steps(doc) if "run" in st]


def ids() -> list[str]:
    return [p.name for p in WORKFLOWS]


@pytest.mark.parametrize("path", WORKFLOWS, ids=ids())
def test_every_job_has_a_timeout(path: Path) -> None:
    for name, job in load(path)["jobs"].items():
        assert "timeout-minutes" in job, f"{path.name}:{name} has no job timeout"
        assert job["timeout-minutes"] <= 150


@pytest.mark.parametrize("path", WORKFLOWS, ids=ids())
def test_scripts_and_flags_exist(path: Path) -> None:
    """Every `python x.py --flag` must name a real script that defines that flag."""
    for cmd in commands(load(path)):
        flat = cmd.replace("\\\n", " ")
        for m in re.finditer(r"python\s+(\S+\.py)([^\n|;&]*)", flat):
            script = ROOT / m.group(1)
            assert script.exists(), f"{path.name}: {m.group(1)} does not exist"
            source = script.read_text(encoding="utf-8")
            for flag in re.findall(r"(?<!\S)(--[a-z][a-z0-9-]*)", m.group(2)):
                assert f'"{flag}"' in source, f"{path.name}: {m.group(1)} has no option {flag}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=ids())
def test_matrix_jobs_do_not_cancel_siblings(path: Path) -> None:
    for name, job in load(path)["jobs"].items():
        if "matrix" in job.get("strategy", {}):
            assert job["strategy"].get("fail-fast") is False, f"{path.name}:{name}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=ids())
def test_artifact_uploads_survive_a_failed_step(path: Path) -> None:
    """A result uploaded only if every earlier step passed is lost with the first failure.

    A 36-minute read once died in its final merge and, with no upload, left nothing behind.
    """
    doc = load(path)
    for job, st in steps(doc):
        if st.get("uses", "").startswith("actions/upload-artifact"):
            assert st.get("if") == "always()", f"{path.name}:{job} upload is skipped on failure"


def test_combine_style_jobs_run_even_when_some_matrix_jobs_failed() -> None:
    doc = load(ROOT / ".github" / "workflows" / "waste_data.yml")
    assert doc["jobs"]["combine"]["needs"] == "fetch"
    assert doc["jobs"]["combine"]["if"] == "always()"
    assert doc["jobs"]["fetch"]["strategy"]["max-parallel"] <= 6


def test_download_and_branch_contracts_are_produced_somewhere() -> None:
    """`gh run download -n X` and `git show origin/B:F` must refer to something a workflow makes."""
    uploads: set[str] = set()
    branches: set[str] = set()
    for p in WORKFLOWS:
        doc = load(p)
        for _, st in steps(doc):
            if st.get("uses", "").startswith("actions/upload-artifact"):
                uploads.add(re.sub(r"\$\{\{[^}]*\}\}", "*", st["with"]["name"]))
        for cmd in commands(doc):
            branches.update(re.findall(r"git push --force origin (\S+)", cmd))
    for p in WORKFLOWS:
        for cmd in commands(load(p)):
            for name in re.findall(r"gh run download[^\n]*? -n (\S+)", cmd):
                assert name in uploads, f"{p.name} downloads artifact {name} nobody uploads"
            for br in re.findall(r"git show origin/([\w-]+):", cmd):
                assert br in branches, f"{p.name} reads branch {br} nobody publishes"


def test_dispatch_workflows_serialise_with_a_concurrency_group() -> None:
    for p in WORKFLOWS:
        doc = load(p)
        raw: dict[Any, Any] = doc  # YAML 1.1 parses the key `on` as the boolean True
        triggers: Any = raw.get(True) or raw.get("on") or {}
        if isinstance(triggers, dict) and "workflow_dispatch" in triggers and p.name != "ci.yml":
            assert "concurrency" in doc, f"{p.name} can be dispatched twice at once"


def test_no_credentials_in_workflows() -> None:
    for p in WORKFLOWS:
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"gh[pousr]_[A-Za-z0-9]{20,}", text), p.name
        for line in text.splitlines():
            if re.match(r"\s*TABLEAU_PAT_(NAME|SECRET):", line):
                assert "${{ secrets." in line, f"{p.name}: literal credential"


API_SCRIPTS = (
    "waste_fetch.py", "waste_explore.py", "waste_probe.py", "forest_fetch.py", "hydro_fetch.py",
    "hydro_catalog.py", "airenergy_explore.py", "explore.py", "api_catalog.py", "run_climate.py",
)  # fmt: skip


def test_workflows_that_query_the_shared_api_take_turns_and_stay_polite() -> None:
    """The public API has a small connection pool: 4 jobs x 6 requests made it answer 504."""
    for p in WORKFLOWS:
        doc = load(p)
        cmds = " ".join(commands(doc))
        if not any(s in cmds for s in API_SCRIPTS):
            continue
        group = str(doc.get("concurrency", {}).get("group", ""))
        assert group.startswith("kaur-api"), f"{p.name} can run alongside other API jobs"
        for name, job in doc["jobs"].items():
            parallel = job.get("strategy", {}).get("max-parallel", 1)
            workers = [int(m) for c in commands(doc) for m in re.findall(r"--workers (\d+)", c)]
            assert parallel * max(workers or [1]) <= 8, f"{p.name}:{name} too many requests at once"
