import dataclasses
import os
import re
from pathlib import Path

from common import MAX_LISTED_LINES, Check, capture, counterexample

UPSTREAM_TAG = "n9.0.2"
UPSTREAM_VERSION = UPSTREAM_TAG.removeprefix("n")
RELEASE_TAG = re.compile(rf"{re.escape(UPSTREAM_TAG)}-kerao\.([1-9][0-9]*)")
RELEASE_TAG_CHECK = "release tag"
CLEAN_WORKTREE_CHECK = "clean worktree"
DEV_BUNDLE_VERSION = "0"


@dataclasses.dataclass(frozen=True)
class Source:
    root: Path
    commit: str
    version: str
    head_tags: tuple[tuple[str, str], ...]
    changes: tuple[str, ...]

    @property
    def dirty(self) -> bool:
        return bool(self.changes)


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return capture(["git", "-C", str(root), *args], env=env)


def read_source(root: Path) -> Source:
    tags = git(
        root,
        "for-each-ref",
        "--points-at",
        "HEAD",
        "--format=%(refname:strip=2) %(objecttype)",
        "refs/tags",
    )
    return Source(
        root=root,
        commit=git(root, "rev-parse", "HEAD"),
        version=git(root, "describe", "--tags", "--always"),
        head_tags=tuple(tuple(line.split(" ")) for line in tags.splitlines()),
        changes=tuple(
            git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        ),
    )


def release_tag(source: Source) -> str | None:
    """The annotated n9.0.2-kerao.<n> tag at HEAD, or None unless there is exactly one."""
    tags = [
        name
        for name, kind in source.head_tags
        if kind == "tag" and RELEASE_TAG.fullmatch(name)
    ]
    return tags[0] if len(tags) == 1 else None


def bundle_version(source: Source) -> str:
    tag = release_tag(source)
    return RELEASE_TAG.fullmatch(tag)[1] if tag else DEV_BUNDLE_VERSION


def artifact_tag(source: Source, mode: str) -> str:
    tag = release_tag(source) if mode == "release" else None
    return tag or source.version


def check_release_tag(source: Source) -> Check:
    tag = release_tag(source)
    if tag is None:
        found = (
            ", ".join(f"{name} ({kind})" for name, kind in source.head_tags) or "none"
        )
        return Check(
            RELEASE_TAG_CHECK,
            False,
            f"HEAD needs one annotated {UPSTREAM_TAG}-kerao.<n> tag, has: {found}",
        )
    return Check(RELEASE_TAG_CHECK, True, tag)


def check_clean_worktree(source: Source) -> Check:
    shown = "; ".join(source.changes[:MAX_LISTED_LINES])
    more = len(source.changes) - MAX_LISTED_LINES
    return Check(
        CLEAN_WORKTREE_CHECK,
        not source.dirty,
        shown + (f"; {more} more" if more > 0 else ""),
    )


def check_no_version_file(source: Source) -> Check:
    path = source.root / "VERSION"
    return Check(
        "no VERSION file",
        not path.exists(),
        f"{path} overrides git describe" if path.exists() else "",
    )


def check_version_string(source: Source) -> Check:
    return Check(
        "version string", source.version.startswith(UPSTREAM_TAG), source.version
    )


def preconditions(source: Source, mode: str) -> list[Check]:
    checks = [check_version_string(source), check_no_version_file(source)]
    if mode == "release":
        checks += [check_release_tag(source), check_clean_worktree(source)]
    return checks


FAKE_GIT_ENV = {
    "PATH": os.environ["PATH"],
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "self-test",
    "GIT_AUTHOR_EMAIL": "self-test@invalid",
    "GIT_COMMITTER_NAME": "self-test",
    "GIT_COMMITTER_EMAIL": "self-test@invalid",
}


def fake_git(repo: Path, *args: str) -> None:
    git(repo, *args, env=FAKE_GIT_ENV)


def fake_release_checkout(tmp: Path) -> Path:
    repo = tmp / "checkout"
    repo.mkdir()
    fake_git(repo, "init", "-q")
    (repo / "RELEASE").write_text(f"{UPSTREAM_VERSION}\n")
    fake_git(repo, "add", "RELEASE")
    fake_git(repo, "commit", "-q", "-m", "upstream")
    fake_git(repo, "tag", "-a", UPSTREAM_TAG, "-m", UPSTREAM_TAG)
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "kerao")
    fake_git(repo, "tag", "-a", f"{UPSTREAM_TAG}-kerao.1", "-m", "release")
    return repo


@counterexample
def head_one_commit_after_release_tag(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_release_tag(read_source(repo))
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "after the tag")
    return good, check_release_tag(read_source(repo))


@counterexample
def release_tag_is_lightweight(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_release_tag(read_source(repo))
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "after the tag")
    fake_git(repo, "tag", f"{UPSTREAM_TAG}-kerao.2")
    return good, check_release_tag(read_source(repo))


@counterexample
def untracked_file_in_worktree(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_clean_worktree(read_source(repo))
    (repo / "untracked.txt").write_text("stray\n")
    return good, check_clean_worktree(read_source(repo))


@counterexample
def version_file_in_checkout(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_no_version_file(read_source(repo))
    (repo / "VERSION").write_text(f"{UPSTREAM_VERSION}\n")
    fake_git(repo, "add", "VERSION")
    fake_git(repo, "commit", "-q", "-m", "pin the version")
    return good, check_no_version_file(read_source(repo))


@counterexample
def checkout_without_tags(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_version_string(read_source(repo))
    fake_git(repo, "tag", "-d", UPSTREAM_TAG, f"{UPSTREAM_TAG}-kerao.1")
    return good, check_version_string(read_source(repo))
