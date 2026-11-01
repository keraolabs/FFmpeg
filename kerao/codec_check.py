import dataclasses
import json
from pathlib import Path

from checkout import UPSTREAM_TAG
from common import ROOT, SLICES, BuildError, Check, Slice, counterexample, scoped
from runners import Runner, compile_program
from toolchain import Toolchain

MANIFEST = ROOT / "kerao" / "codecs.json"
PROTOCOL = "kerao-codec-check"
CODECS_CHECK = "codecs"
VERSION_CHECK = "av_version_info"
PROGRAM_CHECKS = (CODECS_CHECK, VERSION_CHECK)
NOT_RUN = "not run: this slice has no runner"


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


def parse_output(stdout: str) -> ProgramOutput:
    """Read the lines the check program prefixes with PROTOCOL and ignore the rest."""
    versions: list[str] = []
    codecs: list[str] = []
    ends: list[str] = []
    for line in stdout.splitlines():
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
        raise BuildError(
            f"the codec check program printed {len(versions)} versions, "
            f"{len(codecs)} decoders and end {', '.join(ends) or 'never'}"
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
    listed: frozenset[str], output: ProgramOutput | None, release_tag: str | None
) -> list[Check]:
    """output is None when the slice has no runner here."""
    if output is None:
        return [Check(name, False, NOT_RUN) for name in PROGRAM_CHECKS]
    return [check_codecs(listed, output), check_version(output.version, release_tag)]


def codec_checks(
    listed: frozenset[str],
    slice_runners: dict[Slice, Runner],
    toolchain: Toolchain,
    output: Path,
    work: Path,
    release_tag: str | None,
) -> tuple[list[Check], list[str]]:
    """Run the check program on every slice; return its checks and the unverified check names.

    A slice missing from slice_runners fails a release build (release_tag set) and is
    unverified in a dev build (release_tag None).
    """
    checks: list[Check] = []
    unverified: list[str] = []
    for slice_ in SLICES:
        run = slice_runners.get(slice_)
        if run is None and release_tag is None:
            unverified += [f"{slice_.identifier} {name}" for name in PROGRAM_CHECKS]
            continue
        program_output = None
        if run is not None:
            binary = compile_program(
                slice_,
                toolchain.sdks[slice_.identifier].path,
                output,
                work / slice_.identifier / "codec_check",
            )
            try:
                program_output = parse_output(run(binary))
            except BuildError as error:
                raise BuildError(f"{slice_.identifier}: {error}") from error
        checks += [
            scoped(slice_.identifier, check)
            for check in program_checks(listed, program_output, release_tag)
        ]
    return checks, unverified


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
    output = parse_output(fake_program_output(listed, FAKE_VERSION))
    return (
        program_checks(listed, output, FAKE_VERSION)[0],
        program_checks(listed, None, FAKE_VERSION)[0],
    )


@counterexample
def dev_program_reports_n9_0_1(tmp: Path) -> tuple[Check, Check]:
    return (
        check_version(reported_version(FAKE_DEV_VERSION), None),
        check_version(reported_version("n9.0.1-6-g1976b53c6c"), None),
    )
