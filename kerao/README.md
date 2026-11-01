# kerao

Builds FFmpeg's LGPL `libavutil`, `libavcodec`, `libavformat` and `libswresample` for Apple platforms.

```sh
python3 kerao/build.py --output <dir> --mode dev [--device <udid> --codesign-identity <sha-1> --provisioning-profile <path>]
python3 kerao/build.py --output <dir> --mode release --device <udid> --codesign-identity <sha-1> --provisioning-profile <path>
python3 kerao/build.py --self-test
```

`release` builds only a clean checkout whose HEAD is an annotated `n9.0.2-kerao.<n>` tag, and needs an iPhone. `dev` builds any checkout, with or without an iPhone.

## Prerequisites

- Xcode, with the iOS, iOS Simulator and macOS SDKs, and Python 3.11 or newer.
- `meson`, `ninja`, `cmake` and `pkg-config` from Homebrew: `brew install meson ninja cmake pkgconf`. Their versions are not pinned; `artifact.json` records the ones used.
- Network access to the two upstream repositories below.
- A booted iOS Simulator running iOS 17.0 or newer, for the codec check: `xcrun simctl boot <udid>`. Without one the build stops before it starts.
- For the `ios-arm64` codec check, an iPhone running iOS 17.0 or newer, paired with this Mac, in Developer Mode and unlocked, and three arguments:
  - `--device`: its UDID, from `xcrun devicectl list devices`.
  - `--codesign-identity`: the SHA-1 of an Apple Development identity in the keychain, as `security find-identity -v -p codesigning` prints it. Names are refused, because two identities can share one.
  - `--provisioning-profile`: a development `.mobileprovision` that lists the iPhone and holds that identity's certificate, such as one Xcode keeps in `~/Library/Developer/Xcode/UserData/Provisioning Profiles/`. Its team and app ID sign the runner app.

  None of them is stored in the repository. A `release` build without `--device` stops before it starts, and so does any build whose iPhone `devicectl` does not list as paired, or whose profile has expired, does not list the iPhone or lacks the identity's certificate.

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

## Privacy manifests

Every framework carries a `PrivacyInfo.xcprivacy`: at the top level on iOS, in `Versions/A/Resources/` on macOS. It declares no tracking, no tracking domains and no collected data, and its `NSPrivacyAccessedAPITypes` come from `kerao/required-reason-api/<lib>.json`. Each record entry gives a category, the APIs used, their purpose, the approved reason codes and why the library uses them. `apple.json` is Apple's required-reason API list, with its source pages and the date it was copied.

After the build, `nm -u` and the `__objc_methname` section of every binary are matched against `apple.json`. An API that a binary uses and its record does not declare fails the build. A recorded API the scan does not see is only reported. Update `apple.json` when Apple changes the list, and the records when a library's use changes.

`artifact.json` holds `libraries`, `repository`, `tag`, `commit`, `mode`, `dirty`, `built_at`, `xcode_build`, `sdks`, `tools`, `deps`, `inputs`, `frameworks`, `configure` and `unverified`. `tools` maps `meson`, `ninja`, `cmake` and `pkg-config` to their versions. Each `deps[]` entry gives a dependency's `name`, `repository`, `tag` and `commit`. Each `frameworks[].slices[]` entry gives a slice identifier, the binary's path relative to `<dir>` and its SHA-256. A `dev` build lists in `unverified` the checks it skipped.

`configure/<slice>.txt` is the configure output of the current build arguments. Commit it to `kerao/configure/` whenever the `committed configure output` check fails.

## Codec check

`kerao/codecs.json` lists the codecs `libavcodec` must decode, by their `avcodec_get_name()` names, grouped by media type. It comes from appendix A of `kerao/research/mpv-app-store-codecs.md`, a copy of the research on the codecs that the six mpv-based App Store players ship. The manifest also records the players, the research dates, and the codecs it leaves out with the reason for each.

After packaging, the build compiles `kerao/codec_check.c` for each slice against that slice's four delivered frameworks. The program prints `av_version_info()` and the codec of every decoder `av_codec_iterate()` returns. The macOS slice runs directly, the Simulator slice runs in the booted Simulator through `xcrun simctl spawn`, and the `ios-arm64` slice runs on the iPhone in a runner app. A slice fails when any listed codec has no decoder, or when the version is not the release tag (`release`) or `n9.0.2` followed by nothing or `-` (`dev`). The summary names the decoded codecs that the list leaves out.

A `dev` build without `--device` lists `ios-arm64 codecs` and `ios-arm64 av_version_info` in `unverified`.

### Runner app

The script assembles the app itself, without an Xcode project:

- The check program is the executable `KeraoCodecCheck`. `install_name_tool` replaces its rpaths to the build directories with `@executable_path/Frameworks`.
- `Frameworks/` holds copies of the four delivered `ios-arm64` frameworks, each signed with `codesign --sign <identity>`. The delivered frameworks stay unsigned.
- `Info.plist` takes its `CFBundleIdentifier` from the profile's app ID. A wildcard app ID's `*` becomes `kerao-codec-check`.
- The profile is copied in as `embedded.mobileprovision`, and the app is signed with `application-identifier`, `com.apple.developer.team-identifier` and the profile's `get-task-allow` as entitlements.

`xcrun devicectl device install app` installs it, replacing any app with the same bundle ID, and it stays installed. `xcrun devicectl device process launch --console --terminate-existing` runs it and returns its console output. A free personal team allows three of its apps on a device at a time. A fourth install fails with "maximum number of installed apps using a free developer profile", so remove one of them or use the profile of an app that is already installed.

### Completion protocol

A run is judged by its console output alone, and on the iPhone devicectl's exit status is never read. The check program prefixes every line it prints with `kerao-codec-check`: one `version <av_version_info()>` line, one `decoder <decoder> <codec>` line per decoder, then `end <decoder count>` last. Other lines, such as devicectl's own messages or libuavs3d's banner, are ignored. A run has a result only when the prefixed lines hold exactly one version line and one end line whose count equals the decoder lines. When a slice's output has no result, both of its checks fail with `no complete result`. That happens when the program exits or crashes before its end line, devicectl cannot launch it, or the iPhone disconnects. The app never starts a UI, so iOS kills it with signal 9 about 20 s after launch, and a program that hangs on the iPhone ends that way. A device run that outlasts 120 s stops the build with an error. The same rule decides the macOS and Simulator slices, where a program that exits nonzero also stops the build.

`devicectl --console` does not pass the exit code back reliably. To measure this, a hand-signed app whose C `main` printed a line and then returned 0 or 3, called `_exit(5)` or `abort()`, was launched with `devicectl device process launch --console --terminate-existing --json-output <file>` (Xcode 27.0, devicectl 642.16, iPhone 17 on iOS 27.2, 2026-11-01):

- With a 2 s sleep before exiting (4 runs), devicectl exited with the app's code (0, 3, 5), printed "The app terminated with the exit code <n>." and wrote it as `terminationResult.exitCode`. After `abort()` it exited 1 and printed "App terminated due to signal 6."
- When the app exited at once (7 runs), devicectl exited 1 with CoreDeviceError 10004, "The process identifier of the launched application could not be determined", in 5 runs, including one `return 0`. One `abort()` was reported as "exit code 0" with status 0. Only one run, a `return 0`, came back correct.
- The codec check program finishes in under a second. Of 11 runs against the delivered frameworks, 3 ended in error 10004 with status 1. All 11 printed the complete result.
