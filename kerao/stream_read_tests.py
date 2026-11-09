#!/usr/bin/env python3
#
# This file is part of FFmpeg.
#
# FFmpeg is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# FFmpeg is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with FFmpeg; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""The fate-stream-read tests and their refs.

python3 kerao/stream_read_tests.py fate
    Write the fate-stream-read block of tests/fate/libavformat.mak.
python3 kerao/stream_read_tests.py refs <fixtures dir>
    Make the media from the fixtures directory with
    kerao/stream_read_fixtures.py and build BASELINE_COMMIT of this checkout,
    both in a temporary directory, write tests/ref/fate/stream-read-* from
    what libavformat/tests/stream_read built against it prints, and record how
    in kerao/stream_read_refs.txt. The commit and tree there pin the source;
    libavformat.a and stream_read differ in every build, and their SHA-256
    identify the build that wrote the refs, and the SHA-256 of each media
    file pins what it read.

A ref is the output of a plain schedule, which reads with av_read_frame()
alone, on BASELINE_COMMIT. The tests compare schedules that use
av_read_stream_packet() with them.
"""

import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import stream_read_fixtures

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "tests" / "ref" / "fate"
MAK = ROOT / "tests" / "fate" / "libavformat.mak"
PROVENANCE = ROOT / "kerao" / "stream_read_refs.txt"
TEST_PROGRAM = ROOT / "libavformat" / "tests" / "stream_read.c"

BASELINE_COMMIT = "ae49c6ac4a2409553ca0f9a00f9e252cbce632a0"
BASELINE_TREE = "b4a2cbf458f4728c4cf3abb745ed97c625a87732"
CONFIGURE = [
    "--disable-autodetect", "--disable-programs", "--disable-doc", "--disable-avdevice",
    "--disable-avfilter", "--disable-swscale", "--enable-pthreads", "--disable-network",
    "--disable-everything", "--enable-decoders", "--enable-demuxer=mov,matroska",
    "--enable-protocol=file",
]
LIBRARIES = ("avformat", "avcodec", "swresample", "avutil")

MOV = "MOV_DEMUXER AC3_PARSER FILE_PROTOCOL"
MATROSKA = "MATROSKA_DEMUXER FILE_PROTOCOL"

# name, file, schedule and options, ref, components
TESTS = [
    ("interleaved-plain", "interleaved.mp4", "p", "interleaved", MOV),
    ("interleaved-video", "interleaved.mp4", "t0/p", "interleaved", MOV),
    ("interleaved-audio", "interleaved.mp4", "t1/p", "interleaved", MOV),
    ("interleaved-alternate", "interleaved.mp4", "t1+p", "interleaved", MOV),
    ("interleaved-both", "interleaved.mp4", "t1+t0", "interleaved", MOV),
    ("interleaved-noinfo", "interleaved.mp4", "t1+t0+p noinfo", "interleaved-noinfo", MOV),
    ("interleaved-eagain", "interleaved.mp4", "t1/t0 eagain=20000 ends", "interleaved-eagain", MOV),
    ("audio-late", "audio-late.mp4", "t1+p", "audio-late", MOV),
    ("audio-late-first", "audio-late.mp4", "t1/p", "audio-late", MOV),
    ("audio-early-end", "audio-early-end.mp4", "t1/p", "audio-early-end", MOV),
    ("audio-early-end-alternate", "audio-early-end.mp4", "t1+p", "audio-early-end", MOV),
    ("audio-early-end-past-end", "audio-early-end.mp4", "s7000/t1+p", "audio-early-end-s7000", MOV),
    ("audio-early-end-seek-back", "audio-early-end.mp4", "t1/p:20/s0/t1+p", "audio-early-end-s0", MOV),
    ("audio-early-end-eagain", "audio-early-end.mp4", "t1/p/t1 eagain=45000 ends", "audio-early-end-eagain", MOV),
    ("audio-gap", "audio-gap.mp4", "t1+p", "audio-gap", MOV),
    ("b-frames", "b-frames.mp4", "t0+p", "b-frames", MOV),
    ("b-frames-audio", "b-frames.mp4", "t1/p", "b-frames", MOV),
    ("parser-ac3", "parser-streams.mp4", "t1/p", "parser-streams", MOV),
    ("parser-eac3", "parser-streams.mp4", "t2/t1/p", "parser-streams", MOV),
    ("parser-alternate", "parser-streams.mp4", "t2+t1+p", "parser-streams", MOV),
    ("parser-video", "parser-streams.mp4", "t0/p", "parser-streams", MOV),
    ("parser-noinfo", "parser-streams.mp4", "t2+p noinfo", "parser-streams-noinfo", MOV),
    ("parser-queued", "parser-streams.mp4", "p+t2 noinfo", "parser-streams-noinfo", MOV),
    ("parser-queued-info", "parser-streams.mp4", "p+t2", "parser-streams", MOV),
    ("frag-indexed", "frag-indexed.mp4", "t1+p", "frag-indexed", MOV),
    ("frag-sidx-video", "frag-sidx.mp4", "t0/p", "frag-sidx", MOV),
    ("frag-sidx-alternate", "frag-sidx.mp4", "t1+p", "frag-sidx", MOV),
    ("frag-sidx-both", "frag-sidx.mp4", "t0+t1", "frag-sidx", MOV),
    ("frag-sidx-seek", "frag-sidx.mp4", "t0/s3000/t0+p", "frag-sidx-s3000", MOV),
    ("frag-sidx-hole-plain", "frag-sidx.mp4", "s9000/p:5/s3000/p noinfo", "frag-sidx-hole", MOV),
    ("frag-sidx-hole-video", "frag-sidx.mp4", "s9000/p:5/s3000/t0/p noinfo", "frag-sidx-hole", MOV),
    ("frag-sidx-hole-audio", "frag-sidx.mp4", "s9000/p:5/s3000/t1/p noinfo", "frag-sidx-hole", MOV),
    ("frag-sidx-hole-alternate", "frag-sidx.mp4", "s9000/p:5/s3000/t0+p noinfo", "frag-sidx-hole", MOV),
    ("frag-sidx-hole-both", "frag-sidx.mp4", "s9000/t0:5/s3000/t1+t0 noinfo", "frag-sidx-hole", MOV),
    ("frag-sidx-ioerror", "frag-sidx.mp4", "t0+p ioerror=40000 ends", "frag-sidx-ioerror", MOV),
    ("frag-sidx-audio-late", "frag-sidx-audio-late.mp4", "t1+p", "frag-sidx-audio-late", MOV),
    ("frag-sidx-audio-late-first", "frag-sidx-audio-late.mp4", "t1/p", "frag-sidx-audio-late", MOV),
    ("frag-sidx-audio-early-end", "frag-sidx-audio-early-end.mp4", "t1/p", "frag-sidx-audio-early-end", MOV),
    ("frag-sidx-audio-early-end-alternate", "frag-sidx-audio-early-end.mp4", "t1+p", "frag-sidx-audio-early-end", MOV),
    ("mixed-lazy-video", "mixed-lazy.mp4", "t0/p", "mixed-lazy", MOV),
    ("mixed-lazy-alternate", "mixed-lazy.mp4", "t0+p", "mixed-lazy", MOV),
    ("faststart", "faststart.mp4", "t1+p", "faststart", MOV),
    ("cover-open", "cover.mp4", "t0/p noinfo", "cover-noinfo", MOV),
    ("cover-open-picture", "cover.mp4", "t1/p noinfo", "cover-noinfo", MOV),
    ("cover-seek", "cover.mp4", "s0/t0/p", "cover-s0", MOV),
    ("cover-seek-alternate", "cover.mp4", "s0/t0+t1+p", "cover-s0", MOV),
    ("einval", "interleaved.mp4", "t1+p einval", "interleaved", MOV),
    ("enosys-genpts", "interleaved.mp4", "p genpts enosys", "interleaved-genpts", MOV),
    ("enosys-ignidx", "interleaved.mp4", "p ignidx enosys", "interleaved-ignidx", MOV),
    ("enosys-wallclock", "interleaved.mp4", "p wallclock enosys ends", "interleaved-ends", MOV),
    ("enosys-nonseekable", "frag-indexed.mp4", "p nonseekable enosys", "frag-indexed-nonseekable", MOV),
    ("enosys-encrypted", "encrypted.mp4", "p enosys", "encrypted", MOV),
    ("enosys-matroska", "enosys.mkv", "p enosys", "enosys", MATROSKA),
]

# ref: file and plain schedule that BASELINE_COMMIT reads for it
PLAIN = {
    "interleaved": ("interleaved.mp4", "p"),
    "interleaved-noinfo": ("interleaved.mp4", "p noinfo"),
    "interleaved-eagain": ("interleaved.mp4", "p eagain=20000 ends"),
    "audio-late": ("audio-late.mp4", "p"),
    "audio-early-end": ("audio-early-end.mp4", "p"),
    "audio-early-end-s7000": ("audio-early-end.mp4", "s7000/p"),
    "audio-early-end-s0": ("audio-early-end.mp4", "s0/p"),
    "audio-early-end-eagain": ("audio-early-end.mp4", "p eagain=45000 ends"),
    "audio-gap": ("audio-gap.mp4", "p"),
    "b-frames": ("b-frames.mp4", "p"),
    "parser-streams": ("parser-streams.mp4", "p"),
    "parser-streams-noinfo": ("parser-streams.mp4", "p noinfo"),
    "frag-indexed": ("frag-indexed.mp4", "p"),
    "frag-sidx": ("frag-sidx.mp4", "p"),
    "frag-sidx-s3000": ("frag-sidx.mp4", "s3000/p"),
    "frag-sidx-hole": ("frag-sidx.mp4", "s9000/p:5/s3000/p noinfo"),
    "frag-sidx-ioerror": ("frag-sidx.mp4", "p ioerror=40000 ends"),
    "frag-sidx-audio-late": ("frag-sidx-audio-late.mp4", "p"),
    "frag-sidx-audio-early-end": ("frag-sidx-audio-early-end.mp4", "p"),
    "mixed-lazy": ("mixed-lazy.mp4", "p"),
    "faststart": ("faststart.mp4", "p"),
    "cover-noinfo": ("cover.mp4", "p noinfo"),
    "cover-s0": ("cover.mp4", "s0/p"),
    "interleaved-genpts": ("interleaved.mp4", "p genpts"),
    "interleaved-ignidx": ("interleaved.mp4", "p ignidx"),
    "interleaved-ends": ("interleaved.mp4", "p wallclock ends"),
    "frag-indexed-nonseekable": ("frag-indexed.mp4", "p nonseekable"),
    "encrypted": ("encrypted.mp4", "p"),
    "enosys": ("enosys.mkv", "p"),
}

def fate_block():
    lines = [
        "# fate-stream-read-<name> reads stream-read/<file> of the samples with libavformat/tests/stream_read;",
        "# kerao/stream_read_tests.py writes this block and the refs.",
        "",
    ]
    for name, file, args, ref, components in TESTS:
        target = f"fate-stream-read-{name}"
        lines += [
            f"FATE_STREAM_READ-$(call ALLYES, {components}) += {target}",
            f"{target}: libavformat/tests/stream_read$(EXESUF)",
            f"{target}: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/{file} {args}",
            f"{target}: REF = $(SRC_PATH)/tests/ref/fate/stream-read-{ref}",
        ]
    lines += [
        "",
        "FATE_STREAM_READ += $(FATE_STREAM_READ-yes)",
        "FATE_EXTERN-$(CONFIG_AVFORMAT) += $(FATE_STREAM_READ)",
        "fate-stream-read: $(FATE_STREAM_READ)",
    ]
    return "\n".join(lines) + "\n"


def write_fate():
    text = MAK.read_text()
    first = "# fate-stream-read-<name> reads"
    last = "fate-stream-read: $(FATE_STREAM_READ)\n"
    start, end = text.index(first), text.index(last) + len(last)
    MAK.write_text(text[:start] + fate_block() + text[end:])


def run(command, **kwargs):
    return subprocess.run(command, check=True, capture_output=True, text=True, **kwargs).stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_baseline(work):
    """BASELINE_COMMIT of this checkout built under work, and stream_read built against it."""
    tree = run(["git", "-C", str(ROOT), "rev-parse", "--verify", f"{BASELINE_COMMIT}^{{tree}}"]).strip()
    if tree != BASELINE_TREE:
        sys.exit(f"{BASELINE_COMMIT} has tree {tree} here, not {BASELINE_TREE}: refusing to write refs")
    source, build = work / "source", work / "build"
    source.mkdir()
    build.mkdir()
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", BASELINE_COMMIT],
                             check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
    configure = [str(source / "configure"), *CONFIGURE]
    run(configure, cwd=build)
    run(["make", f"-j{os.cpu_count()}"], cwd=build)
    config = (build / "ffbuild" / "config.mak").read_text()
    extralibs = [flag for name in LIBRARIES
                 for line in config.splitlines() if line.startswith(f"EXTRALIBS-{name}=")
                 for flag in shlex.split(line.split("=", 1)[1])]
    binary = work / "stream_read"
    compile_command = [
        "cc", "-O2", f"-I{source}", f"-I{build}",
        "-Dav_read_stream_packet(s,i,p)=AVERROR(ENOSYS)",
        str(TEST_PROGRAM), "-o", str(binary),
        *(str(build / f"lib{name}" / f"lib{name}.a") for name in LIBRARIES),
        *extralibs,
    ]
    run(compile_command)
    return {
        "binary": binary,
        "libavformat": build / "libavformat" / "libavformat.a",
        "configure": configure,
        "compile": compile_command,
        "work": work,
    }


def plain(binary, media, file, args):
    return run([str(binary), str(media / file), *args.split()])


def write_refs(fixtures):
    with tempfile.TemporaryDirectory(prefix="stream-read-baseline-") as tmp:
        samples = Path(tmp) / "samples"
        stream_read_fixtures.make(fixtures, samples)
        media = samples / "stream-read"
        baseline = build_baseline(Path(tmp))
        refs = sorted({ref for _, _, _, ref, _ in TESTS})
        for ref in refs:
            (REFS / f"stream-read-{ref}").write_text(plain(baseline["binary"], media, *PLAIN[ref]))
        work = str(baseline["work"])
        record = [
            f"baseline {BASELINE_COMMIT}",
            f"tree {BASELINE_TREE}",
            "source git archive " + BASELINE_COMMIT,
            "configure " + " ".join(baseline["configure"]).replace(work, "<work>"),
            "compile " + " ".join(baseline["compile"]).replace(work, "<work>").replace(str(ROOT), "<checkout>"),
            "cc " + run(["cc", "--version"]).splitlines()[0],
            f"sha256 {sha256(baseline['libavformat'])} libavformat.a",
            f"sha256 {sha256(baseline['binary'])} stream_read",
            *(f"sha256 {sha256(path)} stream-read/{path.name}" for path in sorted(media.iterdir())),
            *(f"sha256 {sha256(REFS / f'stream-read-{ref}')} tests/ref/fate/stream-read-{ref}" for ref in refs),
        ]
        PROVENANCE.write_text("\n".join(record) + "\n")


def main():
    if sys.argv[1:] == ["fate"]:
        write_fate()
    elif sys.argv[1:2] == ["refs"] and len(sys.argv) == 3:
        write_refs(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
