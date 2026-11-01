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
import re
import shutil
import tempfile
from pathlib import Path

import checkout
import ffmpeg
from common import (
    COUNTEREXAMPLES,
    LIBRARIES,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Counterexample,
    Slice,
    scoped,
)
from toolchain import Sdk, Toolchain, read_toolchain


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
    build_dir.mkdir(parents=True)
    configure_output = ffmpeg.run_configure(
        slice_, ffmpeg.configure_args(slice_, sdk.path), build_dir
    )
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
    copy_dylibs(prefix / "lib", output)
    return [scoped(slice_.identifier, check) for check in checks]


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
