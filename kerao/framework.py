import plistlib
import re
import shutil
from pathlib import Path

from checkout import UPSTREAM_VERSION
from common import (
    ARCHS,
    FRAMEWORKS,
    MACOS,
    BuildError,
    Check,
    Layout,
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


def install_id(name: str, layout: Layout) -> str:
    return f"@rpath/{(Path(f'{name}.framework') / layout.contents / name).as_posix()}"


def bundled(layout: Layout) -> frozenset[str]:
    return frozenset(install_id(name, layout) for name in FRAMEWORKS)


def framework_binary(framework: Path, layout: Layout) -> Path:
    return framework / layout.contents / framework.stem


def framework_headers(framework: Path, layout: Layout) -> Path:
    return framework / layout.contents / "Headers"


def delivered_framework(output: Path, slice_: Slice, name: str) -> Path:
    return output / f"{name}.xcframework" / slice_.identifier / f"{name}.framework"


def framework_plist(framework: Path, layout: Layout) -> Path:
    return framework / layout.resources / "Info.plist"


def xcode_number(version: str) -> str:
    major, minor, patch = (version.split(".") + ["0", "0"])[:3]
    return f"{int(major):02d}{minor}{patch}"


def platform_keys(slice_: Slice) -> dict[str, object]:
    keys: dict[str, object] = {slice_.minimum_version_key: slice_.floor}
    if slice_.device_families:
        keys["UIDeviceFamily"] = list(slice_.device_families)
    if slice_.required_capabilities:
        keys["UIRequiredDeviceCapabilities"] = list(slice_.required_capabilities)
    return keys


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
        **platform_keys(slice_),
    }


def rewrite_install_names(binary: Path, name: str, layout: Layout) -> None:
    changes: list[str] = []
    for dependency in read_macho(binary).dylibs:
        match = CONFIGURE_INSTALL_NAME.fullmatch(dependency)
        if match and match[1] in FRAMEWORKS:
            changes += ["-change", dependency, install_id(match[1], layout)]
    capture(
        [
            "xcrun",
            "install_name_tool",
            "-id",
            install_id(name, layout),
            *changes,
            "-add_rpath",
            layout.rpath,
            str(binary),
        ]
    )


def make_framework(
    name: str,
    dylib: Path,
    headers: Path,
    plist: dict[str, object],
    frameworks_dir: Path,
    layout: Layout,
) -> Path:
    framework = frameworks_dir / f"{name}.framework"
    contents = framework / layout.contents
    contents.mkdir(parents=True)
    (framework / layout.resources).mkdir(exist_ok=True)
    shutil.copy(dylib, contents / name)
    shutil.copytree(headers, framework_headers(framework, layout))
    with framework_plist(framework, layout).open("wb") as file:
        plistlib.dump(plist, file)
    if layout.contents.parts:
        current = layout.contents.parent / "Current"
        (framework / current).symlink_to(layout.contents.name)
        for entry in (name, "Headers", "Resources"):
            (framework / entry).symlink_to(current / entry)
    rewrite_install_names(contents / name, name, layout)
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
            slice_.layout,
        )


def check_info_plist(framework: Path, slice_: Slice) -> Check:
    name = framework.stem
    with framework_plist(framework, slice_.layout).open("rb") as file:
        plist = plistlib.load(file)
    required = {
        **dict.fromkeys(INFO_PLIST_KEYS),
        "CFBundleExecutable": name,
        "CFBundleIdentifier": BUNDLE_ID_PREFIX + name,
        "CFBundleName": name,
        "CFBundlePackageType": "FMWK",
        "CFBundleShortVersionString": UPSTREAM_VERSION,
        "CFBundleSupportedPlatforms": [slice_.bundle_platform],
        **platform_keys(slice_),
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


def framework_checks(output: Path, slice_: Slice, name: str) -> list[Check]:
    layout = slice_.layout
    framework = delivered_framework(output, slice_, name)
    macho = read_macho(framework_binary(framework, layout))
    checks = [
        check_build_version(macho, slice_.platform, slice_.floor),
        check_architectures(macho, ARCHS),
        check_install_id(macho, install_id(name, layout)),
        check_rpath(macho, layout.rpath),
        check_dependencies(macho, bundled(layout)),
        check_info_plist(framework, slice_),
    ]
    return [scoped(f"{slice_.identifier} {name}", check) for check in checks]


FAKE_MAJOR = 1


def fake_frameworks(
    tmp: Path, slice_: Slice = MACOS, cflags: tuple[str, ...] | None = None
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
                slice_.sdk,
                "clang",
                "-dynamiclib",
                *(cflags or ("-target", slice_.target)),
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
            info_plist(slice_, name, FAKE_TOOLCHAIN, "1"),
            tmp / "frameworks",
            slice_.layout,
        )
    return frameworks


def copy_framework(framework: Path, directory: Path) -> Path:
    copy = directory / framework.name
    shutil.copytree(framework, copy, symlinks=True)
    return copy


@counterexample
def framework_with_second_rpath(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_rpath(
        read_macho(framework_binary(framework, MACOS.layout)), MACOS.layout.rpath
    )
    bad = framework_binary(copy_framework(framework, tmp / "bad"), MACOS.layout)
    capture(["xcrun", "install_name_tool", "-add_rpath", str(tmp), str(bad)])
    return good, check_rpath(read_macho(bad), MACOS.layout.rpath)


@counterexample
def install_id_is_absolute(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_install_id(
        read_macho(framework_binary(framework, MACOS.layout)),
        install_id("libavutil", MACOS.layout),
    )
    bad = framework_binary(copy_framework(framework, tmp / "bad"), MACOS.layout)
    capture(["xcrun", "install_name_tool", "-id", str(bad), str(bad)])
    return good, check_install_id(
        read_macho(bad), install_id("libavutil", MACOS.layout)
    )


@counterexample
def dependency_left_on_configure_install_name(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavcodec"]
    good = check_dependencies(
        read_macho(framework_binary(framework, MACOS.layout)), bundled(MACOS.layout)
    )
    bad = framework_binary(copy_framework(framework, tmp / "bad"), MACOS.layout)
    unrewritten = f"@rpath/libavutil.{FAKE_MAJOR}.dylib"
    capture(
        [
            "xcrun",
            "install_name_tool",
            "-change",
            install_id("libavutil", MACOS.layout),
            unrewritten,
            str(bad),
        ]
    )
    return good, check_dependencies(read_macho(bad), bundled(MACOS.layout))


@counterexample
def binary_built_above_floor(tmp: Path) -> tuple[Check, Check]:
    def build_version(directory: Path, target: str) -> Check:
        framework = fake_frameworks(directory, MACOS, ("-target", target))["libavutil"]
        macho = read_macho(framework_binary(framework, MACOS.layout))
        return check_build_version(macho, MACOS.platform, MACOS.floor)

    return (
        build_version(tmp / "good", MACOS.target),
        build_version(tmp / "bad", "arm64-apple-macos15.0"),
    )


@counterexample
def binary_with_x86_64_slice(tmp: Path) -> tuple[Check, Check]:
    def architectures(directory: Path, cflags: tuple[str, ...]) -> Check:
        framework = fake_frameworks(directory, MACOS, cflags)["libavutil"]
        return check_architectures(
            read_macho(framework_binary(framework, MACOS.layout)), ARCHS
        )

    universal = (
        "-arch",
        "arm64",
        "-arch",
        "x86_64",
        f"-mmacosx-version-min={MACOS.floor}",
    )
    return (
        architectures(tmp / "good", ("-target", MACOS.target)),
        architectures(tmp / "bad", universal),
    )


@counterexample
def info_plist_without_minimum_version(tmp: Path) -> tuple[Check, Check]:
    framework = fake_frameworks(tmp)["libavutil"]
    good = check_info_plist(framework, MACOS)
    bad = copy_framework(framework, tmp / "bad")
    with framework_plist(bad, MACOS.layout).open("rb") as file:
        plist = plistlib.load(file)
    del plist[MACOS.minimum_version_key]
    with framework_plist(bad, MACOS.layout).open("wb") as file:
        plistlib.dump(plist, file)
    return good, check_info_plist(bad, MACOS)
