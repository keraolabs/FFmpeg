import datetime
import hashlib
import json
from pathlib import Path

import checkout
import ffmpeg
from common import FRAMEWORKS, MAX_LISTED_LINES, SLICES, Check, Slice, counterexample
from deps import DEPS
from framework import delivered_framework, framework_binary
from toolchain import FAKE_TOOLCHAIN, TOOLS, Toolchain

REPOSITORY = "https://github.com/keraolabs/FFmpeg"
DEP_FIELDS = ("name", "repository", "tag", "commit")
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
            (
                slice_,
                framework_binary(
                    delivered_framework(output, slice_, name), slice_.layout
                ),
            )
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
        "tools": toolchain.tools,
        "deps": [{field: getattr(dep, field) for field in DEP_FIELDS} for dep in DEPS],
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


def check_artifact_slices(path: Path) -> Check:
    record = json.loads(path.read_text())
    expected = sorted(slice_.identifier for slice_ in SLICES)
    sdks = record.get("sdks", {})
    problems = [] if sorted(sdks) == expected else [f"sdks: {', '.join(sdks)}"]
    problems += [
        f"sdks {identifier} has no {key}"
        for identifier, sdk in sdks.items()
        for key in ("name", "version")
        if not sdk.get(key)
    ]
    frameworks = record.get("frameworks", [])
    names = [framework.get("name") for framework in frameworks]
    if names != list(FRAMEWORKS):
        problems.append(f"frameworks: {', '.join(map(str, names))}")
    for framework in frameworks:
        slices = framework.get("slices", [])
        found = sorted(str(entry.get("identifier")) for entry in slices)
        if found != expected:
            problems.append(f"{framework.get('name')} slices: {', '.join(found)}")
        problems += [
            f"{framework.get('name')} {entry.get('identifier')} has no {key}"
            for entry in slices
            for key in ("path", "sha256")
            if not entry.get(key)
        ]
    return Check(
        "artifact.json slices",
        not problems,
        "; ".join(problems[:MAX_LISTED_LINES])
        or f"{len(sdks)} sdks, {len(frameworks)} frameworks with {', '.join(expected)}",
    )


def check_artifact_deps(path: Path) -> Check:
    record = json.loads(path.read_text())
    entries = record.get("deps", [])
    names = [entry.get("name") for entry in entries]
    expected = [dep.name for dep in DEPS]
    problems = [] if names == expected else [f"deps: {', '.join(map(str, names))}"]
    problems += [
        f"deps {entry.get('name')} has no {field}"
        for entry in entries
        for field in DEP_FIELDS
        if not entry.get(field)
    ]
    tools = record.get("tools", {})
    problems += [f"tools has no {name}" for name in TOOLS if not tools.get(name)]
    return Check(
        "artifact.json deps and tools",
        not problems,
        "; ".join(problems[:MAX_LISTED_LINES])
        or ", ".join(
            [
                *(f"{entry['name']} {entry['tag']}" for entry in entries),
                *(f"{name} {tools[name]}" for name in TOOLS),
            ]
        ),
    )


FAKE_SHA256 = "0" * 64


def fake_artifact_record(tmp: Path) -> dict:
    source = checkout.read_source(checkout.fake_release_checkout(tmp))
    configure = {
        slice_.identifier: {
            "args": ffmpeg.configure_args(
                slice_, FAKE_TOOLCHAIN.sdks[slice_.identifier].path
            ),
            "license": ffmpeg.EXPECTED_LICENSE,
        }
        for slice_ in SLICES
    }
    frameworks = [
        {
            "name": name,
            "slices": [
                {
                    "identifier": slice_.identifier,
                    "path": f"{name}.xcframework/{slice_.identifier}/{name}.framework/{name}",
                    "sha256": FAKE_SHA256,
                }
                for slice_ in SLICES
            ],
        }
        for name in FRAMEWORKS
    ]
    return artifact_record("release", source, FAKE_TOOLCHAIN, configure, frameworks)


@counterexample
def artifact_without_required_field(tmp: Path) -> tuple[Check, Check]:
    record = fake_artifact_record(tmp)
    good = tmp / "good.json"
    write_artifact(good, record)
    bad = tmp / "bad.json"
    write_artifact(bad, {key: value for key, value in record.items() if key != "tag"})
    return check_artifact_fields(good), check_artifact_fields(bad)


@counterexample
def artifact_framework_without_a_slice(tmp: Path) -> tuple[Check, Check]:
    record = fake_artifact_record(tmp)
    good = tmp / "good.json"
    write_artifact(good, record)
    first, *rest = record["frameworks"]
    bad = tmp / "bad.json"
    write_artifact(
        bad,
        {
            **record,
            "frameworks": [{**first, "slices": first["slices"][:-1]}, *rest],
        },
    )
    return check_artifact_slices(good), check_artifact_slices(bad)


@counterexample
def artifact_dep_without_commit(tmp: Path) -> tuple[Check, Check]:
    record = fake_artifact_record(tmp)
    good = tmp / "good.json"
    write_artifact(good, record)
    first, *rest = record["deps"]
    bad = tmp / "bad.json"
    write_artifact(
        bad,
        {
            **record,
            "deps": [
                {key: value for key, value in first.items() if key != "commit"},
                *rest,
            ],
        },
    )
    return check_artifact_deps(good), check_artifact_deps(bad)
