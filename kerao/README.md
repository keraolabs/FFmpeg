# kerao

Builds FFmpeg's LGPL `libavutil`, `libavcodec`, `libavformat` and `libswresample` for Apple platforms.

```sh
python3 kerao/build.py --output <dir> --mode dev
python3 kerao/build.py --output <dir> --mode release
python3 kerao/build.py --self-test
```

`release` builds only a clean checkout whose HEAD is an annotated `n9.0.2-kerao.<n>` tag. `dev` builds any checkout.

`configure/<slice>.txt` is the configure output of the current build arguments. A build writes it to `<output>/configure/<slice>.txt`; commit that copy whenever the `committed configure output` check fails.
