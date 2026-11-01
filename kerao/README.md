# kerao

Builds FFmpeg's LGPL `libavutil`, `libavcodec`, `libavformat` and `libswresample` for Apple platforms. This branch holds everything a rebuild needs: the build script, the committed configure output, the codec list with its research and the required-reason API records. FFmpeg's own sources are not patched.

## Prerequisites

- A Mac with Apple silicon.
- Xcode, selected, set up and with the iOS platform installed:

  ```sh
  sudo xcode-select --switch /Applications/Xcode.app
  sudo xcodebuild -runFirstLaunch
  xcodebuild -downloadPlatform iOS
  ```

- Python 3.11 or newer as `python3`, and `meson`, `ninja`, `cmake` and `pkg-config`, all from Homebrew: `brew install python meson ninja cmake pkgconf`. The `/usr/bin/python3` that macOS ships is too old. The tools' versions are not pinned; `artifact.json` records the ones used.
- Network access to the two upstream repositories under [Dependencies](#dependencies).
- A booted iOS Simulator running iOS 17.0 or newer, for the codec check. `xcrun simctl list devices available` lists them and `xcrun simctl boot <udid>` boots one. Without one the build stops before it starts.
- For a `release` build, an iPhone and a signing identity, see below. A `dev` build can do without them.

### iPhone and signing

The `ios-arm64` codec check runs on an iPhone with iOS 17.0 or newer, paired with this Mac, in Developer Mode and unlocked. A free personal team is enough. On a Mac that has never run an app on that iPhone:

1. Add your Apple Account in Xcode's settings, under Accounts.
2. Connect the iPhone, trust this Mac on it, and turn on Settings › Privacy & Security › Developer Mode, which appears once Xcode has seen the iPhone.
3. In Xcode, run any iOS app on the iPhone with Automatically manage signing and your team. Xcode creates an Apple Development identity and a development profile for that app's bundle ID. With a free team, iOS refuses the first launch until you trust the developer in Settings › General › VPN & Device Management.

The build then takes three arguments:

- `--device`: the iPhone's UDID, from `xcrun devicectl list devices`.
- `--codesign-identity`: the SHA-1 of the Apple Development identity, as `security find-identity -v -p codesigning` prints it. Names are refused, because two identities can share one.
- `--provisioning-profile`: a development `.mobileprovision` that lists the iPhone and holds that identity's certificate, such as the one step 3 left in `~/Library/Developer/Xcode/UserData/Provisioning Profiles/`. `security cms -D -i <path>` prints its app ID, devices and expiry. Its team and app ID sign the runner app.

None of them is stored in the repository. A `release` build without `--device` stops before it starts, and so does any build whose iPhone `devicectl` does not list as paired, or whose profile has expired, does not list the iPhone or lacks the identity's certificate.

## Usage

`kerao/build.py` is the entry point. It builds the checkout it lives in from any working directory, so it can be called by its absolute path.

```sh
python3 kerao/build.py --output <dir> --mode dev [--device <udid> --codesign-identity <sha-1> --provisioning-profile <path>]
python3 kerao/build.py --output <dir> --mode release --device <udid> --codesign-identity <sha-1> --provisioning-profile <path>
python3 kerao/build.py --self-test
```

- `--output`: a new or empty directory for the build products. Keep it outside the checkout: products inside it make the worktree dirty, and a `release` build refuses a dirty one.
- `--mode`: `release` or `dev`, see [Modes](#modes).
- `--device`, `--codesign-identity`, `--provisioning-profile`: all three or none, see [iPhone and signing](#iphone-and-signing).
- `--self-test`: runs the [self-test](#self-test) instead of a build.

A build runs every check before it exits and prints a summary to stdout: the commit, toolchain and dependencies, the checks it did not run as `unverified`, then one `pass` or `FAIL` line per check. The build tools write to stderr. The exit status is 0 only when every check passes. When a precondition fails, nothing is built. A failing tool or a missing file stops the build at once with `error:` on stderr, except in the [codec check](#completion-protocol), where it fails that slice's checks.

## Modes

Both modes need a checkout without a `VERSION` file, because one would override the `git describe` that `av_version_info()` reports.

| | `release` | `dev` |
| --- | --- | --- |
| Checkout | HEAD carries exactly one annotated `n9.0.2-kerao.<n>` tag, and `git status` shows nothing, untracked files included | any commit and worktree whose `git describe --tags` starts with `n9.0.2` |
| iPhone | required | optional |
| `av_version_info()` of every slice | exactly the tag | `n9.0.2`, or `n9.0.2-` followed by anything |
| `artifact.json` `tag` | the tag | `git describe --tags --always` |
| `artifact.json` `unverified` | `[]` | `ios-arm64 codecs` and `ios-arm64 av_version_info` without `--device`, otherwise `[]` |

core's release packaging and the libplacebo fork's `release` mode accept only `release` artifacts.

## Self-test

`--self-test` runs each check against counterexamples without building FFmpeg. Every counterexample gives the check an input it must pass and a broken copy it must fail, such as a framework with a second `LC_RPATH` or a codec list naming a codec no decoder has. It needs Xcode, but no network, Simulator or iPhone, and takes a few seconds.

A check is a `check_*` function in `kerao/`, and the self-test also fails when no counterexample calls one. A new check therefore comes with a counterexample registered through `@counterexample`.

## Dependencies

`libavcodec` links these statically. Each build clones them into a temporary directory and stops if the checked-out commit differs from the pin in `kerao/deps.py`.

| Library | Repository | Tag | Commit |
| --- | --- | --- | --- |
| dav1d | `https://code.videolan.org/videolan/dav1d.git` | `1.5.4` | `54706fc6bc0cdecab7e9593974a4039cc038fca7` |
| libuavs3d | `https://github.com/uavs3/uavs3d.git` | `1.2` | `0e20d2c291853f196c68922a264bcd8471d75b68` |

dav1d is built with meson and libuavs3d with CMake, as static libraries for the same target and SDK as FFmpeg. libuavs3d is built with `COMPILE_10BIT=1`, so it decodes 8-bit and 10-bit AVS3. FFmpeg also links the SDK's zlib.

## Output

```
<dir>/
  libavutil.xcframework/ios-arm64/libavutil.framework
  libavutil.xcframework/ios-arm64-simulator/libavutil.framework
  libavutil.xcframework/macos-arm64/libavutil.framework
  libavcodec.xcframework/…
  libavformat.xcframework/…
  libswresample.xcframework/…
  include/libavutil/… include/libavcodec/… include/libavformat/… include/libswresample/…
  artifact.json
  notices/ffmpeg/LICENSE.md
  notices/ffmpeg/COPYING.LGPLv2.1
  notices/dav1d/COPYING
  notices/libuavs3d/COPYING
  configure/<slice>.txt
```

Each xcframework has three slices, built for iOS 17.0, the iOS 17.0 Simulator and macOS 14.0, all arm64. Each framework is unsigned and loads the other frameworks through `@rpath`.

| Slice | Layout | id | Only `LC_RPATH` |
| --- | --- | --- | --- |
| `ios-arm64`, `ios-arm64-simulator` | flat | `@rpath/<lib>.framework/<lib>` | `@loader_path/..` |
| `macos-arm64` | `Versions/A` | `@rpath/<lib>.framework/Versions/A/<lib>` | `@loader_path/../../..` |

The public headers are byte-identical across the three slices, and `include/` is a copy of them.

`configure/<slice>.txt` is the configure output of the current build arguments. Commit it to `kerao/configure/` whenever the `committed configure output` check fails.

### artifact.json

| Field | Value |
| --- | --- |
| `libraries` | `["libavutil", "libavcodec", "libavformat", "libswresample"]` |
| `repository` | `https://github.com/keraolabs/FFmpeg` |
| `tag` | see [Modes](#modes) |
| `commit` | HEAD's full commit hash |
| `mode` | `release` or `dev` |
| `dirty` | `true` when `git status` lists any change, untracked files included |
| `built_at` | when `artifact.json` was written, in UTC, as `2026-11-01T12:43:24Z` |
| `xcode_build` | Xcode's build version, as `27A266a` |
| `sdks` | each slice identifier mapped to its SDK's `name` and `version`, as `{"name": "iphoneos", "version": "27.0"}` |
| `tools` | `meson`, `ninja`, `cmake` and `pkg-config`, each mapped to the version it reports |
| `deps` | one entry per [dependency](#dependencies) with its `name`, `repository`, `tag` and `commit` |
| `inputs` | `[]`, because no other kerao artifact goes into this one |
| `frameworks` | one entry per library with its `name` and `slices`; each slice gives its `identifier`, the binary's `path` relative to `<dir>` and its `sha256` |
| `configure` | each slice identifier mapped to its configure `args`, in full, and its `license` line |
| `unverified` | the names of the artifact checks this build did not run, see [Modes](#modes). The release preconditions a `dev` build skips are not among them: `mode`, `commit` and `dirty` identify a `dev` artifact |

## Privacy manifests

Every framework carries a `PrivacyInfo.xcprivacy`: at the top level on iOS, in `Versions/A/Resources/` on macOS. It declares no tracking, no tracking domains and no collected data, and its `NSPrivacyAccessedAPITypes` come from `kerao/required-reason-api/<lib>.json`. Each record entry gives a category, the APIs used, their purpose, the approved reason codes and why the library uses them. `apple.json` is Apple's required-reason API list, with its source pages and the date it was copied.

After the build, `nm -u` and the `__objc_methname` section of every binary are matched against `apple.json`. An API that a binary uses and its record does not declare fails the build. A recorded API the scan does not see is only reported. Update `apple.json` when Apple changes the list, and the records when a library's use changes.

## Codec check

`kerao/codecs.json` lists the codecs `libavcodec` must decode, by their `avcodec_get_name()` names, grouped by media type. It comes from appendix A of `kerao/research/mpv-app-store-codecs.md`, a copy of the research on the codecs that the six mpv-based App Store players ship. The manifest also records the players, the research dates, and the codecs it leaves out with the reason for each.

After packaging, the build compiles `kerao/codec_check.c` for each slice against that slice's four delivered frameworks. The program prints `av_version_info()` and the codec of every decoder `av_codec_iterate()` returns. The macOS slice runs directly, the Simulator slice runs in the booted Simulator through `xcrun simctl spawn`, and the `ios-arm64` slice runs on the iPhone in a runner app. A slice fails when any listed codec has no decoder, or when the version does not match its [mode](#modes). The summary names the decoded codecs that the list leaves out.

### Runner app

The script assembles the app itself, without an Xcode project:

- The check program is the executable `KeraoCodecCheck`. `install_name_tool` replaces its rpaths to the build directories with `@executable_path/Frameworks`.
- `Frameworks/` holds copies of the four delivered `ios-arm64` frameworks, each signed with `codesign --sign <identity>`. The delivered frameworks stay unsigned.
- `Info.plist` takes its `CFBundleIdentifier` from the profile's app ID. A wildcard app ID's `*` becomes `kerao-codec-check`.
- The profile is copied in as `embedded.mobileprovision`, and the app is signed with `application-identifier`, `com.apple.developer.team-identifier` and the profile's `get-task-allow` as entitlements.

`xcrun devicectl device install app` installs it, replacing any app with the same bundle ID, and it stays installed. `xcrun devicectl device process launch --console --terminate-existing` runs it and returns its console output. A free personal team allows three of its apps on a device at a time. A fourth install fails with "maximum number of installed apps using a free developer profile", so remove one of them or use the profile of an app that is already installed.

### Completion protocol

A run is judged by its console output alone, and on the iPhone devicectl's exit status is never read. The check program prefixes every line it prints with `kerao-codec-check`: one `version <av_version_info()>` line, one `decoder <decoder> <codec>` line per decoder, then `end <decoder count>` last. Other lines, such as devicectl's own messages or libuavs3d's banner, are ignored. A run has a result only when the prefixed lines hold exactly one version line and one end line whose count equals the decoder lines. When a slice's output has no result, both of its checks fail with `no complete result`, and the other slices still run. That happens when the program exits or crashes before its end line, fails to compile, devicectl cannot install or launch it, or the iPhone disconnects. The app never starts a UI, so iOS kills it with signal 9 about 20 s after launch, and a program that hangs on the iPhone ends that way. A run on any slice that outlasts 120 s has no result either. The same rule decides the macOS and Simulator slices, where a program that exits nonzero has no result.

`devicectl --console` does not pass the exit code back reliably. To measure this, a hand-signed app whose C `main` printed a line and then returned 0 or 3, called `_exit(5)` or `abort()`, was launched with `devicectl device process launch --console --terminate-existing --json-output <file>` (Xcode 27.0, devicectl 642.16, iPhone 17 on iOS 27.2, 2026-11-01):

- With a 2 s sleep before exiting (4 runs), devicectl exited with the app's code (0, 3, 5), printed "The app terminated with the exit code <n>." and wrote it as `terminationResult.exitCode`. After `abort()` it exited 1 and printed "App terminated due to signal 6."
- When the app exited at once (7 runs), devicectl exited 1 with CoreDeviceError 10004, "The process identifier of the launched application could not be determined", in 5 runs, including one `return 0`. One `abort()` was reported as "exit code 0" with status 0. Only one run, a `return 0`, came back correct.
- The codec check program finishes in under a second. Of 11 runs against the delivered frameworks, 3 ended in error 10004 with status 1. All 11 printed the complete result.

## Cutting a release

A release is an annotated `n9.0.2-kerao.<n>` tag on the `kerao` branch, built once from a fresh clone. `<n>` starts at 1 for each upstream tag. A tag is never moved, deleted or reused: a fix ships as the next `<n>`, on a new commit, because a HEAD with two release tags fails `release tag`. Rebuilding from an existing tag needs no new one.

1. Merge everything the release ships into `kerao`, then tag its tip and push the tag:

   ```sh
   git switch kerao
   git pull --ff-only
   git tag -a n9.0.2-kerao.<n> -m n9.0.2-kerao.<n>
   git push origin n9.0.2-kerao.<n>
   ```

2. Clone the tag into a new directory and build it in `release` mode, with the Simulator booted and the iPhone connected:

   ```sh
   git clone --branch n9.0.2-kerao.<n> https://github.com/keraolabs/FFmpeg.git <clone>
   python3 <clone>/kerao/build.py --output <dir> --mode release --device <udid> \
       --codesign-identity <sha-1> --provisioning-profile <path> > summary.txt
   ```

3. The build must exit 0. `artifact.json` then has `mode` `release`, `dirty` `false`, `tag` `n9.0.2-kerao.<n>` and `unverified` `[]`, and the summary's three `av_version_info` lines read exactly `n9.0.2-kerao.<n>`. The fork has no CI, so post `summary.txt` and `artifact.json` on the release's issue in keraolabs/kerao as its evidence.
