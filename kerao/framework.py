import plistlib
import re
import shutil
from pathlib import Path

from checkout import UPSTREAM_VERSION
from common import (
    ARCHS,
    FRAMEWORKS,
    SLICES,
    BuildError,
    Check,
    Slice,
    capture,
    counterexample,
    scoped,
)
from macho import (
    check_architectures,
    check_build_version,
    check_dependencies,
    check_install_id,
    check_rpath,
    read_macho,
)
from toolchain import FAKE_TOOLCHAIN, Toolchain

VERSION_DIR = Path("Versions") / "A"
RPATH = "@loader_path/../../.."
BUNDLE_ID_PREFIX = "org.keraolabs."
DT_COMPILER = "com.apple.compilers.llvm.clang.1_0"
CONFIGURE_INSTALL_NAME = re.compile(r"@rpath/(lib\w+)\.[0-9]+\.dylib")
INFO_PLIST_KEYS = (
    "BuildMachineOSBuild",
    "CFBundleDevelopmentRegion",
    "CFBundleExecutable",
    "CFBundleIdentifier",
    "CFBundleInfoDictionaryVersion",
    "CFBundleName",
    "CFBundlePackageType",
    "CFBundleShortVersionString",
    "CFBundleSupportedPlatforms",
    "CFBundleVersion",
    "DTCompiler",
    "DTPlatformBuild",
    "DTPlatformName",
    "DTPlatformVersion",
    "DTSDKBuild",
    "DTSDKName",
    "DTXcode",
    "DTXcodeBuild",
)


def install_id(name: str) -> str:
    return f"@rpath/{name}.framework/{VERSION_DIR}/{name}"


BUNDLED = frozenset(install_id(name) for name in FRAMEWORKS)


def framework_binary(framework: Path) -> Path:
    return framework / VERSION_DIR / framework.stem


def delivered_framework(output: Path, slice_: Slice, name: str) -> Path:
    return output / f"{name}.xcframework" / slice_.identifier / f"{name}.framework"


def framework_plist(framework: Path) -> Path:
    return framework / VERSION_DIR / "Resources" / "Info.plist"


def xcode_number(version: str) -> str:
    major, minor, patch = (version.split(".") + ["0", "0"])[:3]
    return f"{int(major):02d}{minor}{patch}"


def info_plist(
    slice_: Slice, name: str, toolchain: Toolchain, bundle_version: str
) -> dict[str, object]:
    sdk = toolchain.sdks[slice_.identifier]
    return {
        "BuildMachineOSBuild": toolchain.machine_build,
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": name,
        "CFBundleIdentifier": BUNDLE_ID_PREFIX + name,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": name,
        "CFBundlePackageType": "FMWK",
        "CFBundleShortVersionString": UPSTREAM_VERSION,
        "CFBundleSupportedPlatforms": [slice_.bundle_platform],
        "CFBundleVersion": bundle_version,
        "DTCompiler": DT_COMPILER,
        "DTPlatformBuild": sdk.build,
        "DTPlatformName": sdk.name,
        "DTPlatformVersion": sdk.platform_version,
        "DTSDKBuild": sdk.build,
        "DTSDKName": f"{sdk.name}{sdk.version}",
        "DTXcode": xcode_number(toolchain.xcode_version),
        "DTXcodeBuild": toolchain.xcode_build,
        slice_.minimum_version_key: slice_.floor,
    }


def rewrite_install_names(binary: Path, name: str) -> None:
    changes: list[str] = []
    for dependency in read_macho(binary).dylibs:
        match = CONFIGURE_INSTALL_NAME.fullmatch(dependency)
        if match and match[1] in FRAMEWORKS:
            changes += ["-change", dependency, install_id(match[1])]
    capture(
        [
            "xcrun",
            "install_name_tool",
            "-id",
            install_id(name),
            *changes,
            "-add_rpath",
            RPATH,
            str(binary),
        ]
    )


def make_framework(
    name: str,
    dylib: Path,
    headers: Path,
    plist: dict[str, object],
    frameworks_dir: Path,
) -> Path:
    framework = frameworks_dir / f"{name}.framework"
    contents = framework / VERSION_DIR
    (contents / "Resources").mkdir(parents=True)
    shutil.copy(dylib, contents / name)
    shutil.copytree(headers, contents / "Headers")
    with framework_plist(framework).open("wb") as file:
        plistlib.dump(plist, file)
    (framework / "Versions" / "Current").symlink_to(VERSION_DIR.name)
    for entry in (name, "Headers", "Resources"):
        (framework / entry).symlink_to(Path("Versions") / "Current" / entry)
    rewrite_install_names(contents / name, name)
    return framework


def find_dylib(lib_dir: Path, name: str) -> Path:
    found = [
        path
        for path in lib_dir.iterdir()
        if re.fullmatch(rf"{name}\.[0-9]+\.dylib", path.name)
    ]
    if len(found) != 1:
        raise BuildError(
            f"expected one {name}.<major>.dylib in {lib_dir}, found {len(found)}"
        )
    return found[0]


def package_slice(
    slice_: Slice,
    toolchain: Toolchain,
    bundle_version: str,
    prefix: Path,
    frameworks_dir: Path,
) -> None:
    """Turn the installed dylibs and headers under prefix into one framework per library."""
    frameworks_dir.mkdir(parents=True)
    for name in FRAMEWORKS:
        make_framework(
            name,
            find_dylib(prefix / "lib", name),
            prefix / "include" / name,
            info_plist(slice_, name, toolchain, bundle_version),
            frameworks_dir,
        )


def check_info_plist(framework: Path, slice_: Slice) -> Check:
    name = framework.stem
    with framework_plist(framework).open("rb") as file:
        plist = plistlib.load(file)
    required = {
        **dict.fromkeys(INFO_PLIST_KEYS),
        "CFBundleExecutable": name,
        "CFBundleIdentifier": BUNDLE_ID_PREFIX + name,
        "CFBundleName": name,
        "CFBundlePackageType": "FMWK",
        "CFBundleShortVersionString": UPSTREAM_VERSION,
        "CFBundleSupportedPlatforms": [slice_.bundle_platform],
        slice_.minimum_version_key: slice_.floor,
    }
    problems = [
        f"no {key}" if key not in plist else f"{key} is {plist[key]!r}"
        for key, value in required.items()
        if key not in plist or (value is not None and plist[key] != value)
    ]
    return Check(
        "Info.plist",
        not problems,
        "; ".join(problems) or f"{slice_.minimum_version_key} {slice_.floor}",
    )


def make_xcframeworks(frameworks_dirs: dict[Slice, Path], output: Path) -> None:
    for name in FRAMEWORKS:
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


def framework_checks(output: Path, slice_: Slice, name: str) -> list[Check]:
    framework = delivered_framework(output, slice_, name)
    macho = read_macho(framework_binary(framework))
    checks = [
        check_build_version(macho, slice_.platform, slice_.floor),
        check_architectures(macho, ARCHS),
        check_install_id(macho, install_id(name)),
        check_rpath(macho, RPATH),
        check_dependencies(macho, BUNDLED),
        check_info_plist(framework, slice_),
    ]
    return [scoped(f"{slice_.identifier} {name}", check) for check in checks]


FAKE_MAJOR = 1
FAKE_SLICE = SLICES[0]


def fake_frameworks(
    tmp: Path, cflags: tuple[str, ...] = ("-target", FAKE_SLICE.target)
) -> dict[str, Path]:
    """Package a libavutil and a libavcodec that links it, compiled the way configure links them."""
    prefix = tmp / "prefix"
    (prefix / "lib").mkdir(parents=True)
    dylibs: list[Path] = []
    frameworks: dict[str, Path] = {}
    for name in ("libavutil", "libavcodec"):
        (prefix / "include" / name).mkdir(parents=True)
        (prefix / "include" / name / f"{name}.h").write_text(
            f"int {name}_version(void);\n"
        )
        source = prefix / f"{name}.c"
        source.write_text(f"int {name}_version(void) {{ return {FAKE_MAJOR}; }}\n")
        dylib = prefix / "lib" / f"{name}.{FAKE_MAJOR}.dylib"
        capture(
            [
                "xcrun",
                "--sdk",
                FAKE_SLICE.sdk,
                "clang",
                "-dynamiclib",
                *cflags,
                f"-Wl,-install_name,@rpath/{dylib.name}",
                "-Wl,-headerpad_max_install_names",
                "-o",
                str(dylib),
                str(source),
                *map(str, dylibs),
            ]
        )
        dylibs.append(dylib)
        frameworks[name] = make_framework(
            name,
            dylib,
            prefix / "include" / name,
            info_plist(FAKE_SLICE, name, FAKE_TOOLCHAIN, "1"),
            tmp / "frameworks",
        )
    return frameworks


def copy_framework(framework: Path, directory: Path) -> Path:
    copy = directory / framework.name
    shutil.copytree(framework, copy, symlinks=True)
    return copy


@counterexample
def framework_with_second_rpath(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_rpath(read_macho(framework_binary(framework)), RPATH)
    bad = framework_binary(copy_framework(framework, tmp / "bad"))
    capture(["xcrun", "install_name_tool", "-add_rpath", str(tmp), str(bad)])
    return good, check_rpath(read_macho(bad), RPATH)


@counterexample
def install_id_is_absolute(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_install_id(
        read_macho(framework_binary(framework)), install_id("libavutil")
    )
    bad = framework_binary(copy_framework(framework, tmp / "bad"))
    capture(["xcrun", "install_name_tool", "-id", str(bad), str(bad)])
    return good, check_install_id(read_macho(bad), install_id("libavutil"))


@counterexample
def dependency_left_on_configure_install_name(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavcodec"]
    good = check_dependencies(read_macho(framework_binary(framework)), BUNDLED)
    bad = framework_binary(copy_framework(framework, tmp / "bad"))
    unrewritten = f"@rpath/libavutil.{FAKE_MAJOR}.dylib"
    capture(
        [
            "xcrun",
            "install_name_tool",
            "-change",
            install_id("libavutil"),
            unrewritten,
            str(bad),
        ]
    )
    return good, check_dependencies(read_macho(bad), BUNDLED)


@counterexample
def binary_built_above_floor(tmp: Path) -> tuple[Check, Check]:
    def build_version(directory: Path, target: str) -> Check:
        framework = fake_frameworks(directory, ("-target", target))["libavutil"]
        macho = read_macho(framework_binary(framework))
        return check_build_version(macho, FAKE_SLICE.platform, FAKE_SLICE.floor)

    return (
        build_version(tmp / "good", FAKE_SLICE.target),
        build_version(tmp / "bad", "arm64-apple-macos15.0"),
    )


@counterexample
def binary_with_x86_64_slice(tmp: Path) -> tuple[Check, Check]:
    def architectures(directory: Path, cflags: tuple[str, ...]) -> Check:
        framework = fake_frameworks(directory, cflags)["libavutil"]
        return check_architectures(read_macho(framework_binary(framework)), ARCHS)

    universal = (
        "-arch",
        "arm64",
        "-arch",
        "x86_64",
        f"-mmacosx-version-min={FAKE_SLICE.floor}",
    )
    return (
        architectures(tmp / "good", ("-target", FAKE_SLICE.target)),
        architectures(tmp / "bad", universal),
    )


@counterexample
def info_plist_without_minimum_version(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_info_plist(framework, FAKE_SLICE)
    bad = copy_framework(framework, tmp / "bad")
    with framework_plist(bad).open("rb") as file:
        plist = plistlib.load(file)
    del plist[FAKE_SLICE.minimum_version_key]
    with framework_plist(bad).open("wb") as file:
        plistlib.dump(plist, file)
    return good, check_info_plist(bad, FAKE_SLICE)
