# kerao

Builds FFmpeg's LGPL `libavutil`, `libavcodec`, `libavformat` and `libswresample` for Apple platforms.

```sh
python3 kerao/build.py --output <dir> --mode dev
python3 kerao/build.py --output <dir> --mode release
python3 kerao/build.py --self-test
```

`release` builds only a clean checkout whose HEAD is an annotated `n9.0.2-kerao.<n>` tag. `dev` builds any checkout.

## Prerequisites

- Xcode, with the iOS, iOS Simulator and macOS SDKs, and Python 3.11 or newer.
- `meson`, `ninja`, `cmake` and `pkg-config` from Homebrew: `brew install meson ninja cmake pkgconf`. Their versions are not pinned; `artifact.json` records the ones used.
- Network access to the two upstream repositories below.
- A booted iOS Simulator running iOS 17.0 or newer, for the codec check: `xcrun simctl boot <udid>`. Without one the build stops before it starts.

## Dependencies

`libavcodec` links these statically. Each build clones them into a temporary directory and stops if the checked-out commit differs from the pin in `kerao/deps.py`.

| Library | Repository | Tag | Commit |
| --- | --- | --- | --- |
| dav1d | `https://code.videolan.org/videolan/dav1d.git` | `1.5.4` | `54706fc6bc0cdecab7e9593974a4039cc038fca7` |
| libuavs3d | `https://github.com/uavs3/uavs3d.git` | `1.2` | `0e20d2c291853f196c68922a264bcd8471d75b68` |

dav1d is built with meson and libuavs3d with CMake, as static libraries for the same target and SDK as FFmpeg. libuavs3d is built with `COMPILE_10BIT=1`, so it decodes 8-bit and 10-bit AVS3. FFmpeg also links the SDK's zlib and bzlib.

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

`artifact.json` holds `libraries`, `repository`, `tag`, `commit`, `mode`, `dirty`, `built_at`, `xcode_build`, `sdks`, `tools`, `deps`, `inputs`, `frameworks`, `configure` and `unverified`. `tools` maps `meson`, `ninja`, `cmake` and `pkg-config` to their versions. Each `deps[]` entry gives a dependency's `name`, `repository`, `tag` and `commit`. Each `frameworks[].slices[]` entry gives a slice identifier, the binary's path relative to `<dir>` and its SHA-256. A `dev` build lists in `unverified` the checks it skipped.

`configure/<slice>.txt` is the configure output of the current build arguments. Commit it to `kerao/configure/` whenever the `committed configure output` check fails.

## Codec check

`kerao/codecs.json` lists the codecs `libavcodec` must decode, by their `avcodec_get_name()` names, grouped by media type. It comes from appendix A of `kerao/research/mpv-app-store-codecs.md`, a copy of the research on the codecs that the six mpv-based App Store players ship. The manifest also records the players, the research dates, and the codecs it leaves out with the reason for each.

After packaging, the build compiles `kerao/codec_check.c` for each slice against that slice's four delivered frameworks. The program prints `av_version_info()` and the codec of every decoder `av_codec_iterate()` returns. The macOS slice runs directly, and the Simulator slice runs in the booted Simulator through `xcrun simctl spawn`. A slice fails when any listed codec has no decoder, or when the version is not the release tag (`release`) or `n9.0.2` followed by nothing or `-` (`dev`). The summary names the decoded codecs that the list leaves out.

The `ios-arm64` slice has no runner yet. A `dev` build lists its two checks in `unverified`, and a `release` build fails them.
