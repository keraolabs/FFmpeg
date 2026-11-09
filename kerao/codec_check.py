import dataclasses
import json
import shlex
import shutil
from collections.abc import Callable
from pathlib import Path

from checkout import UPSTREAM_TAG
from common import (
    FRAMEWORKS,
    IOS,
    IOS_SIMULATOR,
    MACOS,
    ROOT,
    SLICES,
    BuildError,
    Check,
    Slice,
    capture,
    counterexample,
    scoped,
)
from framework import delivered_framework
from runners import Runner, compile_program, run_on_mac
from toolchain import Toolchain

MANIFEST = ROOT / "kerao" / "codecs.json"
CHECK_PROGRAM = ROOT / "kerao" / "codec_check.c"
PROTOCOL = "kerao-codec-check"
CODECS_CHECK = "codecs"
VERSION_CHECK = "av_version_info"
STREAM_READ_CHECK = "stream read"
PROGRAM_CHECKS = (CODECS_CHECK, VERSION_CHECK, STREAM_READ_CHECK)
STREAM_READ_PLAIN = "6 fd09c391 13 1743ca92 eof"
"""The packet count and CRC of the video and the audio of kerao/stream_read_media.h as
av_read_frame() alone reads them on n9.0.2-kerao.1, and its clean end."""
NOT_RUN = "not run: this slice has no runner"
NO_RESULT = "no complete result"


@dataclasses.dataclass(frozen=True)
class ProgramOutput:
    version: str
    decoders: int
    codecs: frozenset[str]
    stream_reads: tuple[str, ...]


def load_manifest(path: Path) -> frozenset[str]:
    """The codec names path lists under "codecs", across every media type."""
    try:
        listed = json.loads(path.read_text())["codecs"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BuildError(f"cannot read the codec list in {path}: {error}") from error
    if not isinstance(listed, dict) or not all(
        isinstance(kind, list) for kind in listed.values()
    ):
        raise BuildError(f'{path}: "codecs" must map each media type to a list')
    names = [name for kind in listed.values() for name in kind]
    if not names or not all(isinstance(name, str) and name for name in names):
        raise BuildError(f"{path} lists no codecs or a codec that is not a name")
    if len(set(names)) != len(names):
        raise BuildError(f"{path} lists a codec more than once")
    return frozenset(names)


class NoResult(Exception):
    """The console output holds no complete result of the check program."""


def parse_output(console: str) -> ProgramOutput:
    """Read the lines the check program prefixes with PROTOCOL and ignore the rest.

    Raises NoResult unless they hold one version line and an end line that counts
    the decoder lines before it.
    """
    versions: list[str] = []
    codecs: list[str] = []
    stream_reads: list[str] = []
    ends: list[str] = []
    for line in console.splitlines():
        prefix, _, rest = line.partition(" ")
        if prefix != PROTOCOL:
            continue
        kind, _, value = rest.partition(" ")
        if kind == "version":
            versions.append(value)
        elif kind == "decoder":
            codecs.append(value.split(" ")[-1])
        elif kind == "stream-read":
            stream_reads.append(value)
        elif kind == "end":
            ends.append(value)
    if len(versions) != 1 or ends != [str(len(codecs))]:
        raise NoResult(
            f"printed {len(versions)} versions, {len(codecs)} decoders "
            f"and end {', '.join(ends) or 'never'}"
        )
    return ProgramOutput(
        version=versions[0],
        decoders=len(codecs),
        codecs=frozenset(codecs),
        stream_reads=tuple(stream_reads),
    )


def check_codecs(listed: frozenset[str], output: ProgramOutput) -> Check:
    """Fail on every listed codec no decoder covers; name the decoded ones not listed."""
    missing = sorted(listed - output.codecs)
    unlisted = sorted(output.codecs - listed)
    found = (
        f"lacks {len(missing)} of {len(listed)} listed: {', '.join(missing)}"
        if missing
        else f"all {len(listed)} listed"
    )
    return Check(
        CODECS_CHECK,
        not missing,
        f"{found}; {len(output.codecs)} codecs from {output.decoders} decoders; "
        f"not listed: {', '.join(unlisted) or 'none'}",
    )


def check_version(version: str, release_tag: str | None) -> Check:
    """A release build must report exactly release_tag; a dev build (None) any n9.0.2 describe."""
    if release_tag is not None:
        expected = release_tag
        ok = version == release_tag
    else:
        expected = f"{UPSTREAM_TAG} or {UPSTREAM_TAG}-…"
        ok = version == UPSTREAM_TAG or version.startswith(f"{UPSTREAM_TAG}-")
    return Check(
        VERSION_CHECK, ok, version if ok else f"{version}, expected {expected}"
    )


def stream_reads(plain: str) -> tuple[str, str]:
    """The stream-read lines of a program whose av_read_frame() alone gives plain: the
    stream read of the audio returns all of it and ends cleanly, and av_read_frame()
    then returns the whole video and no audio."""
    video, video_crc, audio, audio_crc, _ = plain.split(" ")
    return f"plain {plain}", f"stream {audio} {audio_crc} eof {video} {video_crc} 0 eof"


def check_stream_read(output: ProgramOutput, plain: str = STREAM_READ_PLAIN) -> Check:
    """The program must print exactly stream_reads(plain)."""
    expected = stream_reads(plain)
    if output.stream_reads == expected:
        return Check(STREAM_READ_CHECK, True, " | ".join(expected))
    found = " | ".join(output.stream_reads) or "no stream-read line"
    return Check(STREAM_READ_CHECK, False, f"{found}, expected {' | '.join(expected)}")


def program_checks(
    listed: frozenset[str], console: str | None, release_tag: str | None
) -> list[Check]:
    """console is what the check program printed, or None when the slice has no runner here."""
    if console is None:
        return failed_program_checks(NOT_RUN)
    try:
        output = parse_output(console)
    except NoResult as error:
        return failed_program_checks(f"{NO_RESULT}: {error}")
    return [
        check_codecs(listed, output),
        check_version(output.version, release_tag),
        check_stream_read(output),
    ]


def failed_program_checks(detail: str) -> list[Check]:
    return [Check(name, False, detail) for name in PROGRAM_CHECKS]


Compiler = Callable[[Slice], Path]
"""Build the check program for a slice and return the binary; raises BuildError when it cannot."""


def program_compiler(toolchain: Toolchain, output: Path, work: Path) -> Compiler:
    """Compile CHECK_PROGRAM against each slice's frameworks delivered under output."""

    def compile_slice(slice_: Slice) -> Path:
        return compile_program(
            slice_,
            toolchain.sdks[slice_.identifier].path,
            output,
            CHECK_PROGRAM,
            work / slice_.identifier / "codec_check",
        )

    return compile_slice


def codec_checks(
    listed: frozenset[str],
    slice_runners: dict[Slice, Runner],
    compile_slice: Compiler,
    release_tag: str | None,
) -> tuple[list[Check], list[str]]:
    """Run the check program on every slice; return its checks and the unverified check names.

    A slice missing from slice_runners fails a release build (release_tag set) and is
    unverified in a dev build (release_tag None). A slice whose program fails to
    compile or run fails its checks; the other slices still run.
    """
    checks: list[Check] = []
    unverified: list[str] = []
    for slice_ in SLICES:
        run = slice_runners.get(slice_)
        if run is None and release_tag is None:
            unverified += [f"{slice_.identifier} {name}" for name in PROGRAM_CHECKS]
            continue
        checks += [
            scoped(slice_.identifier, check)
            for check in slice_checks(listed, slice_, run, compile_slice, release_tag)
        ]
    return checks, unverified


def slice_checks(
    listed: frozenset[str],
    slice_: Slice,
    run: Runner | None,
    compile_slice: Compiler,
    release_tag: str | None,
) -> list[Check]:
    if run is None:
        return program_checks(listed, None, release_tag)
    try:
        console = run(compile_slice(slice_))
    except BuildError as error:
        return failed_program_checks(f"{NO_RESULT}: {' '.join(str(error).split())}")
    return program_checks(listed, console, release_tag)


def fake_program_output(codecs: frozenset[str], version: str) -> str:
    lines = [
        "uavs3d version 1.2.89",
        f"{PROTOCOL} version {version}",
        *(f"{PROTOCOL} stream-read {line}" for line in stream_reads(STREAM_READ_PLAIN)),
        *(f"{PROTOCOL} decoder {name} {name}" for name in sorted(codecs)),
        f"{PROTOCOL} end {len(codecs)}",
    ]
    return "\n".join(lines) + "\n"


FAKE_VERSION = "n9.0.2-kerao.1"
FAKE_DEV_VERSION = "n9.0.2-6-g1976b53c6c"
NO_SUCH_CODEC = "kerao_no_such_codec"


@counterexample
def manifest_lists_a_codec_without_a_decoder(tmp: Path) -> tuple[Check, Check]:
    listed = load_manifest(MANIFEST)
    output = parse_output(fake_program_output(listed, FAKE_VERSION))
    manifest = json.loads(MANIFEST.read_text())
    manifest["codecs"]["video"].append(NO_SUCH_CODEC)
    copy = tmp / MANIFEST.name
    copy.write_text(json.dumps(manifest))
    return check_codecs(listed, output), check_codecs(load_manifest(copy), output)


def reported_version(version: str) -> str:
    return parse_output(fake_program_output(frozenset({"h264"}), version)).version


@counterexample
def release_program_reports_n9_0_1(tmp: Path) -> tuple[Check, Check]:
    return (
        check_version(reported_version(FAKE_VERSION), FAKE_VERSION),
        check_version(reported_version("n9.0.1"), FAKE_VERSION),
    )


@counterexample
def release_slice_without_a_program_run(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    console = fake_program_output(listed, FAKE_VERSION)
    return (
        program_checks(listed, console, FAKE_VERSION)[0],
        program_checks(listed, None, FAKE_VERSION)[0],
    )


@counterexample
def dev_program_reports_n9_0_1(tmp: Path) -> tuple[Check, Check]:
    return (
        check_version(reported_version(FAKE_DEV_VERSION), None),
        check_version(reported_version("n9.0.1-6-g1976b53c6c"), None),
    )


def fake_device_console(program_lines: list[str]) -> str:
    """program_lines framed the way devicectl --console prints them."""
    lines = [
        "Launched application with org.keraolabs.codec-check bundle identifier.",
        "Waiting for the application to terminate…",
        *program_lines,
        "The app terminated with the exit code 0.",
    ]
    return "\n".join(lines) + "\n"


@counterexample
def device_console_without_a_result_line(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    program_lines = fake_program_output(listed, FAKE_VERSION).splitlines()
    complete = fake_device_console(program_lines)
    without_end = fake_device_console(program_lines[:-1])
    return (
        program_checks(listed, complete, FAKE_VERSION)[0],
        program_checks(listed, without_end, FAKE_VERSION)[0],
    )


def fake_compile(tmp: Path) -> Compiler:
    return lambda slice_: tmp / slice_.identifier


def fake_runner(console: str) -> Runner:
    return lambda binary: console


def launch_fails(binary: Path) -> str:
    raise BuildError(f"devicectl could not launch {binary.name}")


def by_name(checks: list[Check], name: str) -> Check:
    """The check called name, or a failing one when checks hold none."""
    return next(
        (check for check in checks if check.name == name),
        Check(name, False, "not among the checks"),
    )


@counterexample
def device_launch_fails_on_first_slice(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    runs = fake_runner(fake_program_output(listed, FAKE_VERSION))
    slice_runners = {slice_: runs for slice_ in SLICES} | {IOS: launch_fails}
    checks, _ = codec_checks(listed, slice_runners, fake_compile(tmp), FAKE_VERSION)
    return (
        by_name(checks, f"{MACOS.identifier} {VERSION_CHECK}"),
        by_name(checks, f"{IOS.identifier} {CODECS_CHECK}"),
    )


@counterexample
def dev_build_without_a_device(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    runs = fake_runner(fake_program_output(listed, FAKE_DEV_VERSION))

    def unverified(slices: tuple[Slice, ...]) -> Check:
        slice_runners = {slice_: runs for slice_ in slices}
        _, names = codec_checks(listed, slice_runners, fake_compile(tmp), None)
        return Check("unverified", not names, ", ".join(names) or "none")

    return unverified(SLICES), unverified((IOS_SIMULATOR, MACOS))


FAKE_PROGRAM = """\
#include <stdio.h>
int main(void) {{ return fputs({console}, stdout) < 0; }}
"""


def fake_program(path: Path, console: str) -> Path:
    """C source of a program that prints console."""
    path.write_text(FAKE_PROGRAM.format(console=json.dumps(console)))
    return path


def fake_delivered_frameworks(
    output: Path, slice_: Slice, work: Path, sources: dict[str, str] | None = None
) -> None:
    """A framework of every library, delivered for slice_ under output, built from
    its C source in sources or else empty."""
    for name in FRAMEWORKS:
        source = work / f"{output.name}-{name}.c"
        source.write_text((sources or {}).get(name, ""))
        framework = delivered_framework(output, slice_, name)
        framework.mkdir(parents=True)
        capture(
            [
                *("xcrun", "--sdk", slice_.sdk, "clang", "-dynamiclib"),
                *("-target", slice_.target),
                *("-install_name", f"@rpath/{name}.framework/{name}"),
                *("-o", str(framework / name), str(source)),
            ]
        )


@counterexample
def output_path_with_a_comma(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    program = fake_program(
        tmp / "program.c", fake_program_output(listed, FAKE_DEV_VERSION)
    )
    sdk_path = Path(capture(["xcrun", "--sdk", MACOS.sdk, "--show-sdk-path"]))
    good = tmp / "good,output"
    fake_delivered_frameworks(good, MACOS, tmp)
    bad = tmp / "bad,output"
    shutil.copytree(good, bad)
    shutil.rmtree(delivered_framework(bad, MACOS, FRAMEWORKS[-1]))

    def codecs(output: Path) -> Check:
        def compile_slice(slice_: Slice) -> Path:
            binary = tmp / "programs" / output.name / "codec_check"
            return compile_program(slice_, sdk_path, output, program, binary)

        checks, _ = codec_checks(listed, {MACOS: run_on_mac}, compile_slice, None)
        return by_name(checks, f"{MACOS.identifier} {CODECS_CHECK}")

    return codecs(good), codecs(bad)


FAKE_RUN_TIMEOUT_SECONDS = 1
SLOW_START_SECONDS = 5


@counterexample
def program_runs_past_the_timeout(tmp: Path) -> tuple[Check, Check]:
    listed = frozenset({"h264"})
    result = tmp / "result.txt"
    result.write_text(fake_program_output(listed, FAKE_DEV_VERSION))

    def run(binary: Path) -> str:
        return run_on_mac(binary, FAKE_RUN_TIMEOUT_SECONDS)

    def codecs(delay_seconds: int) -> Check:
        program = tmp / f"program-{delay_seconds}"
        program.write_text(
            f"#!/bin/sh\nsleep {delay_seconds}\nexec cat {shlex.quote(str(result))}\n"
        )
        program.chmod(0o755)
        checks, _ = codec_checks(listed, {MACOS: run}, lambda slice_: program, None)
        return by_name(checks, f"{MACOS.identifier} {CODECS_CHECK}")

    return codecs(0), codecs(SLOW_START_SECONDS)


STREAM_READ_LINE = f"{PROTOCOL} stream-read"


def stream_read_output(lines: tuple[str, ...]) -> ProgramOutput:
    """The program output with lines as its stream-read values."""
    console = fake_program_output(frozenset({"h264"}), FAKE_DEV_VERSION)
    kept = [
        line for line in console.splitlines() if not line.startswith(STREAM_READ_LINE)
    ]
    kept[2:2] = [f"{STREAM_READ_LINE} {line}" for line in lines]
    return parse_output("\n".join(kept) + "\n")


GOOD_STREAM_READS = stream_reads(STREAM_READ_PLAIN)


@counterexample
def program_without_the_stream_line(tmp: Path) -> tuple[Check, Check]:
    return (
        check_stream_read(stream_read_output(GOOD_STREAM_READS)),
        check_stream_read(stream_read_output(GOOD_STREAM_READS[:1])),
    )


@counterexample
def stream_line_cut_short(tmp: Path) -> tuple[Check, Check]:
    plain, stream = GOOD_STREAM_READS
    return (
        check_stream_read(stream_read_output(GOOD_STREAM_READS)),
        check_stream_read(stream_read_output((plain, stream.rsplit(" ", 3)[0]))),
    )


@counterexample
def plain_read_of_another_build(tmp: Path) -> tuple[Check, Check]:
    other = stream_reads(STREAM_READ_PLAIN.replace("fd09c391", "fd09c392"))
    return (
        check_stream_read(stream_read_output(GOOD_STREAM_READS)),
        check_stream_read(stream_read_output(other)),
    )


MOCK_HEADERS = {
    "libavutil": {
        "avutil.h": """\
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#define AVERROR(e) (-(e))
#define AVERROR_EOF (-0x20464f45)
#define AVERROR_BUG (-0x21475542)
#define AVERROR_INVALIDDATA (-0x41444e49)
const char *av_version_info(void);
""",
        "mem.h": "#include <stddef.h>\nvoid *av_malloc(size_t size);\nvoid av_free(void *ptr);\nvoid av_freep(void *ptr);\n",
        "crc.h": """\
#include <stddef.h>
#include <stdint.h>
typedef uint32_t AVCRC;
#define AV_CRC_32_IEEE_LE 0
const AVCRC *av_crc_get_table(int id);
uint32_t av_crc(const AVCRC *ctx, uint32_t crc, const uint8_t *buffer, size_t length);
""",
    },
    "libavcodec": {
        "avcodec.h": """\
#include <libavutil/avutil.h>
typedef struct AVCodec { const char *name; int id; } AVCodec;
typedef struct AVPacket {
    uint8_t *data;
    int size, stream_index, flags;
    int64_t pts, dts, duration;
} AVPacket;
const AVCodec *av_codec_iterate(void **opaque);
int av_codec_is_decoder(const AVCodec *codec);
const char *avcodec_get_name(int id);
AVPacket *av_packet_alloc(void);
void av_packet_unref(AVPacket *pkt);
void av_packet_free(AVPacket **pkt);
""",
    },
    "libavformat": {
        "avformat.h": """\
#include <libavcodec/avcodec.h>
#define AVSEEK_SIZE 0x10000
#define AVSEEK_FORCE 0x20000
typedef struct AVIOContext { unsigned char *buffer; } AVIOContext;
typedef struct AVFormatContext { AVIOContext *pb; unsigned nb_streams; } AVFormatContext;
AVIOContext *avio_alloc_context(unsigned char *buffer, int buffer_size, int write_flag, void *opaque,
                                int (*read)(void *, uint8_t *, int),
                                int (*write)(void *, const uint8_t *, int),
                                int64_t (*seek)(void *, int64_t, int));
void avio_context_free(AVIOContext **pb);
AVFormatContext *avformat_alloc_context(void);
int avformat_open_input(AVFormatContext **ps, const char *url, const void *fmt, void *options);
void avformat_close_input(AVFormatContext **ps);
int av_read_frame(AVFormatContext *s, AVPacket *pkt);
int av_read_stream_packet(AVFormatContext *s, int stream_index, AVPacket *pkt);
""",
    },
}

MOCK_LIBAVFORMAT = """\
#include <stdlib.h>
#include <string.h>
#include <libavformat/avformat.h>
#include <libavutil/crc.h>
#include <libavutil/mem.h>

#define PACKETS 19

static unsigned delivered;
static int stream_reads;
static uint8_t payload[PACKETS];

const char *av_version_info(void) { return "n9.0.2-kerao.9-dev.1"; }
const AVCodec *av_codec_iterate(void **opaque)
{
    static const AVCodec h264 = { "h264", 27 };
    if (*opaque)
        return NULL;
    *opaque = (void *)&h264;
    return &h264;
}
int av_codec_is_decoder(const AVCodec *codec) { return 1; }
const char *avcodec_get_name(int id) { return "h264"; }
void *av_malloc(size_t size) { return malloc(size); }
void av_free(void *ptr) { free(ptr); }
void av_freep(void *ptr) { free(*(void **)ptr); *(void **)ptr = NULL; }
AVPacket *av_packet_alloc(void) { return calloc(1, sizeof(AVPacket)); }
void av_packet_unref(AVPacket *pkt) { memset(pkt, 0, sizeof(*pkt)); }
void av_packet_free(AVPacket **pkt) { free(*pkt); *pkt = NULL; }
const AVCRC *av_crc_get_table(int id) { static const AVCRC table; return &table; }
uint32_t av_crc(const AVCRC *ctx, uint32_t crc, const uint8_t *buffer, size_t length)
{
    while (length--)
        crc = crc * 31 + *buffer++;
    return crc;
}
AVIOContext *avio_alloc_context(unsigned char *buffer, int buffer_size, int write_flag, void *opaque,
                                int (*read)(void *, uint8_t *, int),
                                int (*write)(void *, const uint8_t *, int),
                                int64_t (*seek)(void *, int64_t, int))
{
    AVIOContext *pb = calloc(1, sizeof(*pb));
    if (pb)
        pb->buffer = buffer;
    return pb;
}
void avio_context_free(AVIOContext **pb) { free(*pb); *pb = NULL; }
AVFormatContext *avformat_alloc_context(void) { return calloc(1, sizeof(AVFormatContext)); }
int avformat_open_input(AVFormatContext **ps, const char *url, const void *fmt, void *options)
{
    delivered = 0;
    stream_reads = 0;
    (*ps)->nb_streams = 2;
    return 0;
}
void avformat_close_input(AVFormatContext **ps) { free(*ps); *ps = NULL; }

static int stream_of(int i) { return i % 3 ? 1 : 0; }

static void deliver(AVPacket *pkt, int i)
{
    payload[i] = i;
    pkt->data = &payload[i];
    pkt->size = 1;
    pkt->stream_index = stream_of(i);
    pkt->pts = pkt->dts = i;
    pkt->duration = 1;
    delivered |= 1u << i;
}

int av_read_frame(AVFormatContext *s, AVPacket *pkt)
{
    for (int i = 0; i < PACKETS; i++)
        if (!(delivered & 1u << i)) {
            deliver(pkt, i);
            return 0;
        }
    return AVERROR_EOF;
}

#ifdef STREAM_READ_LIMIT
int av_read_stream_packet(AVFormatContext *s, int stream_index, AVPacket *pkt)
{
    if (STREAM_READ_LIMIT >= 0 && stream_reads >= STREAM_READ_LIMIT)
        return AVERROR_EOF;
    for (int i = 0; i < PACKETS; i++)
        if (!(delivered & 1u << i) && stream_of(i) == stream_index) {
            stream_reads++;
            deliver(pkt, i);
            return 0;
        }
    return AVERROR_EOF;
}
#endif
"""
EVERY_PACKET = -1


def mock_frameworks(output: Path, slice_: Slice, work: Path, limit: int | None) -> None:
    """Frameworks of every library delivered for slice_ under output, with MOCK_HEADERS,
    whose libavformat is MOCK_LIBAVFORMAT: its stream read returns at most limit
    packets, all of the stream for EVERY_PACKET, and is missing for None."""
    for name in FRAMEWORKS:
        framework = delivered_framework(output, slice_, name)
        (framework / "Headers").mkdir(parents=True)
        for header, text in MOCK_HEADERS.get(name, {}).items():
            (framework / "Headers" / header).write_text(f"#pragma once\n{text}")
    for name in FRAMEWORKS:
        framework = delivered_framework(output, slice_, name)
        source = work / f"{output.name}-{name}.c"
        defines = f"#define STREAM_READ_LIMIT {limit}\n" if limit is not None else ""
        source.write_text(defines + MOCK_LIBAVFORMAT if name == "libavformat" else "")
        capture(
            [
                *("xcrun", "--sdk", slice_.sdk, "clang", "-dynamiclib"),
                *("-target", slice_.target),
                *(
                    arg
                    for other in FRAMEWORKS
                    for arg in ("-F", str(delivered_framework(output, slice_, other).parent))
                ),
                *("-install_name", f"@rpath/{name}.framework/{name}"),
                *("-o", str(framework / name), str(source)),
            ]
        )


def mock_stream_read(tmp: Path, name: str, limit: int | None) -> Check:
    """check_stream_read() of the check program built against mock_frameworks() with
    limit, expecting the plain read of mock_frameworks() with EVERY_PACKET."""
    sdk_path = Path(capture(["xcrun", "--sdk", MACOS.sdk, "--show-sdk-path"]))

    def run(output: Path, limit: int | None) -> ProgramOutput:
        mock_frameworks(output, MACOS, tmp, limit)
        binary = compile_program(
            MACOS, sdk_path, output, CHECK_PROGRAM, tmp / "programs" / output.name / "codec_check"
        )
        return parse_output(run_on_mac(binary))

    plain = run(tmp / f"{name}-plain", EVERY_PACKET).stream_reads[0].removeprefix("plain ")
    try:
        output = run(tmp / name, limit)
    except (BuildError, NoResult) as error:
        return Check(STREAM_READ_CHECK, False, f"{NO_RESULT}: {' '.join(str(error).split())[:200]}")
    return check_stream_read(output, plain)


@counterexample
def stream_read_ends_at_once(tmp: Path) -> tuple[Check, Check]:
    return mock_stream_read(tmp, "good", EVERY_PACKET), mock_stream_read(tmp, "bad", 0)


@counterexample
def stream_read_ends_early(tmp: Path) -> tuple[Check, Check]:
    return mock_stream_read(tmp, "good", EVERY_PACKET), mock_stream_read(tmp, "bad", 3)


@counterexample
def libavformat_without_the_stream_read_symbol(tmp: Path) -> tuple[Check, Check]:
    return mock_stream_read(tmp, "good", EVERY_PACKET), mock_stream_read(tmp, "bad", None)
