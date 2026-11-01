#!/usr/bin/env python3
"""Build the kerao FFmpeg libraries for Apple platforms.

python3 kerao/build.py --output DIR --mode release|dev
    [--device UDID --codesign-identity SHA-1 --provisioning-profile PATH]
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
import types
from pathlib import Path

import artifact
import checkout
import codec_check
import deps
import device
import ffmpeg
import framework
import privacy
import runners
import xcframework
from common import (
    COUNTEREXAMPLES,
    FRAMEWORKS,
    IOS,
    IOS_SIMULATOR,
    MACOS,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Counterexample,
    Slice,
    scoped,
)
from deps import DEPS, Dep
from toolchain import Toolchain, read_toolchain

NOTICES = ("LICENSE.md", "COPYING.LGPLv2.1")
KERAO = ROOT / "kerao"
CHECK_PREFIX = "check_"


@dataclasses.dataclass(frozen=True)
class SliceBuild:
    checks: list[Check]
    configure: dict[str, object]
    config_components: Path
    prefix: Path
    frameworks: Path


def build_slice(
    slice_: Slice,
    toolchain: Toolchain,
    bundle_version: str,
    checkouts: dict[Dep, Path],
    records: privacy.Records,
    work: Path,
    output: Path,
) -> SliceBuild:
    sdk_path = toolchain.sdks[slice_.identifier].path
    pkgconfig, checks = deps.build_deps(slice_, sdk_path, checkouts, work / "deps")
    build_dir = work / "build"
    build_dir.mkdir(parents=True)
    args = ffmpeg.configure_args(slice_, sdk_path)
    configure_output = ffmpeg.run_configure(slice_, args, build_dir, pkgconfig)
    written = output / "configure" / f"{slice_.identifier}.txt"
    written.parent.mkdir(exist_ok=True)
    written.write_text(configure_output)
    checks += [
        ffmpeg.check_license(configure_output),
        ffmpeg.check_external_libraries(configure_output),
        ffmpeg.check_configure_output_committed(
            configure_output, ffmpeg.COMMITTED_CONFIGURE / written.name
        ),
    ]
    prefix = ffmpeg.run_make(slice_, build_dir, work / "stage")
    linked = framework.find_dylib(build_dir / "libavcodec", "libavcodec")
    checks += deps.linked_checks(linked)
    frameworks = work / "frameworks"
    framework.package_slice(
        slice_, toolchain, bundle_version, prefix, records, frameworks
    )
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


def copy_notices(checkouts: dict[Dep, Path], notices: Path) -> None:
    (notices / "ffmpeg").mkdir(parents=True)
    for name in NOTICES:
        shutil.copy(ROOT / name, notices / "ffmpeg" / name)
    deps.copy_notices(checkouts, notices)


def print_summary(
    mode: str,
    source: checkout.Source,
    toolchain: Toolchain | None,
    output: Path | None,
    checks: list[Check],
    unverified: tuple[str, ...] = (),
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
        facts.append(
            (
                "tools",
                ", ".join(
                    f"{name} {version}" for name, version in toolchain.tools.items()
                ),
            )
        )
    facts += [(dep.name, f"{dep.tag} {dep.commit}") for dep in DEPS]
    if output is not None:
        facts.append(("output", str(output)))
    if unverified:
        facts.append(("unverified", ", ".join(unverified)))
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


def build(output: Path, mode: str, target: device.Target | None) -> int:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise BuildError(f"--output {output} must be a new or empty directory")
    records = privacy.read_records()
    source = checkout.read_source(ROOT)
    listed = codec_check.load_manifest(codec_check.MANIFEST)
    simulators = runners.read_booted_simulators()
    checks = [
        *checkout.preconditions(source, mode),
        runners.check_booted_simulator(simulators),
        *device.preconditions(target, mode),
    ]
    if not all(check.ok for check in checks):
        print_summary(mode, source, None, None, checks)
        print("not built: preconditions failed")
        return 1
    toolchain = read_toolchain()
    bundle_version = checkout.bundle_version(source)
    with tempfile.TemporaryDirectory(prefix="kerao-ffmpeg-") as tmp:
        work = Path(tmp)
        checkouts = {dep: deps.fetch(dep, work / "src" / dep.name) for dep in DEPS}
        checks += [deps.check_commit(dep, path) for dep, path in checkouts.items()]
        if not all(check.ok for check in checks):
            print_summary(mode, source, toolchain, None, checks)
            print("not built: a dependency is not at its pinned commit")
            return 1
        output.mkdir(parents=True, exist_ok=True)
        builds = {
            slice_: build_slice(
                slice_,
                toolchain,
                bundle_version,
                checkouts,
                records,
                work / slice_.identifier,
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
        copy_notices(checkouts, output / "notices")
    for slice_ in SLICES:
        for name in FRAMEWORKS:
            checks += framework.framework_checks(output, slice_, name, records)
    for name in FRAMEWORKS:
        checks.append(
            xcframework.check_library_identifiers(output / f"{name}.xcframework")
        )
        checks.append(xcframework.check_public_headers(output, name))
    slice_runners = {
        MACOS: runners.run_on_mac,
        IOS_SIMULATOR: runners.simulator_runner(simulators[0]),
        **({IOS: device.device_runner(target, output)} if target else {}),
    }
    with tempfile.TemporaryDirectory(prefix="kerao-codec-check-") as tmp:
        program_checks, unverified = codec_check.codec_checks(
            listed,
            slice_runners,
            codec_check.program_compiler(toolchain, output, Path(tmp)),
            checkout.release_tag(source) if mode == "release" else None,
        )
    checks += program_checks
    record = artifact.artifact_record(
        mode,
        source,
        toolchain,
        {slice_.identifier: built.configure for slice_, built in builds.items()},
        artifact.framework_records(output, SLICES),
        unverified,
    )
    artifact_path = output / "artifact.json"
    artifact.write_artifact(artifact_path, record)
    checks.append(artifact.check_artifact_fields(artifact_path))
    checks.append(artifact.check_artifact_slices(artifact_path))
    checks.append(artifact.check_artifact_deps(artifact_path))
    print_summary(mode, source, toolchain, output, checks, tuple(unverified))
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


def defined_checks() -> list[types.FunctionType]:
    """Every function named check_* that a loaded module of kerao/ defines."""
    return [
        value
        for module in list(sys.modules.values())
        if getattr(module, "__file__", None)
        and Path(module.__file__).resolve().parent == KERAO
        for name, value in vars(module).items()
        if name.startswith(CHECK_PREFIX)
        and isinstance(value, types.FunctionType)
        and value.__module__ == module.__name__
    ]


def referenced_names(code: types.CodeType) -> frozenset[str]:
    nested = [const for const in code.co_consts if isinstance(const, types.CodeType)]
    return frozenset(code.co_names).union(*map(referenced_names, nested))


def uncovered_checks() -> tuple[int, list[str]]:
    """The number of check functions, and those no counterexample calls."""
    called = frozenset().union(
        *(referenced_names(case.__code__) for case in COUNTEREXAMPLES)
    )
    checks = defined_checks()
    return len(checks), sorted(
        f"{check.__module__}.{check.__name__}"
        for check in checks
        if check.__name__ not in called
    )


def self_test() -> int:
    width = max(len(case.__name__) for case in COUNTEREXAMPLES)
    caught = 0
    for case in COUNTEREXAMPLES:
        ok, detail = run_counterexample(case)
        caught += ok
        print(f"{'pass' if ok else 'FAIL'}  {case.__name__:<{width}}  {detail}")
    print(f"\n{caught} of {len(COUNTEREXAMPLES)} counterexamples caught")
    total, uncovered = uncovered_checks()
    for name in uncovered:
        print(f"FAIL  {name}  no counterexample calls it")
    print(f"{total - len(uncovered)} of {total} checks have a counterexample")
    return 0 if caught == len(COUNTEREXAMPLES) and not uncovered else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the kerao FFmpeg libraries for Apple platforms."
    )
    parser.add_argument(
        "--output", type=Path, help="new or empty directory for the build products"
    )
    parser.add_argument("--mode", choices=("release", "dev"))
    parser.add_argument(
        "--device",
        metavar="UDID",
        help="iPhone that runs the ios-arm64 codec check; release builds need one",
    )
    parser.add_argument(
        "--codesign-identity",
        metavar="SHA-1",
        help="identity that signs the runner app, as security find-identity -v -p codesigning prints it",
    )
    parser.add_argument(
        "--provisioning-profile",
        type=Path,
        metavar="PATH",
        help="development profile that provisions --device and holds the identity's certificate",
    )
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
    signing_args = (args.codesign_identity, args.provisioning_profile)
    if args.device is not None and None in signing_args:
        parser.error("--device needs --codesign-identity and --provisioning-profile")
    if args.device is None and signing_args != (None, None):
        parser.error("--codesign-identity and --provisioning-profile need --device")
    try:
        target = (
            device.read_target(
                args.device, args.codesign_identity, args.provisioning_profile.resolve()
            )
            if args.device is not None
            else None
        )
        return build(args.output.resolve(), args.mode, target)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
