import dataclasses
import subprocess
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LISTED_LINES = 5

PLATFORM_MACOS = 1
PLATFORM_IOS = 2
PLATFORM_IOS_SIMULATOR = 7

ARCHS = ("arm64",)
IOS_DEVICE_FAMILIES = (1, 2)


@dataclasses.dataclass(frozen=True)
class Layout:
    """Paths are relative to the .framework directory."""

    contents: Path
    resources: Path
    rpath: str


VERSIONED = Layout(
    contents=Path("Versions") / "A",
    resources=Path("Versions") / "A" / "Resources",
    rpath="@loader_path/../../..",
)
FLAT = Layout(contents=Path(), resources=Path(), rpath="@loader_path/..")


@dataclasses.dataclass(frozen=True)
class Slice:
    identifier: str
    sdk: str
    target: str
    floor: str
    platform: int
    bundle_platform: str
    minimum_version_key: str
    layout: Layout
    cross_compile: bool
    device_families: tuple[int, ...] = ()
    required_capabilities: tuple[str, ...] = ()


IOS = Slice(
    identifier="ios-arm64",
    sdk="iphoneos",
    target="arm64-apple-ios17.0",
    floor="17.0",
    platform=PLATFORM_IOS,
    bundle_platform="iPhoneOS",
    minimum_version_key="MinimumOSVersion",
    layout=FLAT,
    cross_compile=True,
    device_families=IOS_DEVICE_FAMILIES,
    required_capabilities=ARCHS,
)
IOS_SIMULATOR = Slice(
    identifier="ios-arm64-simulator",
    sdk="iphonesimulator",
    target="arm64-apple-ios17.0-simulator",
    floor="17.0",
    platform=PLATFORM_IOS_SIMULATOR,
    bundle_platform="iPhoneSimulator",
    minimum_version_key="MinimumOSVersion",
    layout=FLAT,
    cross_compile=True,
    device_families=IOS_DEVICE_FAMILIES,
)
MACOS = Slice(
    identifier="macos-arm64",
    sdk="macosx",
    target="arm64-apple-macos14.0",
    floor="14.0",
    platform=PLATFORM_MACOS,
    bundle_platform="MacOSX",
    minimum_version_key="LSMinimumSystemVersion",
    layout=VERSIONED,
    cross_compile=False,
)
SLICES = (IOS, IOS_SIMULATOR, MACOS)

LIBRARIES = ("avutil", "avcodec", "avformat", "swresample")
FRAMEWORKS = tuple(f"lib{name}" for name in LIBRARIES)


class BuildError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def scoped(scope: str, check: Check) -> Check:
    return dataclasses.replace(check, name=f"{scope} {check.name}")


def capture(
    command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> str:
    result = subprocess.run(
        command, check=False, cwd=cwd, env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BuildError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


Counterexample = Callable[[Path], tuple[Check, Check]]
COUNTEREXAMPLES: list[Counterexample] = []


def counterexample(case: Counterexample) -> Counterexample:
    """Register a self-test case returning (good, bad): good must pass, bad must fail."""
    COUNTEREXAMPLES.append(case)
    return case
