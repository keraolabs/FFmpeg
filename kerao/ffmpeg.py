import difflib
import os
import re
import subprocess
from pathlib import Path

from common import (
    LIBRARIES,
    MAX_LISTED_LINES,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Slice,
    build_env,
    counterexample,
    stream,
)

COMMITTED_CONFIGURE = ROOT / "kerao" / "configure"
SOURCE_PLACEHOLDER = "<source>"
EXPECTED_LICENSE = "LGPL version 2.1 or later"
LICENSE_PREFIX = "License: "
COMPONENTS_HEADER = "External libraries:"
CONFIG_LOG_TAIL_LINES = 40
CONFIGURED_DECODER = re.compile(r"^#define CONFIG_(\w+)_DECODER 1$", re.MULTILINE)

EXCLUDED_LIBRARIES = ("avdevice", "avfilter", "swscale")
EXTERNAL_LIBRARIES = ("libdav1d", "libuavs3d", "zlib", "bzlib")
EXTERNAL_DECODERS = ("libdav1d", "libuavs3d")
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
        *(f"--enable-{name}" for name in EXTERNAL_LIBRARIES),
        "--pkg-config-flags=--static",
        f"--enable-demuxer={','.join(DEMUXERS)}",
        *component_args("parser", PARSERS),
        *component_args("bsf", BSFS),
        *component_args("hwaccel", HWACCELS),
        *(["--enable-cross-compile"] if slice_.cross_compile else []),
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


def run_configure(
    slice_: Slice, args: list[str], build_dir: Path, pkgconfig: Path
) -> str:
    """pkgconfig is the only directory pkg-config searches."""
    result = subprocess.run(
        [str(ROOT / "configure"), *args],
        check=False,
        cwd=build_dir,
        env={**build_env(), "PKG_CONFIG_LIBDIR": str(pkgconfig)},
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
    stream(command, f"make for {slice_.identifier}", cwd=build_dir, env=build_env())
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


def external_libraries(configure_output: str) -> frozenset[str]:
    lines = component_lines(configure_output)
    if COMPONENTS_HEADER not in lines:
        return frozenset()
    section = lines[lines.index(COMPONENTS_HEADER) + 1 :]
    end = section.index("") if "" in section else len(section)
    return frozenset(" ".join(section[:end]).split())


def check_external_libraries(configure_output: str) -> Check:
    found = external_libraries(configure_output)
    expected = frozenset(EXTERNAL_LIBRARIES)
    problems = [
        f"{verb} {', '.join(sorted(names))}"
        for verb, names in (("lacks", expected - found), ("adds", found - expected))
        if names
    ]
    return Check(
        "external libraries",
        not problems,
        "; ".join(problems) or ", ".join(sorted(found)),
    )


def configured_decoders(config_components: Path) -> frozenset[str]:
    return frozenset(
        name.lower()
        for name in CONFIGURED_DECODER.findall(config_components.read_text())
    )


def check_configured_decoders(config_components: dict[str, Path]) -> Check:
    """config_components maps each slice identifier to its config_components.h."""
    decoders = {
        label: configured_decoders(path) for label, path in config_components.items()
    }
    (reference_label, reference), *others = decoders.items()
    problems = [f"{label} has none" for label, names in decoders.items() if not names]
    problems += [
        f"{label} lacks {', '.join(missing)}"
        for label, names in decoders.items()
        if names
        and (missing := [name for name in EXTERNAL_DECODERS if name not in names])
    ]
    for label, names in others:
        for verb, differing in (
            ("lacks", reference - names),
            ("adds", names - reference),
        ):
            if differing:
                problems.append(
                    f"{label} {verb} {', '.join(sorted(differing))} against {reference_label}"
                )
    return Check(
        "configured decoders",
        not problems,
        "; ".join(problems) or f"{len(reference)} in {', '.join(decoders)}",
    )


FAKE_CONFIGURE_OUTPUT = f"""\
install prefix            {PREFIX}
source path               {SOURCE_PLACEHOLDER}
C compiler                xcrun --sdk macosx clang
ARCH                      aarch64 (generic)

{COMPONENTS_HEADER}
bzlib                   libdav1d                libuavs3d
zlib

External libraries providing hardware acceleration:

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


@counterexample
def configure_dropped_an_external_library(tmp: Path) -> tuple[Check, Check]:
    without_zlib = FAKE_CONFIGURE_OUTPUT.replace("\nzlib\n", "\n")
    return (
        check_external_libraries(FAKE_CONFIGURE_OUTPUT),
        check_external_libraries(without_zlib),
    )


FAKE_CONFIG_COMPONENTS = """\
/* Automatically generated by configure - do not modify! */
#ifndef FFMPEG_CONFIG_COMPONENTS_H
#define FFMPEG_CONFIG_COMPONENTS_H
#define CONFIG_AAC_DECODER 1
#define CONFIG_H264_DECODER 1
#define CONFIG_HEVC_DECODER 1
#define CONFIG_LIBDAV1D_DECODER 1
#define CONFIG_LIBUAVS3D_DECODER 1
#define CONFIG_AAC_AT_DECODER 0
#define CONFIG_AAC_ENCODER 0
#define CONFIG_MOV_DEMUXER 1
#endif /* FFMPEG_CONFIG_COMPONENTS_H */
"""


@counterexample
def slice_configured_without_a_decoder(tmp: Path) -> tuple[Check, Check]:
    headers = {slice_.identifier: tmp / f"{slice_.identifier}.h" for slice_ in SLICES}
    for header in headers.values():
        header.write_text(FAKE_CONFIG_COMPONENTS)
    good = check_configured_decoders(headers)
    headers[SLICES[-1].identifier].write_text(
        FAKE_CONFIG_COMPONENTS.replace("CONFIG_HEVC_DECODER 1", "CONFIG_HEVC_DECODER 0")
    )
    return good, check_configured_decoders(headers)


@counterexample
def every_slice_configured_without_an_external_decoder(
    tmp: Path,
) -> tuple[Check, Check]:
    headers = {slice_.identifier: tmp / f"{slice_.identifier}.h" for slice_ in SLICES}
    for header in headers.values():
        header.write_text(FAKE_CONFIG_COMPONENTS)
    good = check_configured_decoders(headers)
    for header in headers.values():
        header.write_text(
            FAKE_CONFIG_COMPONENTS.replace(
                "CONFIG_LIBUAVS3D_DECODER 1", "CONFIG_LIBUAVS3D_DECODER 0"
            )
        )
    return good, check_configured_decoders(headers)
