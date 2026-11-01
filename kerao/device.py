import dataclasses
import datetime
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

from checkout import UPSTREAM_VERSION
from common import FRAMEWORKS, IOS, BuildError, Check, capture, counterexample
from framework import delivered_framework, platform_keys
from macho import read_macho
from runners import RUN_TIMEOUT_SECONDS, Runner

DEVICE_CHECK = "device"
PHYSICAL = "physical"
PAIRED = "paired"
IOS_PLATFORM = "iOS"
SHA1 = re.compile(r"[0-9A-F]{40}")
APP_NAME = "KeraoCodecCheck"
APP_VERSION = "1"
APP_RPATH = "@executable_path/Frameworks"
WILDCARD_APP_NAME = "kerao-codec-check"


@dataclasses.dataclass(frozen=True)
class Iphone:
    udid: str
    name: str
    model: str
    version: str
    paired: bool


def find_iphone(listing: dict, udid: str) -> Iphone | None:
    """The physical iOS device udid in `devicectl list devices` JSON, if it is listed."""
    try:
        for device in listing["result"]["devices"]:
            properties = device["properties"]
            hardware = properties["hardware"]
            if (
                hardware.get("udid") != udid
                or hardware["reality"] != PHYSICAL
                or hardware["platform"] != IOS_PLATFORM
            ):
                continue
            return Iphone(
                udid=udid,
                name=properties["state"]["name"],
                model=hardware["marketingName"],
                version=properties["software"]["osVersionNumber"]["stringValue"],
                paired=properties["connection"]["pairingState"] == PAIRED,
            )
    except (KeyError, TypeError) as error:
        raise BuildError(f"cannot read the devicectl device list: {error!r}") from error
    return None


def read_device_listing() -> dict:
    listing = capture(["xcrun", "devicectl", "list", "devices", "--json-output", "-"])
    try:
        return json.loads(listing)
    except ValueError as error:
        raise BuildError(
            f"devicectl printed a device list that is not JSON: {error}"
        ) from error


def check_device(listing: dict, udid: str | None, mode: str) -> list[Check]:
    """listing is `devicectl list devices` JSON, unread without a udid.

    No check for a dev build without a udid; a release build fails without one.
    """
    if udid is None:
        if mode != "release":
            return []
        return [
            Check(
                DEVICE_CHECK,
                False,
                "a release build runs the ios-arm64 codec check: pass --device <udid>",
            )
        ]
    iphone = find_iphone(listing, udid)
    if iphone is None:
        return [Check(DEVICE_CHECK, False, f"devicectl lists no iPhone {udid}")]
    if not iphone.paired:
        return [Check(DEVICE_CHECK, False, f"{iphone.name} ({udid}) is not paired")]
    return [
        Check(
            DEVICE_CHECK,
            True,
            f"{iphone.name}, {iphone.model}, iOS {iphone.version}, {udid}",
        )
    ]


@dataclasses.dataclass(frozen=True)
class Target:
    """An iPhone and what signs the runner app installed on it."""

    udid: str
    identity: str
    profile: Path
    team: str
    bundle_id: str
    get_task_allow: bool


def read_profile(path: Path) -> dict:
    try:
        return plistlib.loads(
            capture(["security", "cms", "-D", "-i", str(path)]).encode()
        )
    except plistlib.InvalidFileException as error:
        raise BuildError(f"{path} is not a provisioning profile: {error}") from error


def read_target(udid: str, identity: str, profile_path: Path) -> Target:
    """identity is the SHA-1 of a codesigning identity in the keychain.

    Raises BuildError unless the profile provisions udid, holds the identity's
    certificate and has not expired.
    """
    if not SHA1.fullmatch(identity.upper()):
        raise BuildError(
            f"--codesign-identity {identity} is not the SHA-1 that "
            "security find-identity -v -p codesigning prints"
        )
    profile = read_profile(profile_path)
    try:
        team = profile["TeamIdentifier"][0]
        entitlements = profile["Entitlements"]
        app_id = entitlements["application-identifier"]
        expires = profile["ExpirationDate"]
        certificates = {
            hashlib.sha1(certificate).hexdigest().upper()
            for certificate in profile["DeveloperCertificates"]
        }
        provisioned = profile.get("ProvisionsAllDevices", False) or udid in profile.get(
            "ProvisionedDevices", []
        )
    except (KeyError, IndexError, TypeError) as error:
        raise BuildError(f"cannot read {profile_path}: {error!r}") from error
    if not app_id.startswith(f"{team}."):
        raise BuildError(f"{profile_path}: app id {app_id} is not in team {team}")
    if expires <= datetime.datetime.now(datetime.UTC).replace(tzinfo=None):
        raise BuildError(f"{profile_path} expired on {expires:%Y-%m-%d}")
    if not provisioned:
        raise BuildError(f"{profile_path} does not provision {udid}")
    if identity.upper() not in certificates:
        raise BuildError(f"{profile_path} does not hold the certificate of {identity}")
    bundle_id = app_id.removeprefix(f"{team}.")
    if bundle_id.endswith("*"):
        bundle_id = bundle_id.removesuffix("*") + WILDCARD_APP_NAME
    return Target(
        udid=udid,
        identity=identity,
        profile=profile_path,
        team=team,
        bundle_id=bundle_id,
        get_task_allow=bool(entitlements.get("get-task-allow", False)),
    )


def preconditions(target: Target | None, mode: str) -> list[Check]:
    if target is None:
        return check_device({}, None, mode)
    return check_device(read_device_listing(), target.udid, mode)


def codesign(identity: str, bundle: Path, entitlements: Path | None = None) -> None:
    capture(
        [
            *("codesign", "--force", "--sign", identity, "--timestamp=none"),
            *(("--entitlements", str(entitlements)) if entitlements else ()),
            str(bundle),
        ]
    )


def app_plist(bundle_id: str) -> dict[str, object]:
    return {
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": bundle_id,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": UPSTREAM_VERSION,
        "CFBundleSupportedPlatforms": [IOS.bundle_platform],
        "CFBundleVersion": APP_VERSION,
        **platform_keys(IOS),
    }


def make_app(binary: Path, output: Path, target: Target, app: Path) -> Path:
    """Wrap binary, linked against output's ios-arm64 frameworks, in a signed app."""
    executable = app / APP_NAME
    app.mkdir(parents=True)
    shutil.copy(binary, executable)
    host_rpaths = read_macho(executable).rpaths
    capture(
        [
            *("xcrun", "install_name_tool"),
            *(arg for rpath in host_rpaths for arg in ("-delete_rpath", rpath)),
            *("-add_rpath", APP_RPATH, str(executable)),
        ]
    )
    for name in FRAMEWORKS:
        embedded = app / "Frameworks" / f"{name}.framework"
        shutil.copytree(delivered_framework(output, IOS, name), embedded)
        codesign(target.identity, embedded)
    with (app / "Info.plist").open("wb") as file:
        plistlib.dump(app_plist(target.bundle_id), file)
    shutil.copy(target.profile, app / "embedded.mobileprovision")
    entitlements = app.parent / "entitlements.plist"
    with entitlements.open("wb") as file:
        plistlib.dump(
            {
                "application-identifier": f"{target.team}.{target.bundle_id}",
                "com.apple.developer.team-identifier": target.team,
                "get-task-allow": target.get_task_allow,
            },
            file,
        )
    codesign(target.identity, app, entitlements)
    return app


def launch(udid: str, bundle_id: str) -> str:
    """The console output of one run, whatever devicectl's exit status.

    Raises BuildError when the run outlasts RUN_TIMEOUT_SECONDS.
    """
    command = [
        *("xcrun", "devicectl", "device", "process", "launch"),
        *("--device", udid, "--console", "--terminate-existing", bundle_id),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise BuildError("xcrun not found") from error
    except subprocess.TimeoutExpired as error:
        raise BuildError(
            f"the codec check app on {udid} ran past {RUN_TIMEOUT_SECONDS} s"
        ) from error
    return result.stdout


def device_runner(target: Target, output: Path) -> Runner:
    def run(binary: Path) -> str:
        app = make_app(binary, output, target, binary.parent / f"{APP_NAME}.app")
        capture(
            [
                *("xcrun", "devicectl", "device", "install", "app"),
                *("--device", target.udid, str(app)),
            ]
        )
        return launch(target.udid, target.bundle_id)

    return run


FAKE_UDID = "00008150-0000000000000001"


def fake_device_listing(pairing_state: str) -> dict:
    """`devicectl list devices` JSON with one iPhone in pairing_state and one Simulator."""
    return {
        "result": {
            "devices": [
                {
                    "properties": {
                        "connection": {"pairingState": pairing_state},
                        "hardware": {
                            "marketingName": "iPhone 17",
                            "platform": "iOS",
                            "reality": "physical",
                            "udid": FAKE_UDID,
                        },
                        "software": {"osVersionNumber": {"stringValue": "27.2"}},
                        "state": {"name": "iPhone"},
                    }
                },
                {
                    "properties": {
                        "connection": {"pairingState": "paired"},
                        "hardware": {
                            "marketingName": "iPhone 15",
                            "platform": "iOS",
                            "reality": "simulated",
                            "udid": "00000000-0000-0000-0000-000000000000",
                        },
                        "software": {"osVersionNumber": {"stringValue": "17.0"}},
                        "state": {"name": "iPhone 15"},
                    }
                },
            ]
        }
    }


@counterexample
def release_build_without_a_device(tmp: Path) -> tuple[Check, Check]:
    listing = fake_device_listing("paired")
    return (
        check_device(listing, FAKE_UDID, "release")[0],
        check_device(listing, None, "release")[0],
    )


@counterexample
def device_not_paired(tmp: Path) -> tuple[Check, Check]:
    def check(pairing_state: str) -> Check:
        return check_device(fake_device_listing(pairing_state), FAKE_UDID, "dev")[0]

    return check("paired"), check("unpaired")
