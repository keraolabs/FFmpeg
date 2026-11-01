import dataclasses
import re
from pathlib import Path

from common import SLICES, BuildError, capture


@dataclasses.dataclass(frozen=True)
class Sdk:
    name: str
    version: str
    path: Path


@dataclasses.dataclass(frozen=True)
class Toolchain:
    xcode_version: str
    xcode_build: str
    sdks: dict[str, Sdk]


def read_sdk(name: str) -> Sdk:
    def show(what: str) -> str:
        return capture(["xcrun", "--sdk", name, f"--show-sdk-{what}"])

    return Sdk(
        name=name,
        version=show("version"),
        path=Path(show("path")),
    )


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
        sdks={slice_.identifier: read_sdk(slice_.sdk) for slice_ in SLICES},
    )
