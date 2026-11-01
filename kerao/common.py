import dataclasses
import subprocess
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LISTED_LINES = 5

PLATFORM_MACOS = 1


@dataclasses.dataclass(frozen=True)
class Slice:
    identifier: str
    sdk: str
    target: str
    floor: str
    platform: int
    bundle_platform: str
    minimum_version_key: str


SLICES = (
    Slice(
        identifier="macos-arm64",
        sdk="macosx",
        target="arm64-apple-macos14.0",
        floor="14.0",
        platform=PLATFORM_MACOS,
        bundle_platform="MacOSX",
        minimum_version_key="LSMinimumSystemVersion",
    ),
)

LIBRARIES = ("avutil", "avcodec", "avformat", "swresample")
FRAMEWORKS = tuple(f"lib{name}" for name in LIBRARIES)
ARCHS = ("arm64",)


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
