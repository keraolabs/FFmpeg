#!/usr/bin/env python3
"""Build the kerao FFmpeg libraries for Apple platforms.

python3 kerao/build.py --output DIR --mode release|dev
python3 kerao/build.py --self-test
"""

import sys

MIN_PYTHON = (3, 11)

if sys.version_info < MIN_PYTHON:
    sys.exit(
        f"build.py needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, found {sys.version.split()[0]}"
    )

import argparse
import dataclasses
import difflib
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMITTED_CONFIGURE = ROOT / "kerao" / "configure"
SOURCE_PLACEHOLDER = "<source>"

UPSTREAM_TAG = "n9.0.2"
RELEASE_TAG = re.compile(rf"{re.escape(UPSTREAM_TAG)}-kerao\.[1-9][0-9]*")
EXPECTED_LICENSE = "LGPL version 2.1 or later"
COMPONENTS_HEADER = "External libraries:"
MAX_LISTED_LINES = 5
CONFIG_LOG_TAIL_LINES = 40


@dataclasses.dataclass(frozen=True)
class Slice:
    identifier: str
    sdk: str
    target: str


SLICES = (Slice("macos-arm64", "macosx", "arm64-apple-macos14.0"),)

LIBRARIES = ("avutil", "avcodec", "avformat", "swresample")
EXCLUDED_LIBRARIES = ("avdevice", "avfilter", "swscale")
DEMUXERS = ("mov",)
PARSERS: dict[str, str] = {}
BSFS: dict[str, str] = {}
HWACCELS: dict[str, str] = {}
PREFIX = "/usr/local"


def component_args(kind: str, names: dict[str, str]) -> list[str]:
    return [f"--enable-{kind}={','.join(names)}"] if names else []


def configure_args(slice_: Slice, sdk_path: Path) -> list[str]:
    xcrun = f"xcrun --sdk {slice_.sdk}"
    target = f"-target {slice_.target}"
    return [
        f"--prefix={PREFIX}",
        "--install-name-dir=@rpath",
        "--disable-everything",
        "--disable-autodetect",
        "--disable-programs",
        "--disable-doc",
        *(f"--disable-{name}" for name in EXCLUDED_LIBRARIES),
        *(f"--enable-{name}" for name in LIBRARIES),
        "--enable-shared",
        "--disable-static",
        "--enable-pic",
        "--disable-network",
        "--enable-pthreads",
        "--enable-decoders",
        f"--enable-demuxer={','.join(DEMUXERS)}",
        *component_args("parser", PARSERS),
        *component_args("bsf", BSFS),
        *component_args("hwaccel", HWACCELS),
        "--arch=aarch64",
        "--target-os=darwin",
        f"--cc={xcrun} clang",
        f"--ar={xcrun} ar",
        f"--nm={xcrun} nm -g",
        f"--ranlib={xcrun} ranlib",
        f"--strip={xcrun} strip",
        f"--sysroot={sdk_path}",
        f"--extra-cflags={target}",
        f"--extra-ldflags={target} -Wl,-headerpad_max_install_names",
    ]


class BuildError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def scoped(slice_: Slice, check: Check) -> Check:
    return dataclasses.replace(check, name=f"{slice_.identifier} {check.name}")


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


def capture(
    command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> str:
    result = subprocess.run(
        command, check=False, cwd=cwd, env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BuildError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


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


def check_release_tag(source: Source) -> Check:
    tags = [
        name
        for name, kind in source.head_tags
        if kind == "tag" and RELEASE_TAG.fullmatch(name)
    ]
    if len(tags) != 1:
        found = (
            ", ".join(f"{name} ({kind})" for name, kind in source.head_tags) or "none"
        )
        return Check(
            "release tag",
            False,
            f"HEAD needs one annotated {UPSTREAM_TAG}-kerao.<n> tag, has: {found}",
        )
    return Check("release tag", True, tags[0])


def check_clean_worktree(source: Source) -> Check:
    shown = "; ".join(source.changes[:MAX_LISTED_LINES])
    more = len(source.changes) - MAX_LISTED_LINES
    return Check(
        "clean worktree",
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


def check_license(configure_output: str) -> Check:
    licenses = [
        line.removeprefix("License: ")
        for line in configure_output.splitlines()
        if line.startswith("License: ")
    ]
    if len(licenses) != 1:
        return Check(
            "license", False, f"expected one License line, found {len(licenses)}"
        )
    return Check("license", licenses[0] == EXPECTED_LICENSE, licenses[0])


def component_lines(configure_output: str) -> list[str]:
    lines = configure_output.splitlines()
    return (
        lines[lines.index(COMPONENTS_HEADER) :] if COMPONENTS_HEADER in lines else lines
    )


def check_configure_output_committed(configure_output: str, committed: Path) -> Check:
    name = "committed configure output"
    if not committed.is_file():
        return Check(name, False, f"{committed} is missing")
    diff = difflib.unified_diff(
        component_lines(committed.read_text()), component_lines(configure_output), n=0
    )
    changed = [
        line
        for line in diff
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    if changed:
        return Check(
            name,
            False,
            f"{committed} differs: {' | '.join(changed[:MAX_LISTED_LINES])}",
        )
    return Check(name, True, str(committed))


def preconditions(source: Source, mode: str) -> list[Check]:
    checks = [check_version_string(source), check_no_version_file(source)]
    if mode == "release":
        checks += [check_release_tag(source), check_clean_worktree(source)]
    return checks


@dataclasses.dataclass(frozen=True)
class Sdk:
    name: str
    version: str
    path: Path


@dataclasses.dataclass(frozen=True)
class Toolchain:
    xcode_version: str
    xcode_build: str
    sdks: dict[str, Sdk]


def read_toolchain() -> Toolchain:
    version = re.fullmatch(
        r"Xcode (\S+)\nBuild version (\S+)",
        capture(["xcrun", "xcodebuild", "-version"]),
    )
    if version is None:
        raise BuildError("cannot read the Xcode version from xcodebuild -version")
    sdks = {
        slice_.identifier: Sdk(
            name=slice_.sdk,
            version=capture(["xcrun", "--sdk", slice_.sdk, "--show-sdk-version"]),
            path=Path(capture(["xcrun", "--sdk", slice_.sdk, "--show-sdk-path"])),
        )
        for slice_ in SLICES
    }
    return Toolchain(xcode_version=version[1], xcode_build=version[2], sdks=sdks)


def build_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key != "revision"}


def run_configure(slice_: Slice, sdk: Sdk, build_dir: Path) -> str:
    command = [str(ROOT / "configure"), *configure_args(slice_, sdk.path)]
    result = subprocess.run(
        command,
        check=False,
        cwd=build_dir,
        env=build_env(),
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        log = build_dir / "ffbuild" / "config.log"
        tail = (
            log.read_text(errors="replace").splitlines()[-CONFIG_LOG_TAIL_LINES:]
            if log.is_file()
            else []
        )
        raise BuildError(
            "\n".join(
                [f"configure failed for {slice_.identifier}:", result.stdout, *tail]
            )
        )
    return result.stdout.replace(str(ROOT), SOURCE_PLACEHOLDER)


def run_make(slice_: Slice, build_dir: Path, stage: Path) -> None:
    jobs = f"-j{os.cpu_count()}"
    command = [
        "xcrun",
        "--sdk",
        slice_.sdk,
        "make",
        jobs,
        "install",
        f"DESTDIR={stage}",
    ]
    result = subprocess.run(
        command, check=False, cwd=build_dir, env=build_env(), stdout=sys.stderr
    )
    if result.returncode != 0:
        raise BuildError(f"make failed for {slice_.identifier}")


def copy_dylibs(lib_dir: Path, output: Path) -> None:
    for name in LIBRARIES:
        found = [
            path
            for path in lib_dir.iterdir()
            if re.fullmatch(rf"lib{name}\.[0-9]+\.dylib", path.name)
        ]
        if len(found) != 1:
            raise BuildError(
                f"expected one lib{name}.<major>.dylib in {lib_dir}, found {len(found)}"
            )
        shutil.copy(found[0], output / found[0].name)


def build_slice(slice_: Slice, sdk: Sdk, work: Path, output: Path) -> list[Check]:
    build_dir = work / "build"
    stage = work / "stage"
    build_dir.mkdir(parents=True)
    configure_output = run_configure(slice_, sdk, build_dir)
    written = output / "configure" / f"{slice_.identifier}.txt"
    written.parent.mkdir(exist_ok=True)
    written.write_text(configure_output)
    checks = [
        check_license(configure_output),
        check_configure_output_committed(
            configure_output, COMMITTED_CONFIGURE / written.name
        ),
    ]
    run_make(slice_, build_dir, stage)
    copy_dylibs(stage / PREFIX.lstrip("/") / "lib", output)
    return [scoped(slice_, check) for check in checks]


def print_summary(
    mode: str,
    source: Source,
    toolchain: Toolchain | None,
    output: Path | None,
    checks: list[Check],
) -> None:
    facts = [
        ("mode", mode),
        ("commit", source.commit),
        ("version", source.version),
        ("dirty", "yes" if source.dirty else "no"),
    ]
    if toolchain is not None:
        facts.append(("xcode", f"{toolchain.xcode_version} ({toolchain.xcode_build})"))
        facts += [
            (f"sdk {key}", f"{sdk.name} {sdk.version}")
            for key, sdk in toolchain.sdks.items()
        ]
    if output is not None:
        facts.append(("output", str(output)))
    width = max(len(label) for label, _ in facts)
    print("\n".join(f"{label:<{width}}  {value}" for label, value in facts))
    print()
    width = max(len(check.name) for check in checks)
    for check in checks:
        print(
            f"{'pass' if check.ok else 'FAIL'}  {check.name:<{width}}  {check.detail}".rstrip()
        )
    failed = sum(not check.ok for check in checks)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")


def build(output: Path, mode: str) -> int:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise BuildError(f"--output {output} must be a new or empty directory")
    source = read_source(ROOT)
    checks = preconditions(source, mode)
    if not all(check.ok for check in checks):
        print_summary(mode, source, None, None, checks)
        print("not built: preconditions failed")
        return 1
    toolchain = read_toolchain()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kerao-ffmpeg-") as work:
        for slice_ in SLICES:
            checks += build_slice(
                slice_,
                toolchain.sdks[slice_.identifier],
                Path(work) / slice_.identifier,
                output,
            )
    print_summary(mode, source, toolchain, output, checks)
    return 0 if all(check.ok for check in checks) else 1


Counterexample = Callable[[Path], tuple[Check, Check]]
COUNTEREXAMPLES: list[Counterexample] = []


def counterexample(case: Counterexample) -> Counterexample:
    COUNTEREXAMPLES.append(case)
    return case


FAKE_CONFIGURE_OUTPUT = f"""\
install prefix            {PREFIX}
source path               {SOURCE_PLACEHOLDER}
C compiler                xcrun --sdk macosx clang
ARCH                      aarch64 (generic)

{COMPONENTS_HEADER}

Libraries:
avcodec                 avutil
avformat                swresample

Enabled decoders:
aac                     h264

Enabled demuxers:
mov

License: {EXPECTED_LICENSE}
"""

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
    (repo / "RELEASE").write_text("9.0.2\n")
    fake_git(repo, "add", "RELEASE")
    fake_git(repo, "commit", "-q", "-m", "upstream")
    fake_git(repo, "tag", "-a", UPSTREAM_TAG, "-m", UPSTREAM_TAG)
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "kerao")
    fake_git(repo, "tag", "-a", f"{UPSTREAM_TAG}-kerao.1", "-m", "release")
    return repo


@counterexample
def license_line_is_not_lgpl21(tmp: Path) -> tuple[Check, Check]:
    gpl = FAKE_CONFIGURE_OUTPUT.replace(EXPECTED_LICENSE, "GPL version 2 or later")
    return check_license(FAKE_CONFIGURE_OUTPUT), check_license(gpl)


@counterexample
def committed_configure_output_is_stale(tmp: Path) -> tuple[Check, Check]:
    committed = tmp / "macos-arm64.txt"
    committed.write_text(FAKE_CONFIGURE_OUTPUT)
    good = check_configure_output_committed(FAKE_CONFIGURE_OUTPUT, committed)
    committed.write_text(
        FAKE_CONFIGURE_OUTPUT.replace("aac                     h264", "h264")
    )
    return good, check_configure_output_committed(FAKE_CONFIGURE_OUTPUT, committed)


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
    (repo / "VERSION").write_text("9.0.2\n")
    fake_git(repo, "add", "VERSION")
    fake_git(repo, "commit", "-q", "-m", "pin the version")
    return good, check_no_version_file(read_source(repo))


@counterexample
def checkout_without_tags(tmp: Path) -> tuple[Check, Check]:
    repo = fake_release_checkout(tmp)
    good = check_version_string(read_source(repo))
    fake_git(repo, "tag", "-d", UPSTREAM_TAG, f"{UPSTREAM_TAG}-kerao.1")
    return good, check_version_string(read_source(repo))


def run_counterexample(case: Counterexample) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="kerao-self-test-") as tmp:
        try:
            good, bad = case(Path(tmp))
        except BuildError as error:
            return False, f"error: {error}"
    if not good.ok:
        return False, f"baseline fails {good.name}: {good.detail}"
    if bad.ok:
        return False, f"not caught by {bad.name}"
    return True, f"{bad.name}: {bad.detail}"


def self_test() -> int:
    width = max(len(case.__name__) for case in COUNTEREXAMPLES)
    caught = 0
    for case in COUNTEREXAMPLES:
        ok, detail = run_counterexample(case)
        caught += ok
        print(f"{'pass' if ok else 'FAIL'}  {case.__name__:<{width}}  {detail}")
    print(f"\n{caught} of {len(COUNTEREXAMPLES)} counterexamples caught")
    return 0 if caught == len(COUNTEREXAMPLES) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the kerao FFmpeg libraries for Apple platforms."
    )
    parser.add_argument(
        "--output", type=Path, help="new or empty directory for the build products"
    )
    parser.add_argument("--mode", choices=("release", "dev"))
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run every check against its counterexample",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.output is None or args.mode is None:
        parser.error("--output and --mode are required unless --self-test is given")
    try:
        return build(args.output.resolve(), args.mode)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
