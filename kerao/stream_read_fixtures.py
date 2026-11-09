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

"""Make the media of the fate-stream-read tests.

python3 kerao/stream_read_fixtures.py <fixtures dir> <samples dir>

The fixtures directory holds quiet.mp4, H.264 640x360 24 fps and AAC-LC
stereo 48 kHz, 10 s, with its moov after its mdat, and cover-art-audio.mp4,
AAC with an attached picture. Every file but cover.mp4 comes from quiet.mp4,
remuxed or partly re-encoded with the ffmpeg on PATH, and some then have
their boxes edited here. cover.mp4 is a copy of cover-art-audio.mp4. The
files go to stream-read/ of the samples directory, which FATE reads with
SAMPLES=<samples dir>.
"""

import shutil
import struct
import subprocess
import sys
from pathlib import Path

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"moof", b"traf", b"mvex", b"edts", b"dinf"}
ENCRYPTION_KEY = "76a6c65c5ea762046bd749a2e632ccbb"
ENCRYPTION_KID = "a7e61c373e219033c21091fa607bf3b8"


class Box:
    def __init__(self, kind, payload=b"", children=None):
        self.kind = kind
        self.payload = payload
        self.children = children

    def serialize(self):
        body = b"".join(c.serialize() for c in self.children) if self.children is not None else self.payload
        return struct.pack(">I4s", 8 + len(body), self.kind) + body

    def find(self, *path):
        if not path:
            return [self]
        return [box for child in self.children or [] if child.kind == path[0] for box in child.find(*path[1:])]


def parse(data):
    boxes, offset = [], 0
    while offset + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[offset : offset + 8])
        if size < 8:
            raise ValueError(f"box {kind} at {offset} has size {size}")
        body = data[offset + 8 : offset + size]
        boxes.append(Box(kind, children=parse(body)) if kind in CONTAINERS else Box(kind, body))
        offset += size
    return boxes


def write(path, boxes):
    path.write_bytes(b"".join(box.serialize() for box in boxes))


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def table(stbl, kind):
    return stbl.find(kind)[0]


def read_stsz(box):
    default, count = struct.unpack(">II", box.payload[4:12])
    if default:
        return [default] * count
    return list(struct.unpack(f">{count}I", box.payload[12 : 12 + 4 * count]))


def write_stsz(box, sizes):
    box.payload = box.payload[:4] + struct.pack(f">II{len(sizes)}I", 0, len(sizes), *sizes)


def read_stts(box):
    count = struct.unpack(">I", box.payload[4:8])[0]
    runs = struct.unpack(f">{2 * count}I", box.payload[8 : 8 + 8 * count])
    return [delta for n, delta in zip(runs[::2], runs[1::2]) for _ in range(n)]


def write_stts(box, durations):
    runs = []
    for delta in durations:
        if runs and runs[-1][1] == delta:
            runs[-1][0] += 1
        else:
            runs.append([1, delta])
    box.payload = box.payload[:4] + struct.pack(">I", len(runs)) + b"".join(struct.pack(">II", *run) for run in runs)


def read_stsc(box, chunks):
    """Samples per chunk for each of chunks chunks."""
    count = struct.unpack(">I", box.payload[4:8])[0]
    entries = [struct.unpack(">III", box.payload[8 + 12 * i : 20 + 12 * i]) for i in range(count)]
    per_chunk = []
    for i, (first, samples, _) in enumerate(entries):
        last = entries[i + 1][0] if i + 1 < count else chunks + 1
        per_chunk += [samples] * (last - first)
    return per_chunk


def write_stsc(box, per_chunk):
    entries = [struct.pack(">III", i + 1, n, 1) for i, n in enumerate(per_chunk)]
    box.payload = box.payload[:4] + struct.pack(">I", len(entries)) + b"".join(entries)


def chunk_count(stbl):
    return struct.unpack(">I", table(stbl, b"stco").payload[4:8])[0]


def regroup(stbl, group):
    """Replace stbl's samples, chunk by chunk, with group(sizes, durations) -> (sizes, durations)."""
    sizes, durations = read_stsz(table(stbl, b"stsz")), read_stts(table(stbl, b"stts"))
    per_chunk = read_stsc(table(stbl, b"stsc"), chunk_count(stbl))
    new_sizes, new_durations, new_per_chunk, first = [], [], [], 0
    for n in per_chunk:
        s, d = group(sizes[first : first + n], durations[first : first + n])
        new_sizes += s
        new_durations += d
        new_per_chunk.append(len(s))
        first += n
    return new_sizes, new_durations, new_per_chunk


def pairs(sizes, durations):
    """Two frames per sample."""
    s = [sum(sizes[i : i + 2]) for i in range(0, len(sizes), 2)]
    d = [sum(durations[i : i + 2]) for i in range(0, len(durations), 2)]
    return s, d


def split(sizes, durations):
    """Each odd sample ends halfway through its frame; the next one carries the rest."""
    s = list(sizes)
    for i in range(0, len(s) - 1, 2):
        moved = s[i] // 2
        s[i] -= moved
        s[i + 1] += moved
    return s, list(durations)


def media_scale(trak):
    mdhd = trak.find(b"mdia", b"mdhd")[0].payload
    return struct.unpack(">I", mdhd[12:16] if mdhd[0] == 0 else mdhd[20:24])[0]


def rechunk(data, chunk_seconds):
    """data with every track's samples in chunks of chunk_seconds, interleaved by time, moov last."""
    boxes = parse(data)
    moov = next(box for box in boxes if box.kind == b"moov")
    chunks = []
    for trak in moov.find(b"trak"):
        stbl = trak.find(b"mdia", b"minf", b"stbl")[0]
        sizes, durations = read_stsz(table(stbl, b"stsz")), read_stts(table(stbl, b"stts"))
        stco = table(stbl, b"stco")
        count = struct.unpack(">I", stco.payload[4:8])[0]
        offsets = struct.unpack(f">{count}I", stco.payload[8 : 8 + 4 * count])
        payloads, first = [], 0
        for offset, n in zip(offsets, read_stsc(table(stbl, b"stsc"), count)):
            for size in sizes[first : first + n]:
                payloads.append(data[offset : offset + size])
                offset += size
            first += n
        scale, dts, start, bounds = media_scale(trak), 0, 0, []
        for i, duration in enumerate(durations):
            if dts >= (len(bounds) + 1) * chunk_seconds * scale:
                bounds.append((start, i))
                start = i
            dts += duration
        bounds.append((start, len(durations)))
        chunks += [(sum(durations[:a]) / scale, stco, stbl, payloads[a:b], k) for k, (a, b) in enumerate(bounds)]
    ftyp = next(box for box in boxes if box.kind == b"ftyp")
    offset = len(ftyp.serialize()) + 8
    body, placed = [], {}
    for t, stco, stbl, payloads, k in sorted(chunks, key=lambda c: c[0]):
        placed.setdefault(id(stco), (stco, stbl, []))[2].append((k, offset, len(payloads)))
        body += payloads
        offset += sum(len(p) for p in payloads)
    for stco, stbl, entries in placed.values():
        entries.sort()
        stco.payload = stco.payload[:4] + struct.pack(f">I{len(entries)}I", len(entries), *(o for _, o, _ in entries))
        write_stsc(table(stbl, b"stsc"), [n for _, _, n in entries])
    return [ftyp, Box(b"mdat", b"".join(body)), moov]


def parser_streams(source, out):
    """AC-3 with two frames per sample and E-AC-3 with frames across samples, each ending in a partial frame."""
    boxes = rechunk(source.read_bytes(), 0.5)
    moov = next(box for box in boxes if box.kind == b"moov")
    sounds = [trak for trak in moov.find(b"trak") if trak.find(b"mdia", b"hdlr")[0].payload[8:12] == b"soun"]
    for trak, group in zip(sounds, (pairs, split)):
        stbl = trak.find(b"mdia", b"minf", b"stbl")[0]
        sizes, durations, per_chunk = regroup(stbl, group)
        sizes[-1] -= 100
        write_stsz(table(stbl, b"stsz"), sizes)
        write_stts(table(stbl, b"stts"), durations)
        write_stsc(table(stbl, b"stsc"), per_chunk)
    write(out, boxes)


def read_sidx(box):
    version = box.payload[0]
    head = 12 + (8 if version == 0 else 16)
    reference_id, timescale = struct.unpack(">II", box.payload[4:12])
    if version == 0:
        earliest, first_offset = struct.unpack(">II", box.payload[12:20])
    else:
        earliest, first_offset = struct.unpack(">QQ", box.payload[12:28])
    count = struct.unpack(">H", box.payload[head + 2 : head + 4])[0]
    refs = [list(struct.unpack(">III", box.payload[head + 4 + 12 * i : head + 16 + 12 * i])) for i in range(count)]
    return dict(version=version, flags=box.payload[1:4], reference_id=reference_id, timescale=timescale,
                earliest=earliest, first_offset=first_offset, refs=refs)


def write_sidx(box, sidx):
    fields = struct.pack(">II", sidx["earliest"], sidx["first_offset"]) if sidx["version"] == 0 else struct.pack(">QQ", sidx["earliest"], sidx["first_offset"])
    box.payload = (bytes([sidx["version"]]) + sidx["flags"] + struct.pack(">II", sidx["reference_id"], sidx["timescale"])
                   + fields + struct.pack(">HH", 0, len(sidx["refs"])) + b"".join(struct.pack(">III", *ref) for ref in sidx["refs"]))


def moov_duration(moov, track_id, timescale):
    for trak in moov.find(b"trak"):
        tkhd = trak.find(b"tkhd")[0].payload
        if struct.unpack(">I", tkhd[12:16] if tkhd[0] == 0 else tkhd[20:24])[0] != track_id:
            continue
        stbl = trak.find(b"mdia", b"minf", b"stbl")[0]
        mdhd = trak.find(b"mdia", b"mdhd")[0].payload
        track_scale = struct.unpack(">I", mdhd[12:16] if mdhd[0] == 0 else mdhd[20:24])[0]
        return sum(read_stts(table(stbl, b"stts"))) * timescale // track_scale
    raise ValueError(f"no track {track_id}")


def mixed_lazy(source, out):
    """Move the global sidx boxes in front of the moov's mdat and index that mdat as their first segment."""
    boxes = [box for box in parse(source.read_bytes()) if box.kind != b"mfra"]
    kinds = [box.kind for box in boxes]
    moov_at, mdat_at = kinds.index(b"moov"), kinds.index(b"mdat")
    sidxs = [box for box in boxes if box.kind == b"sidx"]
    mdat = boxes[mdat_at]
    moov = boxes[moov_at]
    for box in sidxs:
        sidx = read_sidx(box)
        sap = 1 << 31 | 1 << 28
        sidx["refs"].insert(0, [len(mdat.serialize()), moov_duration(moov, sidx["reference_id"], sidx["timescale"]), sap])
        sidx["earliest"] = 0
        write_sidx(box, sidx)
    for i, box in enumerate(sidxs):
        sidx = read_sidx(box)
        sidx["first_offset"] = sum(len(b.serialize()) for b in sidxs[i + 1 :])
        write_sidx(box, sidx)
    moved = sum(len(box.serialize()) for box in sidxs)
    for stco in moov.find(b"trak", b"mdia", b"minf", b"stbl", b"stco"):
        count = struct.unpack(">I", stco.payload[4:8])[0]
        offsets = struct.unpack(f">{count}I", stco.payload[8 : 8 + 4 * count])
        stco.payload = stco.payload[:8] + struct.pack(f">{count}I", *(o + moved for o in offsets))
    rest = [box for box in boxes[mdat_at + 1 :] if box.kind != b"sidx"]
    write(out, boxes[: moov_at + 1] + sidxs + [mdat] + rest)


def single_sidx(source, out):
    """Keep only the first sidx, which indexes every fragment, and drop mfra.

    ffmpeg's global sidx for a track absent from some fragments does not end at
    the end of the file, so libavformat would read every fragment at open."""
    boxes = [box for box in parse(source.read_bytes()) if box.kind != b"mfra"]
    first = next(i for i, box in enumerate(boxes) if box.kind == b"sidx")
    sidx = read_sidx(boxes[first])
    sidx["first_offset"] = 0
    write_sidx(boxes[first], sidx)
    write(out, [box for i, box in enumerate(boxes) if box.kind != b"sidx" or i == first])


def make(fixtures, samples):
    """Write the media to stream-read/ of samples."""
    quiet = str(fixtures / "quiet.mp4")
    out = samples / "stream-read"
    tmp = out / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    copy = ["-c", "copy"]
    lazy = ["-movflags", "frag_keyframe+empty_moov+default_base_moof+global_sidx"]
    shutil.copyfile(fixtures / "cover-art-audio.mp4", out / "cover.mp4")

    ffmpeg("-i", quiet, "-t", "4", *copy, str(out / "interleaved.mp4"))
    ffmpeg("-i", quiet, "-itsoffset", "5", "-i", quiet, "-map", "0:v", "-map", "1:a", "-t", "10", *copy, str(out / "audio-late.mp4"))
    ffmpeg("-i", quiet, "-t", "5", "-i", quiet, "-map", "0:v", "-map", "1:a", *copy, str(out / "audio-early-end.mp4"))
    ffmpeg("-i", quiet, "-map", "0", *copy, "-bsf:a", "noise=drop=between(pts*tb\\,2.5\\,7.5)", str(out / "audio-gap.mp4"))
    ffmpeg("-i", quiet, "-t", "4", "-map", "0", "-c:v", "libx264", "-bf", "3", "-g", "24", "-preset", "veryfast",
           "-crf", "35", "-c:a", "copy", str(out / "b-frames.mp4"))
    ffmpeg("-i", quiet, "-t", "4", "-map", "0:v", "-map", "0:a", "-map", "0:a", "-c:v", "copy",
           "-c:a:0", "ac3", "-b:a:0", "96k", "-c:a:1", "eac3", "-b:a:1", "96k", str(tmp / "ac3-eac3.mp4"))
    parser_streams(tmp / "ac3-eac3.mp4", out / "parser-streams.mp4")

    ffmpeg("-i", quiet, "-t", "6", *copy, "-movflags", "frag_keyframe+empty_moov+default_base_moof", str(out / "frag-indexed.mp4"))
    ffmpeg("-i", quiet, *copy, *lazy, str(out / "frag-sidx.mp4"))
    for name in ("audio-early-end", "audio-late"):
        ffmpeg("-i", str(out / f"{name}.mp4"), *copy, *lazy, str(tmp / f"{name}.mp4"))
        single_sidx(tmp / f"{name}.mp4", out / f"frag-sidx-{name}.mp4")
    ffmpeg("-i", quiet, *copy, "-movflags", "frag_keyframe+global_sidx+default_base_moof", str(tmp / "mixed-sidx.mp4"))
    mixed_lazy(tmp / "mixed-sidx.mp4", out / "mixed-lazy.mp4")

    ffmpeg("-i", quiet, "-t", "4", *copy, "-movflags", "faststart", str(out / "faststart.mp4"))

    ffmpeg("-i", quiet, "-t", "2", *copy, "-fflags", "+bitexact", str(out / "enosys.mkv"))
    ffmpeg("-i", quiet, "-t", "2", *copy, "-fflags", "+bitexact",
           "-encryption_scheme", "cenc-aes-ctr", "-encryption_key", ENCRYPTION_KEY,
           "-encryption_kid", ENCRYPTION_KID, str(out / "encrypted.mp4"))
    for path in tmp.iterdir():
        path.unlink()
    tmp.rmdir()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    make(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
