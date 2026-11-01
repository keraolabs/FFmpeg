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

sys.dont_write_bytecode = True

import argparse
import dataclasses
import shutil
import tempfile
from pathlib import Path

import artifact
import checkout
import ffmpeg
import framework
import xcframework
from common import (
    COUNTEREXAMPLES,
    FRAMEWORKS,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Counterexample,
    Slice,
    scoped,
)
from toolchain import Toolchain, read_toolchain

NOTICES = ("LICENSE.md", "COPYING.LGPLv2.1")


@dataclasses.dataclass(frozen=True)
class SliceBuild:
    checks: list[Check]
    configure: dict[str, object]
    config_components: Path
    prefix: Path
    frameworks: Path


def build_slice(
    slice_: Slice, toolchain: Toolchain, bundle_version: str, work: Path, output: Path
) -> SliceBuild:
    build_dir = work / "build"
    build_dir.mkdir(parents=True)
    args = ffmpeg.configure_args(slice_, toolchain.sdks[slice_.identifier].path)
    configure_output = ffmpeg.run_configure(slice_, args, build_dir)
    written = output / "configure" / f"{slice_.identifier}.txt"
    written.parent.mkdir(exist_ok=True)
    written.write_text(configure_output)
    checks = [
        ffmpeg.check_license(configure_output),
        ffmpeg.check_configure_output_committed(
            configure_output, ffmpeg.COMMITTED_CONFIGURE / written.name
        ),
    ]
    prefix = ffmpeg.run_make(slice_, build_dir, work / "stage")
    frameworks = work / "frameworks"
    framework.package_slice(slice_, toolchain, bundle_version, prefix, frameworks)
    return SliceBuild(
        checks=[scoped(slice_.identifier, check) for check in checks],
        configure={
            "args": args,
            "license": "; ".join(ffmpeg.license_lines(configure_output)),
        },
        config_components=build_dir / "config_components.h",
        prefix=prefix,
        frameworks=frameworks,
    )


def copy_notices(notices: Path) -> None:
    notices.mkdir(parents=True)
    for name in NOTICES:
        shutil.copy(ROOT / name, notices / name)


def print_summary(
    mode: str,
    source: checkout.Source,
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
    source = checkout.read_source(ROOT)
    checks = checkout.preconditions(source, mode)
    if not all(check.ok for check in checks):
        print_summary(mode, source, None, None, checks)
        print("not built: preconditions failed")
        return 1
    toolchain = read_toolchain()
    output.mkdir(parents=True, exist_ok=True)
    bundle_version = checkout.bundle_version(source)
    with tempfile.TemporaryDirectory(prefix="kerao-ffmpeg-") as work:
        builds = {
            slice_: build_slice(
                slice_,
                toolchain,
                bundle_version,
                Path(work) / slice_.identifier,
                output,
            )
            for slice_ in SLICES
        }
        for slice_build in builds.values():
            checks += slice_build.checks
        checks.append(
            ffmpeg.check_configured_decoders(
                {
                    slice_.identifier: built.config_components
                    for slice_, built in builds.items()
                }
            )
        )
        shutil.copytree(builds[SLICES[0]].prefix / "include", output / "include")
        xcframework.make_xcframeworks(
            {slice_: slice_build.frameworks for slice_, slice_build in builds.items()},
            output,
        )
    for slice_ in SLICES:
        for name in FRAMEWORKS:
            checks += framework.framework_checks(output, slice_, name)
    for name in FRAMEWORKS:
        checks.append(
            xcframework.check_library_identifiers(output / f"{name}.xcframework")
        )
        checks.append(xcframework.check_public_headers(output, name))
    copy_notices(output / "notices" / "ffmpeg")
    record = artifact.artifact_record(
        mode,
        source,
        toolchain,
        {slice_.identifier: built.configure for slice_, built in builds.items()},
        artifact.framework_records(output, SLICES),
    )
    artifact_path = output / "artifact.json"
    artifact.write_artifact(artifact_path, record)
    checks.append(artifact.check_artifact_fields(artifact_path))
    checks.append(artifact.check_artifact_slices(artifact_path))
    print_summary(mode, source, toolchain, output, checks)
    return 0 if all(check.ok for check in checks) else 1


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
