import dataclasses
import shutil
from collections.abc import Callable
from pathlib import Path

from checkout import fake_git, git
from common import (
    IOS,
    IOS_SIMULATOR,
    MACOS,
    Check,
    Slice,
    build_env,
    capture,
    counterexample,
    scoped,
    stream,
)
from macho import check_object_build_versions, read_archive_builds

MESON_SUBSYSTEMS = {IOS: "ios", IOS_SIMULATOR: "ios-simulator", MACOS: "macos"}
CMAKE_SYSTEMS = {IOS: "iOS", IOS_SIMULATOR: "iOS", MACOS: "Darwin"}
CMAKE_POLICY_VERSION_MINIMUM = "3.5"

Builder = Callable[[Slice, Path, Path, Path, Path], None]


@dataclasses.dataclass(frozen=True)
class Dep:
    """build(slice, sdk path, checkout, work dir, prefix) installs archive under prefix/lib."""

    name: str
    repository: str
    tag: str
    commit: str
    license: str
    archive: str
    symbol: str
    build: Builder


def meson_literal(values: list[str]) -> str:
    quoted = (value.replace("\\", "\\\\").replace("'", "\\'") for value in values)
    return "[" + ", ".join(f"'{value}'" for value in quoted) + "]"


def meson_cross_file(slice_: Slice, sdk_path: Path) -> str:
    xcrun = ["xcrun", "--sdk", slice_.sdk]
    flags = meson_literal(["-target", slice_.target, "-isysroot", str(sdk_path)])
    return f"""\
[binaries]
c = {meson_literal([*xcrun, "clang"])}
ar = {meson_literal([*xcrun, "ar"])}
strip = {meson_literal([*xcrun, "strip"])}

[built-in options]
c_args = {flags}
c_link_args = {flags}

[properties]
needs_exe_wrapper = {"true" if slice_.cross_compile else "false"}

[host_machine]
system = 'darwin'
subsystem = '{MESON_SUBSYSTEMS[slice_]}'
kernel = 'xnu'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'
"""


def build_dav1d(
    slice_: Slice, sdk_path: Path, checkout: Path, work: Path, prefix: Path
) -> None:
    work.mkdir(parents=True)
    cross_file = work / "cross.ini"
    cross_file.write_text(meson_cross_file(slice_, sdk_path))
    what = f"dav1d for {slice_.identifier}"
    stream(
        [
            *("meson", "setup", "--cross-file", str(cross_file)),
            *("--prefix", str(prefix), "--libdir", "lib"),
            *("--buildtype", "release", "--default-library", "static"),
            "--wrap-mode=nodownload",
            "-Denable_tools=false",
            "-Denable_tests=false",
            str(work / "build"),
            str(checkout),
        ],
        f"meson setup of {what}",
        env=build_env(),
    )
    stream(
        ["meson", "install", "-C", str(work / "build"), "--quiet"],
        f"meson install of {what}",
        env=build_env(),
    )


def build_uavs3d(
    slice_: Slice, sdk_path: Path, checkout: Path, work: Path, prefix: Path
) -> None:
    build_dir = work / "build"
    flags = f"-target {slice_.target}"
    clang = capture(["xcrun", "--sdk", slice_.sdk, "--find", "clang"])
    what = f"libuavs3d for {slice_.identifier}"
    stream(
        [
            *("cmake", "-S", str(checkout), "-B", str(build_dir), "-G", "Ninja"),
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_INSTALL_PREFIX={prefix}",
            f"-DCMAKE_POLICY_VERSION_MINIMUM={CMAKE_POLICY_VERSION_MINIMUM}",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DCOMPILE_10BIT=1",
            f"-DCMAKE_SYSTEM_NAME={CMAKE_SYSTEMS[slice_]}",
            "-DCMAKE_SYSTEM_PROCESSOR=arm64",
            f"-DCMAKE_OSX_SYSROOT={sdk_path}",
            f"-DCMAKE_C_COMPILER={clang}",
            f"-DCMAKE_C_FLAGS={flags}",
            f"-DCMAKE_ASM_FLAGS={flags}",
        ],
        f"cmake configure of {what}",
        cwd=checkout,
        env=build_env(),
    )
    stream(
        ["cmake", "--build", str(build_dir), "--target", "uavs3d"],
        f"cmake build of {what}",
        env=build_env(),
    )
    stream(
        ["cmake", "--install", str(build_dir)],
        f"cmake install of {what}",
        env=build_env(),
    )


DAV1D = Dep(
    name="dav1d",
    repository="https://code.videolan.org/videolan/dav1d.git",
    tag="1.5.4",
    commit="54706fc6bc0cdecab7e9593974a4039cc038fca7",
    license="COPYING",
    archive="libdav1d.a",
    symbol="dav1d_version",
    build=build_dav1d,
)
UAVS3D = Dep(
    name="libuavs3d",
    repository="https://github.com/uavs3/uavs3d.git",
    tag="1.2",
    commit="0e20d2c291853f196c68922a264bcd8471d75b68",
    license="COPYING",
    archive="libuavs3d.a",
    symbol="uavs3d_decode",
    build=build_uavs3d,
)
DEPS = (DAV1D, UAVS3D)


def fetch(dep: Dep, checkout: Path) -> Path:
    capture(
        [
            *("git", "-c", "advice.detachedHead=false", "clone", "--quiet"),
            *("--branch", dep.tag, dep.repository, str(checkout)),
        ]
    )
    return checkout


def check_commit(dep: Dep, checkout: Path) -> Check:
    head = git(checkout, "rev-parse", "HEAD")
    return Check(
        f"{dep.name} commit",
        head == dep.commit,
        f"{dep.tag} is {head}"
        + ("" if head == dep.commit else f", pinned {dep.commit}"),
    )


def build_deps(
    slice_: Slice, sdk_path: Path, checkouts: dict[Dep, Path], work: Path
) -> tuple[Path, list[Check]]:
    """Build every dep for slice_ into one prefix; return its pkg-config dir and checks."""
    prefix = work / "prefix"
    checks = []
    for dep in DEPS:
        dep.build(slice_, sdk_path, checkouts[dep], work / dep.name, prefix)
        builds = read_archive_builds(prefix / "lib" / dep.archive)
        check = check_object_build_versions(builds, slice_.platform, slice_.floor)
        checks.append(scoped(dep.name, check))
    return prefix / "lib" / "pkgconfig", checks


def check_linked(dep: Dep, binary: Path) -> Check:
    """binary is an unstripped image that must define dep.symbol, exported or not."""
    symbol = f"_{dep.symbol}"
    defined = capture(["xcrun", "nm", "--defined-only", "-j", str(binary)]).split()
    return Check(
        f"{dep.name} symbols",
        symbol in defined,
        f"{symbol} {'defined' if symbol in defined else 'not defined'}",
    )


def linked_checks(libavcodec: Path) -> list[Check]:
    return [scoped("libavcodec", check_linked(dep, libavcodec)) for dep in DEPS]


def copy_notices(checkouts: dict[Dep, Path], notices: Path) -> None:
    for dep, checkout in checkouts.items():
        (notices / dep.name).mkdir(parents=True)
        shutil.copy(checkout / dep.license, notices / dep.name / dep.license)


def fake_upstream(tmp: Path) -> Dep:
    """DAV1D pointed at a local repository whose tag sits on its second commit."""
    repo = tmp / "upstream"
    repo.mkdir()
    fake_git(repo, "init", "-q")
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "first")
    fake_git(repo, "commit", "-q", "--allow-empty", "-m", "release")
    fake_git(repo, "tag", "-a", "1.0.0", "-m", "1.0.0")
    return dataclasses.replace(
        DAV1D,
        repository=str(repo),
        tag="1.0.0",
        commit=git(repo, "rev-parse", "HEAD"),
    )


@counterexample
def dep_pinned_to_another_commit(tmp: Path) -> tuple[Check, Check]:
    dep = fake_upstream(tmp)
    checkout = fetch(dep, tmp / "checkout")
    parent = git(Path(dep.repository), "rev-parse", "HEAD~1")
    return (
        check_commit(dep, checkout),
        check_commit(dataclasses.replace(dep, commit=parent), checkout),
    )


def fake_archive(directory: Path, slice_: Slice, targets: tuple[str, ...]) -> Path:
    """A static library with one object compiled for each target."""
    directory.mkdir(parents=True)
    objects = []
    for index, target in enumerate(targets):
        source = directory / f"object{index}.c"
        source.write_text(f"int object{index}(void) {{ return {index}; }}\n")
        objects.append(source.with_suffix(".o"))
        capture(
            [
                *("xcrun", "--sdk", slice_.sdk, "clang"),
                *("-target", target, "-c", "-o", str(objects[-1]), str(source)),
            ]
        )
    archive = directory / "libfake.a"
    capture(
        ["xcrun", "--sdk", slice_.sdk, "ar", "rcs", str(archive), *map(str, objects)]
    )
    return archive


@counterexample
def archive_object_above_floor(tmp: Path) -> tuple[Check, Check]:
    def build_version(directory: Path, targets: tuple[str, ...]) -> Check:
        archive = fake_archive(directory, IOS, targets)
        return check_object_build_versions(
            read_archive_builds(archive), IOS.platform, IOS.floor
        )

    return (
        build_version(tmp / "good", (IOS.target, IOS.target)),
        build_version(tmp / "bad", (IOS.target, "arm64-apple-ios18.0")),
    )


@counterexample
def libavcodec_without_a_dep_symbol(tmp: Path) -> tuple[Check, Check]:
    def linked(name: str, symbols: tuple[str, ...]) -> Check:
        source = tmp / f"{name}.c"
        source.write_text(
            "".join(f"int {symbol}(void) {{ return 0; }}\n" for symbol in symbols)
        )
        dylib = tmp / f"{name}.dylib"
        capture(
            [
                *("xcrun", "--sdk", MACOS.sdk, "clang", "-dynamiclib"),
                *("-target", MACOS.target, "-Wl,-exported_symbol,_avcodec_version"),
                *("-o", str(dylib), str(source)),
            ]
        )
        return check_linked(DAV1D, dylib)

    return (
        linked("good", ("avcodec_version", DAV1D.symbol)),
        linked("bad", ("avcodec_version", UAVS3D.symbol)),
    )
