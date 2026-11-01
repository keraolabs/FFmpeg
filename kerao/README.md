# kerao

Builds FFmpeg's LGPL `libavutil`, `libavcodec`, `libavformat` and `libswresample` for Apple platforms.

```sh
python3 kerao/build.py --output <dir> --mode dev
python3 kerao/build.py --output <dir> --mode release
python3 kerao/build.py --self-test
```

`release` builds only a clean checkout whose HEAD is an annotated `n9.0.2-kerao.<n>` tag. `dev` builds any checkout.

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
  configure/<slice>.txt
```

Each xcframework has three slices, built for iOS 17.0, the iOS 17.0 Simulator and macOS 14.0, all arm64. Each framework is unsigned and loads the other frameworks through `@rpath`.

| Slice | Layout | id | Only `LC_RPATH` |
| --- | --- | --- | --- |
| `ios-arm64`, `ios-arm64-simulator` | flat | `@rpath/<lib>.framework/<lib>` | `@loader_path/..` |
| `macos-arm64` | `Versions/A` | `@rpath/<lib>.framework/Versions/A/<lib>` | `@loader_path/../../..` |

The public headers are byte-identical across the three slices, and `include/` is a copy of them.

`artifact.json` holds `libraries`, `repository`, `tag`, `commit`, `mode`, `dirty`, `built_at`, `xcode_build`, `sdks`, `tools`, `deps`, `inputs`, `frameworks`, `configure` and `unverified`. Each `frameworks[].slices[]` entry gives a slice identifier, the binary's path relative to `<dir>` and its SHA-256. A `dev` build lists in `unverified` the checks it skipped.

`configure/<slice>.txt` is the configure output of the current build arguments. Commit it to `kerao/configure/` whenever the `committed configure output` check fails.
