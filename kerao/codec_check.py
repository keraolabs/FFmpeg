import dataclasses
import json
import shutil
from collections.abc import Callable
from pathlib import Path

from checkout import UPSTREAM_TAG
from common import (
    FRAMEWORKS,
    IOS,
    IOS_SIMULATOR,
    MACOS,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Slice,
    capture,
    counterexample,
    scoped,
)
from framework import delivered_framework
from runners import Runner, compile_program, run_on_mac
from toolchain import Toolchain

MANIFEST = ROOT / "kerao" / "codecs.json"
CHECK_PROGRAM = ROOT / "kerao" / "codec_check.c"
PROTOCOL = "kerao-codec-check"
CODECS_CHECK = "codecs"
VERSION_CHECK = "av_version_info"
PROGRAM_CHECKS = (CODECS_CHECK, VERSION_CHECK)
NOT_RUN = "not run: this slice has no runner"
NO_RESULT = "no complete result"


@dataclasses.dataclass(frozen=True)
class ProgramOutput:
    version: str
    decoders: int
    codecs: frozenset[str]


def load_manifest(path: Path) -> frozenset[str]:
    """The codec names path lists under "codecs", across every media type."""
    try:
        listed = json.loads(path.read_text())["codecs"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BuildError(f"cannot read the codec list in {path}: {error}") from error
    if not isinstance(listed, dict) or not all(
        isinstance(kind, list) for kind in listed.values()
    ):
        raise BuildError(f'{path}: "codecs" must map each media type to a list')
    names = [name for kind in listed.values() for name in kind]
    if not names or not all(isinstance(name, str) and name for name in names):
        raise BuildError(f"{path} lists no codecs or a codec that is not a name")
    if len(set(names)) != len(names):
        raise BuildError(f"{path} lists a codec more than once")
    return frozenset(names)


class NoResult(Exception):
    """The console output holds no complete result of the check program."""


def parse_output(console: str) -> ProgramOutput:
    """Read the lines the check program prefixes with PROTOCOL and ignore the rest.

    Raises NoResult unless they hold one version line and an end line that counts
    the decoder lines before it.
    """
    versions: list[str] = []
    codecs: list[str] = []
    ends: list[str] = []
    for line in console.splitlines():
        prefix, _, rest = line.partition(" ")
        if prefix != PROTOCOL:
            continue
        kind, _, value = rest.partition(" ")
        if kind == "version":
            versions.append(value)
        elif kind == "decoder":
            codecs.append(value.split(" ")[-1])
        elif kind == "end":
            ends.append(value)
    if len(versions) != 1 or ends != [str(len(codecs))]:
        raise NoResult(
            f"printed {len(versions)} versions, {len(codecs)} decoders "
            f"and end {', '.join(ends) or 'never'}"
        )
    return ProgramOutput(
        version=versions[0], decoders=len(codecs), codecs=frozenset(codecs)
    )


def check_codecs(listed: frozenset[str], output: ProgramOutput) -> Check:
    """Fail on every listed codec no decoder covers; name the decoded ones not listed."""
    missing = sorted(listed - output.codecs)
    unlisted = sorted(output.codecs - listed)
    found = (
        f"lacks {len(missing)} of {len(listed)} listed: {', '.join(missing)}"
        if missing
        else f"all {len(listed)} listed"
    )
    return Check(
        CODECS_CHECK,
        not missing,
        f"{found}; {len(output.codecs)} codecs from {output.decoders} decoders; "
        f"not listed: {', '.join(unlisted) or 'none'}",
    )


def check_version(version: str, release_tag: str | None) -> Check:
    """A release build must report exactly release_tag; a dev build (None) any n9.0.2 describe."""
    if release_tag is not None:
        expected = release_tag
        ok = version == release_tag
    else:
        expected = f"{UPSTREAM_TAG} or {UPSTREAM_TAG}-…"
        ok = version == UPSTREAM_TAG or version.startswith(f"{UPSTREAM_TAG}-")
    return Check(
        VERSION_CHECK, ok, version if ok else f"{version}, expected {expected}"
    )


def program_checks(
    listed: frozenset[str], console: str | None, release_tag: str | None
) -> list[Check]:
    """console is what the check program printed, or None when the slice has no runner here."""
    if console is None:
        return failed_program_checks(NOT_RUN)
    try:
        output = parse_output(console)
    except NoResult as error:
        return failed_program_checks(f"{NO_RESULT}: {error}")
    return [check_codecs(listed, output), check_version(output.version, release_tag)]


def failed_program_checks(detail: str) -> list[Check]:
    return [Check(name, False, detail) for name in PROGRAM_CHECKS]


Compiler = Callable[[Slice], Path]
"""Build the check program for a slice and return the binary; raises BuildError when it cannot."""


def program_compiler(toolchain: Toolchain, output: Path, work: Path) -> Compiler:
    """Compile CHECK_PROGRAM against each slice's frameworks delivered under output."""

    def compile_slice(slice_: Slice) -> Path:
        return compile_program(
            slice_,
            toolchain.sdks[slice_.identifier].path,
            output,
            CHECK_PROGRAM,
            work / slice_.identifier / "codec_check",
        )

    return compile_slice


def codec_checks(
    listed: frozenset[str],
    slice_runners: dict[Slice, Runner],
    compile_slice: Compiler,
    release_tag: str | None,
) -> tuple[list[Check], list[str]]:
    """Run the check program on every slice; return its checks and the unverified check names.

    A slice missing from slice_runners fails a release build (release_tag set) and is
    unverified in a dev build (release_tag None). A slice whose program fails to
    compile or run fails its checks; the other slices still run.
    """
    checks: list[Check] = []
    unverified: list[str] = []
    for slice_ in SLICES:
        run = slice_runners.get(slice_)
        if run is None and release_tag is None:
            unverified += [f"{slice_.identifier} {name}" for name in PROGRAM_CHECKS]
            continue
        checks += [
            scoped(slice_.identifier, check)
            for check in slice_checks(listed, slice_, run, compile_slice, release_tag)
        ]
    return checks, unverified


def slice_checks(
    listed: frozenset[str],
    slice_: Slice,
    run: Runner | None,
    compile_slice: Compiler,
    release_tag: str | None,
) -> list[Check]:
    if run is None:
        return program_checks(listed, None, release_tag)
    try:
        console = run(compile_slice(slice_))
    except BuildError as error:
        return failed_program_checks(f"{NO_RESULT}: {' '.join(str(error).split())}")
    return program_checks(listed, console, release_tag)


def fake_program_output(codecs: frozenset[str], version: str) -> str:
    lines = [
        "uavs3d version 1.2.89",
        f"{PROTOCOL} version {version}",
        *(f"{PROTOCOL} decoder {name} {name}" for name in sorted(codecs)),
        f"{PROTOCOL} end {len(codecs)}",
    ]
    return "\n".join(lines) + "\n"


FAKE_VERSION = "n9.0.2-kerao.1"
FAKE_DEV_VERSION = "n9.0.2-6-g1976b53c6c"
NO_SUCH_CODEC = "kerao_no_such_codec"


@counterexample
def manifest_lists_a_codec_without_a_decoder(tmp: Path) -> tuple[Check, Check]:
    listed = load_manifest(MANIFEST)
    output = parse_output(fake_program_output(listed, FAKE_VERSION))
    manifest = json.loads(MANIFEST.read_text())
    manifest["codecs"]["video"].append(NO_SUCH_CODEC)
    copy = tmp / MANIFEST.name
    copy.write_text(json.dumps(manifest))
    return check_codecs(listed, output), check_codecs(load_manifest(copy), output)


def reported_version(version: str) -> str:
    return parse_output(fake_program_output(frozenset({"h264"}), version)).version


@counterexample
def release_program_reports_n9_0_1(tmp: Path) -> tuple[Check, Check]:
    return (
        check_version(reported_version(FAKE_VERSION), FAKE_VERSION),
        check_version(reported_version("n9.0.1"), FAKE_VERSION),
    )


@counterexample
def release_slice_without_a_program_run(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    console = fake_program_output(listed, FAKE_VERSION)
    return (
        program_checks(listed, console, FAKE_VERSION)[0],
        program_checks(listed, None, FAKE_VERSION)[0],
    )


@counterexample
def dev_program_reports_n9_0_1(tmp: Path) -> tuple[Check, Check]:
    return (
        check_version(reported_version(FAKE_DEV_VERSION), None),
        check_version(reported_version("n9.0.1-6-g1976b53c6c"), None),
    )


def fake_device_console(program_lines: list[str]) -> str:
    """program_lines framed the way devicectl --console prints them."""
    lines = [
        "Launched application with org.keraolabs.codec-check bundle identifier.",
        "Waiting for the application to terminate…",
        *program_lines,
        "The app terminated with the exit code 0.",
    ]
    return "\n".join(lines) + "\n"


@counterexample
def device_console_without_a_result_line(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    program_lines = fake_program_output(listed, FAKE_VERSION).splitlines()
    complete = fake_device_console(program_lines)
    without_end = fake_device_console(program_lines[:-1])
    return (
        program_checks(listed, complete, FAKE_VERSION)[0],
        program_checks(listed, without_end, FAKE_VERSION)[0],
    )


def fake_compile(tmp: Path) -> Compiler:
    return lambda slice_: tmp / slice_.identifier


def fake_runner(console: str) -> Runner:
    return lambda binary: console


def launch_fails(binary: Path) -> str:
    raise BuildError(f"devicectl could not launch {binary.name}")


def by_name(checks: list[Check], name: str) -> Check:
    """The check called name, or a failing one when checks hold none."""
    return next(
        (check for check in checks if check.name == name),
        Check(name, False, "not among the checks"),
    )


@counterexample
def device_launch_fails_on_first_slice(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    runs = fake_runner(fake_program_output(listed, FAKE_VERSION))
    slice_runners = {slice_: runs for slice_ in SLICES} | {IOS: launch_fails}
    checks, _ = codec_checks(listed, slice_runners, fake_compile(tmp), FAKE_VERSION)
    return (
        by_name(checks, f"{MACOS.identifier} {VERSION_CHECK}"),
        by_name(checks, f"{IOS.identifier} {CODECS_CHECK}"),
    )


@counterexample
def dev_build_without_a_device(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    runs = fake_runner(fake_program_output(listed, FAKE_DEV_VERSION))

    def unverified(slices: tuple[Slice, ...]) -> Check:
        slice_runners = {slice_: runs for slice_ in slices}
        _, names = codec_checks(listed, slice_runners, fake_compile(tmp), None)
        return Check("unverified", not names, ", ".join(names) or "none")

    return unverified(SLICES), unverified((IOS_SIMULATOR, MACOS))


FAKE_PROGRAM = """\
#include <stdio.h>
int main(void) {{ return fputs({console}, stdout) < 0; }}
"""


def fake_program(path: Path, console: str) -> Path:
    """C source of a program that prints console."""
    path.write_text(FAKE_PROGRAM.format(console=json.dumps(console)))
    return path


def fake_delivered_frameworks(output: Path, slice_: Slice, work: Path) -> None:
    """An empty framework of every library, delivered for slice_ under output."""
    source = work / "empty.c"
    source.write_text("")
    for name in FRAMEWORKS:
        framework = delivered_framework(output, slice_, name)
        framework.mkdir(parents=True)
        capture(
            [
                *("xcrun", "--sdk", slice_.sdk, "clang", "-dynamiclib"),
                *("-target", slice_.target),
                *("-install_name", f"@rpath/{name}.framework/{name}"),
                *("-o", str(framework / name), str(source)),
            ]
        )


@counterexample
def output_path_with_a_comma(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    program = fake_program(
        tmp / "program.c", fake_program_output(listed, FAKE_DEV_VERSION)
    )
    sdk_path = Path(capture(["xcrun", "--sdk", MACOS.sdk, "--show-sdk-path"]))
    good = tmp / "good,output"
    fake_delivered_frameworks(good, MACOS, tmp)
    bad = tmp / "bad,output"
    shutil.copytree(good, bad)
    shutil.rmtree(delivered_framework(bad, MACOS, FRAMEWORKS[-1]))

    def codecs(output: Path) -> Check:
        def compile_slice(slice_: Slice) -> Path:
            binary = tmp / "programs" / output.name / "codec_check"
            return compile_program(slice_, sdk_path, output, program, binary)

        checks, _ = codec_checks(listed, {MACOS: run_on_mac}, compile_slice, None)
        return by_name(checks, f"{MACOS.identifier} {CODECS_CHECK}")

    return codecs(good), codecs(bad)
