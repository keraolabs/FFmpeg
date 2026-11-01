import datetime
import hashlib
import json
from pathlib import Path

import checkout
import ffmpeg
from common import FRAMEWORKS, Check, Slice, counterexample
from framework import FAKE_SLICE, delivered_framework, framework_binary
from toolchain import FAKE_TOOLCHAIN, Toolchain

REPOSITORY = "https://github.com/keraolabs/FFmpeg"
ARTIFACT_FIELDS = (
    "libraries",
    "repository",
    "tag",
    "commit",
    "mode",
    "dirty",
    "built_at",
    "xcode_build",
    "sdks",
    "tools",
    "deps",
    "inputs",
    "frameworks",
    "configure",
    "unverified",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def framework_records(output: Path, slices: tuple[Slice, ...]) -> list[dict]:
    records = []
    for name in FRAMEWORKS:
        binaries = [
            (slice_, framework_binary(delivered_framework(output, slice_, name)))
            for slice_ in slices
        ]
        records.append(
            {
                "name": name,
                "slices": [
                    {
                        "identifier": slice_.identifier,
                        "path": str(binary.relative_to(output)),
                        "sha256": sha256(binary),
                    }
                    for slice_, binary in binaries
                ],
            }
        )
    return records


def artifact_record(
    mode: str,
    source: checkout.Source,
    toolchain: Toolchain,
    configure: dict[str, dict],
    frameworks: list[dict],
) -> dict:
    """configure maps each slice identifier to its configure args and License line."""
    return {
        "libraries": list(FRAMEWORKS),
        "repository": REPOSITORY,
        "tag": checkout.artifact_tag(source, mode),
        "commit": source.commit,
        "mode": mode,
        "dirty": source.dirty,
        "built_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "xcode_build": toolchain.xcode_build,
        "sdks": {
            identifier: {"name": sdk.name, "version": sdk.version}
            for identifier, sdk in toolchain.sdks.items()
        },
        "tools": {},
        "deps": [],
        "inputs": [],
        "frameworks": frameworks,
        "configure": configure,
        "unverified": checkout.skipped_checks(mode),
    }


def write_artifact(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, indent=2) + "\n")


def check_artifact_fields(path: Path) -> Check:
    record = json.loads(path.read_text())
    missing = [field for field in ARTIFACT_FIELDS if field not in record]
    return Check(
        "artifact.json fields",
        not missing,
        f"missing {', '.join(missing)}"
        if missing
        else f"{len(ARTIFACT_FIELDS)} fields",
    )


def fake_artifact_record(tmp: Path) -> dict:
    source = checkout.read_source(checkout.fake_release_checkout(tmp))
    sdk = FAKE_TOOLCHAIN.sdks[FAKE_SLICE.identifier]
    configure = {
        FAKE_SLICE.identifier: {
            "args": ffmpeg.configure_args(FAKE_SLICE, sdk.path),
            "license": ffmpeg.EXPECTED_LICENSE,
        }
    }
    return artifact_record("release", source, FAKE_TOOLCHAIN, configure, [])


@counterexample
def artifact_without_required_field(tmp: Path) -> tuple[Check, Check]:
    record = fake_artifact_record(tmp)
    good = tmp / "good.json"
    write_artifact(good, record)
    bad = tmp / "bad.json"
    write_artifact(bad, {key: value for key, value in record.items() if key != "tag"})
    return check_artifact_fields(good), check_artifact_fields(bad)
