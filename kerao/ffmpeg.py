import difflib
import os
import subprocess
import sys
from pathlib import Path

from common import (
    LIBRARIES,
    MAX_LISTED_LINES,
    ROOT,
    BuildError,
    Check,
    Slice,
    counterexample,
)

COMMITTED_CONFIGURE = ROOT / "kerao" / "configure"
SOURCE_PLACEHOLDER = "<source>"
EXPECTED_LICENSE = "LGPL version 2.1 or later"
LICENSE_PREFIX = "License: "
COMPONENTS_HEADER = "External libraries:"
CONFIG_LOG_TAIL_LINES = 40

EXCLUDED_LIBRARIES = ("avdevice", "avfilter", "swscale")
DEMUXERS = ("mov",)
PARSERS: dict[str, str] = {}
BSFS: dict[str, str] = {}
HWACCELS: dict[str, str] = {}
PREFIX = "/usr/local"


def component_args(kind: str, names: dict[str, str]) -> list[str]:
    return [f"--enable-{kind}={','.join(names)}"] if names else []


def configure_args(slice_: Slice, sdk_path: Path) -> list[str]:
    xcrun = f"xcrun --sdk {slice_.sdk}"
    target = f"-target {slice_.target}"
    return [
        f"--prefix={PREFIX}",
        "--install-name-dir=@rpath",
        "--disable-everything",
        "--disable-autodetect",
        "--disable-programs",
        "--disable-doc",
        *(f"--disable-{name}" for name in EXCLUDED_LIBRARIES),
        *(f"--enable-{name}" for name in LIBRARIES),
        "--enable-shared",
        "--disable-static",
        "--enable-pic",
        "--disable-network",
        "--enable-pthreads",
        "--enable-decoders",
        f"--enable-demuxer={','.join(DEMUXERS)}",
        *component_args("parser", PARSERS),
        *component_args("bsf", BSFS),
        *component_args("hwaccel", HWACCELS),
        "--arch=aarch64",
        "--target-os=darwin",
        f"--cc={xcrun} clang",
        f"--ar={xcrun} ar",
        f"--nm={xcrun} nm -g",
        f"--ranlib={xcrun} ranlib",
        f"--strip={xcrun} strip",
        f"--sysroot={sdk_path}",
        f"--extra-cflags={target}",
        f"--extra-ldflags={target} -Wl,-headerpad_max_install_names",
    ]


def build_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key != "revision"}


def run_configure(slice_: Slice, args: list[str], build_dir: Path) -> str:
    result = subprocess.run(
        [str(ROOT / "configure"), *args],
        check=False,
        cwd=build_dir,
        env=build_env(),
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        log = build_dir / "ffbuild" / "config.log"
        tail = (
            log.read_text(errors="replace").splitlines()[-CONFIG_LOG_TAIL_LINES:]
            if log.is_file()
            else []
        )
        raise BuildError(
            "\n".join(
                [f"configure failed for {slice_.identifier}:", result.stdout, *tail]
            )
        )
    return result.stdout.replace(str(ROOT), SOURCE_PLACEHOLDER)


def run_make(slice_: Slice, build_dir: Path, stage: Path) -> Path:
    """Install into stage and return the installed prefix inside it."""
    command = [
        "xcrun",
        "--sdk",
        slice_.sdk,
        "make",
        f"-j{os.cpu_count()}",
        "install",
        f"DESTDIR={stage}",
    ]
    result = subprocess.run(
        command, check=False, cwd=build_dir, env=build_env(), stdout=sys.stderr
    )
    if result.returncode != 0:
        raise BuildError(f"make failed for {slice_.identifier}")
    return stage / PREFIX.lstrip("/")


def license_lines(configure_output: str) -> list[str]:
    return [
        line.removeprefix(LICENSE_PREFIX)
        for line in configure_output.splitlines()
        if line.startswith(LICENSE_PREFIX)
    ]


def check_license(configure_output: str) -> Check:
    licenses = license_lines(configure_output)
    if len(licenses) != 1:
        return Check(
            "license", False, f"expected one License line, found {len(licenses)}"
        )
    return Check("license", licenses[0] == EXPECTED_LICENSE, licenses[0])


def component_lines(configure_output: str) -> list[str]:
    lines = configure_output.splitlines()
    return (
        lines[lines.index(COMPONENTS_HEADER) :] if COMPONENTS_HEADER in lines else lines
    )


def check_configure_output_committed(configure_output: str, committed: Path) -> Check:
    name = "committed configure output"
    if not committed.is_file():
        return Check(name, False, f"{committed} is missing")
    diff = difflib.unified_diff(
        component_lines(committed.read_text()), component_lines(configure_output), n=0
    )
    changed = [
        line
        for line in diff
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    if changed:
        return Check(
            name,
            False,
            f"{committed} differs: {' | '.join(changed[:MAX_LISTED_LINES])}",
        )
    return Check(name, True, str(committed))


FAKE_CONFIGURE_OUTPUT = f"""\
install prefix            {PREFIX}
source path               {SOURCE_PLACEHOLDER}
C compiler                xcrun --sdk macosx clang
ARCH                      aarch64 (generic)

{COMPONENTS_HEADER}

Libraries:
avcodec                 avutil
avformat                swresample

Enabled decoders:
aac                     h264

Enabled demuxers:
mov

{LICENSE_PREFIX}{EXPECTED_LICENSE}
"""


@counterexample
def license_line_is_not_lgpl21(tmp: Path) -> tuple[Check, Check]:
    gpl = FAKE_CONFIGURE_OUTPUT.replace(EXPECTED_LICENSE, "GPL version 2 or later")
    return check_license(FAKE_CONFIGURE_OUTPUT), check_license(gpl)


@counterexample
def committed_configure_output_is_stale(tmp: Path) -> tuple[Check, Check]:
    committed = tmp / "macos-arm64.txt"
    committed.write_text(FAKE_CONFIGURE_OUTPUT)
    good = check_configure_output_committed(FAKE_CONFIGURE_OUTPUT, committed)
    committed.write_text(
        FAKE_CONFIGURE_OUTPUT.replace("aac                     h264", "h264")
    )
    return good, check_configure_output_committed(FAKE_CONFIGURE_OUTPUT, committed)
