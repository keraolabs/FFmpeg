import dataclasses
import re
from pathlib import Path

from common import Check, capture

DYLIB_COMMANDS = frozenset(
    {
        "LC_LOAD_DYLIB",
        "LC_LOAD_WEAK_DYLIB",
        "LC_REEXPORT_DYLIB",
        "LC_LOAD_UPWARD_DYLIB",
        "LC_LAZY_LOAD_DYLIB",
    }
)
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
OFFSET_SUFFIX = re.compile(r" \(offset \d+\)$")


@dataclasses.dataclass(frozen=True)
class MachO:
    path: Path
    archs: tuple[str, ...]
    install_ids: tuple[str, ...]
    rpaths: tuple[str, ...]
    dylibs: tuple[str, ...]
    builds: tuple[tuple[int, str], ...]


def load_commands(otool_output: str) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for line in otool_output.splitlines():
        key, _, value = line.strip().partition(" ")
        value = OFFSET_SUFFIX.sub("", value.strip())
        if key == "cmd":
            commands.append({"cmd": value})
        elif commands:
            commands[-1].setdefault(key, value)
    return commands


def read_macho(path: Path) -> MachO:
    commands = load_commands(capture(["xcrun", "otool", "-l", str(path)]))

    def values(cmds: set[str] | frozenset[str], key: str) -> tuple[str, ...]:
        return tuple(command[key] for command in commands if command["cmd"] in cmds)

    return MachO(
        path=path,
        archs=tuple(capture(["xcrun", "lipo", "-archs", str(path)]).split()),
        install_ids=values({"LC_ID_DYLIB"}, "name"),
        rpaths=values({"LC_RPATH"}, "path"),
        dylibs=values(DYLIB_COMMANDS, "name"),
        builds=tuple(
            (int(command["platform"]), command["minos"])
            for command in commands
            if command["cmd"] == "LC_BUILD_VERSION"
        ),
    )


def check_rpath(macho: MachO, rpath: str) -> Check:
    return Check(
        "rpath", macho.rpaths == (rpath,), ", ".join(macho.rpaths) or "no LC_RPATH"
    )


def check_install_id(macho: MachO, install_id: str) -> Check:
    return Check(
        "install id",
        macho.install_ids == (install_id,),
        ", ".join(macho.install_ids) or "no LC_ID_DYLIB",
    )


def check_dependencies(macho: MachO, bundled: set[str]) -> Check:
    """bundled holds the install ids of the frameworks shipped alongside this binary."""
    foreign = [
        name
        for name in macho.dylibs
        if name not in bundled and not name.startswith(SYSTEM_PREFIXES)
    ]
    return Check(
        "dependencies",
        not foreign,
        ", ".join(foreign)
        or f"{len(macho.dylibs)} load commands, all bundled or system",
    )


def check_build_version(macho: MachO, platform: int, floor: str) -> Check:
    return Check(
        "build version",
        macho.builds == ((platform, floor),),
        ", ".join(f"platform {number} minos {minos}" for number, minos in macho.builds)
        or "no LC_BUILD_VERSION",
    )


def check_architectures(macho: MachO, archs: tuple[str, ...]) -> Check:
    return Check("architectures", macho.archs == archs, " ".join(macho.archs))
