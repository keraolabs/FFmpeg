import plistlib
import shutil
from pathlib import Path

from common import (
    FRAMEWORKS,
    IOS,
    IOS_SIMULATOR,
    MAX_LISTED_LINES,
    SLICES,
    VERSIONED,
    BuildError,
    Check,
    Slice,
    capture,
    counterexample,
)
from framework import (
    delivered_framework,
    fake_frameworks,
    framework_binary,
    framework_checks,
    framework_headers,
)


def make_xcframework(
    name: str, frameworks_dirs: dict[Slice, Path], output: Path
) -> Path:
    xcframework = output / f"{name}.xcframework"
    command = ["xcrun", "xcodebuild", "-create-xcframework"]
    for frameworks_dir in frameworks_dirs.values():
        command += ["-framework", str(frameworks_dir / f"{name}.framework")]
    capture([*command, "-output", str(xcframework)])
    for slice_ in frameworks_dirs:
        if not delivered_framework(output, slice_, name).is_dir():
            found = sorted(path.name for path in xcframework.iterdir())
            raise BuildError(
                f"{xcframework} has no {slice_.identifier} slice, has: {', '.join(found)}"
            )
    return xcframework


def make_xcframeworks(frameworks_dirs: dict[Slice, Path], output: Path) -> None:
    for name in FRAMEWORKS:
        make_xcframework(name, frameworks_dirs, output)


def check_library_identifiers(xcframework: Path) -> Check:
    with (xcframework / "Info.plist").open("rb") as file:
        plist = plistlib.load(file)
    found = sorted(
        library["LibraryIdentifier"] for library in plist["AvailableLibraries"]
    )
    return Check(
        f"{xcframework.name} library identifiers",
        found == sorted(slice_.identifier for slice_ in SLICES),
        ", ".join(found) or "none",
    )


def header_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def check_public_headers(output: Path, name: str) -> Check:
    """Compare the Headers of every slice of name and include/<name> byte for byte."""
    trees = {
        slice_.identifier: header_files(
            framework_headers(delivered_framework(output, slice_, name), slice_.layout)
        )
        for slice_ in SLICES
    }
    trees["include"] = header_files(output / "include" / name)
    (reference_label, reference), *others = trees.items()
    problems = [f"{label} has no headers" for label, tree in trees.items() if not tree]
    problems += [
        f"{path} differs between {reference_label} and {label}"
        for label, tree in others
        for path in sorted(reference.keys() | tree.keys())
        if tree.get(path) != reference.get(path)
    ]
    return Check(
        f"{name} public headers",
        not problems,
        "; ".join(problems[:MAX_LISTED_LINES])
        or f"{len(reference)} identical in {', '.join(trees)}",
    )


def fake_output(tmp: Path) -> Path:
    """An output holding a libavutil.xcframework with every slice and its include/ tree."""
    output = tmp / "output"
    output.mkdir()
    frameworks_dirs = {}
    for slice_ in SLICES:
        frameworks = fake_frameworks(tmp / slice_.identifier, slice_)
        frameworks_dirs[slice_] = frameworks["libavutil"].parent
    make_xcframework("libavutil", frameworks_dirs, output)
    shutil.copytree(
        tmp / SLICES[0].identifier / "prefix" / "include" / "libavutil",
        output / "include" / "libavutil",
    )
    return output


def copy_output(output: Path, directory: Path) -> Path:
    copy = directory / output.name
    shutil.copytree(output, copy, symlinks=True)
    return copy


def named(checks: list[Check], name: str) -> Check:
    return next(check for check in checks if check.name.endswith(f" {name}"))


@counterexample
def ios_slice_with_macos_rpath(tmp: Path) -> tuple[Check, Check]:
    output = fake_output(tmp)
    good = named(framework_checks(output, IOS, "libavutil"), "rpath")
    bad = copy_output(output, tmp / "bad")
    binary = framework_binary(delivered_framework(bad, IOS, "libavutil"), IOS.layout)
    capture(["xcrun", "install_name_tool", "-add_rpath", VERSIONED.rpath, str(binary)])
    return good, named(framework_checks(bad, IOS, "libavutil"), "rpath")


@counterexample
def public_header_differs_in_one_slice(tmp: Path) -> tuple[Check, Check]:
    output = fake_output(tmp)
    good = check_public_headers(output, "libavutil")
    bad = copy_output(output, tmp / "bad")
    framework = delivered_framework(bad, IOS_SIMULATOR, "libavutil")
    header = framework_headers(framework, IOS_SIMULATOR.layout) / "libavutil.h"
    content = header.read_bytes()
    header.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    return good, check_public_headers(bad, "libavutil")


@counterexample
def xcframework_without_a_slice(tmp: Path) -> tuple[Check, Check]:
    xcframework = fake_output(tmp) / "libavutil.xcframework"
    good = check_library_identifiers(xcframework)
    bad = copy_output(xcframework.parent, tmp / "bad") / xcframework.name
    shutil.rmtree(bad / IOS_SIMULATOR.identifier)
    with (bad / "Info.plist").open("rb") as file:
        plist = plistlib.load(file)
    plist["AvailableLibraries"] = [
        library
        for library in plist["AvailableLibraries"]
        if library["LibraryIdentifier"] != IOS_SIMULATOR.identifier
    ]
    with (bad / "Info.plist").open("wb") as file:
        plistlib.dump(plist, file)
    return good, check_library_identifiers(bad)
