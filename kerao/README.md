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

Each framework is unsigned. Its id is `@rpath/<lib>.framework/Versions/A/<lib>`, its only `LC_RPATH` is `@loader_path/../../..`, and it loads the other frameworks through `@rpath`.

`artifact.json` holds `libraries`, `repository`, `tag`, `commit`, `mode`, `dirty`, `built_at`, `xcode_build`, `sdks`, `tools`, `deps`, `inputs`, `frameworks`, `configure` and `unverified`. Each `frameworks[].slices[]` entry gives a slice identifier, the binary's path relative to `<dir>` and its SHA-256. A `dev` build lists in `unverified` the checks it skipped.

`configure/<slice>.txt` is the configure output of the current build arguments. Commit it to `kerao/configure/` whenever the `committed configure output` check fails.
