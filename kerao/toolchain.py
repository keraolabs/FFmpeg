import dataclasses
import re
from pathlib import Path

from common import SLICES, BuildError, capture

TOOLS = ("meson", "ninja", "cmake", "pkg-config")
CMAKE_VERSION_PREFIX = "cmake version "


@dataclasses.dataclass(frozen=True)
class Sdk:
    name: str
    version: str
    build: str
    platform_version: str
    path: Path


@dataclasses.dataclass(frozen=True)
class Toolchain:
    xcode_version: str
    xcode_build: str
    machine_build: str
    sdks: dict[str, Sdk]
    tools: dict[str, str]


def read_sdk(name: str) -> Sdk:
    def show(what: str) -> str:
        return capture(["xcrun", "--sdk", name, f"--show-sdk-{what}"])

    return Sdk(
        name=name,
        version=show("version"),
        build=show("build-version"),
        platform_version=show("platform-version"),
        path=Path(show("path")),
    )


def read_tool_version(name: str) -> str:
    output = capture([name, "--version"])
    return output.splitlines()[0].removeprefix(CMAKE_VERSION_PREFIX) if output else ""


def read_toolchain() -> Toolchain:
    version = re.fullmatch(
        r"Xcode (\S+)\nBuild version (\S+)",
        capture(["xcrun", "xcodebuild", "-version"]),
    )
    if version is None:
        raise BuildError("cannot read the Xcode version from xcodebuild -version")
    return Toolchain(
        xcode_version=version[1],
        xcode_build=version[2],
        machine_build=capture(["sw_vers", "-buildVersion"]),
        sdks={slice_.identifier: read_sdk(slice_.sdk) for slice_ in SLICES},
        tools={name: read_tool_version(name) for name in TOOLS},
    )


def fake_sdk(name: str, build: str) -> Sdk:
    return Sdk(
        name=name,
        version="27.0",
        build=build,
        platform_version="27.0",
        path=Path(f"/SDKs/{name}27.0.sdk"),
    )


FAKE_TOOLCHAIN = Toolchain(
    xcode_version="27.0",
    xcode_build="27A266a",
    machine_build="26A434",
    sdks={
        "ios-arm64": fake_sdk("iphoneos", "24A430"),
        "ios-arm64-simulator": fake_sdk("iphonesimulator", "24A430"),
        "macos-arm64": fake_sdk("macosx", "26A425"),
    },
    tools={
        "meson": "1.11.1",
        "ninja": "1.13.2",
        "cmake": "4.3.2",
        "pkg-config": "2.5.1",
    },
)
