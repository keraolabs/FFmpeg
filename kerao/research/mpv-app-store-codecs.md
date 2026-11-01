# mpv-based players on the Apple App Store: the codecs they ship

Research for a proposed requirement: **the core decodes every codec that mpv-based players currently on the Apple App Store ship, within the license rules of R8.**

**Scope.** Coverage counts codecs, meaning FFmpeg `AVCodecID`s, not decoder implementations. When a codec has both a native and an external-library decoder (`vp9` and `libvpx-vp9`), either one covers it. Demuxers, protocols and real-time performance are out of scope.

**License rules applied.** These are the R8 rules from `CODING_STANDARDS.md`:

- FFmpeg is configured as LGPL-2.1, so no `--enable-gpl`, `--enable-nonfree` or `--enable-version3`.
- No GPLv3 or LGPLv3 component.
- Every external C library has a compatible license.

**Sources and dates.** Everything was read on 2026-10-30 and 2026-10-31.

- **App Store presence:** Apple's iTunes Lookup and Search API (`itunes.apple.com/lookup`, `/search`, US storefront). The `apps.apple.com` pages rate-limit automated fetches, so the API was used instead.
- **Build configuration:** each app's public repository at the tag or commit that matches its store version, and the build scripts of the packaging it pins.
- **Prebuilt binaries:** where an app pins one, the binary was downloaded from its GitHub release and inspected with `strings` and `nm`. Three things were read from it:
  - the configure line FFmpeg embeds for `avcodec_configuration()`;
  - the `libavcodec license:` string;
  - the `ff_*_decoder` symbols.
- **FFmpeg 9.0:** branch `release/9.0` at [`7adfbe4`](https://github.com/FFmpeg/FFmpeg/commit/7adfbe40dcde598f93a6963d2f7b22cd75202ccc) (2026-10-30). It was configured and its `libavcodec` built on a Mac (section 6).

**Trust tags.** Every statement carries one:

- **Verified:** a primary source at the cited URL or file and line says it, or it was measured here.
- **Secondary:** a third party says it, and it was not reproduced here.
- **Inferred:** a conclusion drawn here from verified facts.

**Code provenance.** Only build scripts, dependency manifests, FFmpeg's `configure`, license headers and binary metadata were read, in line with [ADR-0012](https://github.com/keraolabs/kerao/blob/main/docs/adr/0012-the-core-never-ports-gpl-or-lgpl-source.md). No decoder implementation was read.

## Short answer

- **Players.** Six App Store apps ship libmpv and publish how they build it: Streamyfin, AerioTV, Plezy, Airwave, Tentacle TV and NipaPlay. NipaPlay ships it only as a non-default engine. Two more well-known apps are verified to use mpv but publish no build configuration: Outplayer and Filebar. So do twelve smaller closed-source apps whose App Store text credits mpv.
- **Excluded.** IINA, Yattee and Stremio are not on the App Store. Swiftfin's store build uses VLCKit. Strimr and Moonfin use AetherEngine. Plex's current Apple apps are reported not to use mpv. Infuse runs its own player. SenPlayer and VidHub cannot be shown either way.
- **The union is every native FFmpeg decoder, plus dav1d and uavs3d.**
  - Plezy and Airwave enable every native decoder of FFmpeg n8.0.1. Their binaries contain all 517 native decoders that n8.0.1 can build on Apple.
  - Tentacle TV for macOS (n7.1.1) and NipaPlay (FFmpeg 6.0) also enable every native decoder.
  - The only external decoder libraries any public build links are **libdav1d** and **libuavs3d**.
  - No public build links libvpx, libaribcaption, libxevd, libjxl, libzvbi, liblc3, libcodec2, or any decoder library that is GPL, nonfree or version3.
- **The filtered result for FFmpeg 9.0 under R8** (section 4 and appendix A):
  - It is **every decoder a default LGPL-2.1 configure of FFmpeg 9.0 enables on Apple (514), plus libdav1d (BSD-2-Clause) and libuavs3d (BSD-3-Clause)**.
  - One of the 514, `webp_anim`, is new in 9.0 and outside the union. Without it, the set is 515 decoders covering 489 codec IDs: 266 video, 203 audio and 20 subtitle. Keeping it is harmless.
- **Removed.**
  - **Eight ADPCM codecs**, which only Streamyfin ships. Since FFmpeg 8.1, `configure` builds them only with `--enable-gpl`.
  - **Sonic.** FFmpeg 9.0 deleted its decoder, so the reason is availability, not license.
  - Not lost: the `v308`, `v408`, `v410` and `ayuv` decoders are gone in 9.0, but `rawvideo` now decodes those formats.
- **AV1 caveat.** FFmpeg's native `av1` decoder only drives a hardware accelerator. Software AV1 needs libdav1d.
- **License flags in the players' builds.**
  - Every public build except Tentacle TV's macOS one passes `--enable-gpl`, `--enable-nonfree` or `--enable-version3`. Even MPVKit's "LGPL" product is LGPLv3. Streamyfin's binary declares itself "nonfree and unredistributable".
  - None of those flags adds a codec to the union except the eight ADPCM codecs.
- **Not verifiable from public sources:**
  - the FFmpeg configuration of Outplayer, Filebar and the long tail;
  - whether VidHub, SenPlayer and the current Plex apps use mpv on Apple platforms.

## 1. Which players

### 1.1 Players included

Store data is from the iTunes Lookup API, read 2026-10-30. "Store devices" lists what the API's `supportedDevices` field names. It gives one version per listing and does not separate the platform builds of a universal purchase.

| Player | App Store | Version, date | Store devices | mpv evidence | Build public |
|---|---|---|---|---|---|
| Streamyfin | [id6593660679](https://apps.apple.com/us/app/streamyfin/id6593660679) | 0.55.2, 2026-10-09 | iPhone, iPad | pins a streamyfin/MPVKit podspec | yes |
| AerioTV | [id6760727974](https://apps.apple.com/us/app/aeriotv/id6760727974) | 1.8.42, 2026-10-12 | iPhone, iPad | pins mpvkit/MPVKit 1.0.0 | yes |
| Plezy | [id6754315964](https://apps.apple.com/us/app/plezy-media-server-client/id6754315964) | 2.25.0, 2026-10-27 | iPhone, iPad | pins edde746/mpv-build | yes |
| Airwave: Live TV | [id6801608850](https://apps.apple.com/us/app/airwave-live-tv/id6801608850) | 1.3, 2026-09-30 | Apple TV | pins edde746/MPVKit 1.0.12 | yes |
| Tentacle TV | [id6760205634](https://apps.apple.com/us/app/tentacle-tv/id6760205634) | 1.30.0, 2026-10-30 | iPhone, iPad, Mac | own LGPL MPVKit build (iOS), own LGPL mpv build (macOS) | yes |
| NipaPlay | [id6751284970](https://apps.apple.com/us/app/nipaplay/id6751284970) | 1.11.10, 2026-10-23 | iPhone, iPad | media_kit libmpv as a selectable engine | yes |
| Outplayer | [id1449923287](https://apps.apple.com/us/app/outplayer/id1449923287) | 2026.11, 2026-10-21 | iPhone, iPad | public forks "mpv, used in Outplayer" | source only |
| Filebar (formerly Fileball) | [id1558391784](https://apps.apple.com/us/app/filebar-media-player/id1558391784) | 1.4.13, 2026-07-19 | iPhone, iPad | changelog | no |

**Streamyfin**

- **Verified, mpv:** at tag `v0.55.2`, [`app.json` L184–185](https://github.com/streamyfin/streamyfin/blob/v0.55.2/app.json#L184-L185) points the `MPVKit` pod at `streamyfin/MPVKit/0.41.0-av5/MPVKit.podspec`.
- **Verified:** the [`MpvPlayer.podspec` L12](https://github.com/streamyfin/streamyfin/blob/v0.55.2/modules/mpv-player/ios/MpvPlayer.podspec#L12) depends on `MPVKit`.

**AerioTV**

- **Verified, mpv:** at tag `v1.8.42`, [`Package.resolved` L5–11](https://github.com/jonzey231/AerioTV/blob/v1.8.42/Aerio.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved#L5-L11) pins `mpvkit/MPVKit` 1.0.0, revision `288527d`.
- **Verified:** `project.pbxproj` L2101 and L2106 link `productName = MPVKit`, the LGPL product rather than `MPVKit-GPL`.
- **Verified:** its README (L638 at that tag) says it "links MPVKit (mpv v0.41.0 and FFmpeg 8.x, LGPL-3.0-or-later …)".

**Plezy**

- **Verified, mpv:** at tag `2.25.0`, [`ios/Runner.xcworkspace/.../Package.resolved` L31–36](https://github.com/edde746/plezy/blob/2.25.0/ios/Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved#L31-L36) pins `edde746/mpv-build` at revision `3b9f38a`. The macOS and tvOS projects carry the same pin.
- **Verified:** the [mpv-build README](https://github.com/edde746/mpv-build/blob/3b9f38affe3c4171f8e6bc47331feffd3d13be1d/README.md) calls itself "One repository for every mpv supply chain Plezy ships" (L7). It says "The packages ship as GPL builds" (L51).

**Airwave: Live TV**

- **Verified, mpv:** [`packages/mpv-player/app.plugin.js` L15–17](https://github.com/Quixomatic/Airwave/blob/7fd3da6a4ef55d2051c5d90b920161cf4f95efa4/packages/mpv-player/app.plugin.js#L15-L17) pins `https://github.com/edde746/MPVKit`, version `1.0.12`, product `MPVKit`. L80 sets `exactVersion`.
- **Verified:** the file last changed on 2026-08-23. It is unchanged at `main` (2026-10-23).
- **Inferred:** the store build 1.3 (2026-09-30) uses this pin. The repository has no release tags to confirm it.
- **Verified:** the repository links the listing (`apps/site/lib/store-links.ts`, `APPLE_APP_ID = "6801608850"`).

**Tentacle TV**

One listing covers iOS, iPadOS, macOS and tvOS. The README's platform table (tag `mobile-v1.30.0`) lists three Apple rows:

| Platform | Technology (README) |
|---|---|
| iOS / iPadOS | "React Native + Expo" |
| macOS | "Electron + native mpv player" |
| Apple TV | "React Native (tvOS) + AVPlayer" |

- **Verified, iOS mpv:** [`apps/mobile/ios/MPVKit.podspec`](https://github.com/Knaox/Tentacle-TV/blob/mobile-v1.30.0/apps/mobile/ios/MPVKit.podspec) at `mobile-v1.30.0` (2026-10-28) pins its own LGPL rebuild of streamyfin's fork, `mpvkit-lgpl-0.41.0-av5`.
- **Verified, macOS mpv:** at `desktop-v1.40.0` (2026-10-28), [`.github/workflows/desktop.yml` L238 and L275](https://github.com/Knaox/Tentacle-TV/blob/desktop-v1.40.0/.github/workflows/desktop.yml#L238-L275) builds the "macOS App Store (Electron)" target with `apps/desktop-electron/scripts/build-mpv-lgpl-macos.sh`.
- **tvOS:** it plays through AVPlayer and is out of scope (secondary: README only).
- **Inferred:** the Mac App Store build is `desktop-v1.40.0`. The lookup API reports only the listing's 1.30.0, which matches `mobile-v1.30.0`.

**NipaPlay**

- **Verified, mpv:** at the 1.11.10 version commit [`f077dd4`](https://github.com/AimesSoft/NipaPlay-Reload/commit/f077dd48653ab71d51ff26176608d0be4633a3c2), the `ios` and `macos` `Podfile.lock` files list `media_kit_libs_*_video (1.0.4)`. These come from the submodule `AimesSoft/media-kit` at `7a21356`.
- **Verified:** that fork's [`libs/ios/media_kit_libs_ios_video/ios/Makefile` L3 and L16](https://github.com/AimesSoft/media-kit/blob/7a2135661ff37a717f11d6012fefa56cae27ef36/libs/ios/media_kit_libs_ios_video/ios/Makefile#L3-L16) downloads `media-kit/libmpv-darwin-build` `v0.6.0`, variant `ios-universal-video-full`.
- **Verified, engine choice:** `lib/player_abstraction/player_factory.dart` L238–244 at the same commit makes MDK the default kernel. libmpv is the selectable `mediaKit` kernel.
- NipaPlay is included because its binary ships libmpv. Excluding it would not change the union (section 3).

**Outplayer**

- **Verified, mpv:** the GitHub organisation [OutplayerApp](https://github.com/OutplayerApp) hosts three forks: `mpv` ("mpv, used in Outplayer"), `FFmpeg` ("FFmpeg, used in Outplayer") and `fribidi`.
  - The [`outplayer` branch of OutplayerApp/FFmpeg](https://github.com/OutplayerApp/FFmpeg/tree/outplayer) is tag `n8.1.1` plus one commit. That commit is [`fb30627`](https://github.com/OutplayerApp/FFmpeg/commit/fb3062786baa8075538310d2bd697d72c82db8f4) (2026-05-10, "disable pixel formats not compatible with GLES") and touches only `configure` (GitHub compare `n8.1.1...outplayer`: 1 ahead, 0 behind).
  - The `outplayer` branch of OutplayerApp/mpv was last committed on 2026-09-18.
- **Secondary:** the mpv wiki page "Applications using mpv" lists Outplayer.

**Filebar (formerly Fileball)**

- **Verified, mpv:** the [changelog](https://fileball.app/changelog/) has these mpv entries:
  - 1.2.13 (2023-02-28): "upgrade mpv version to 0.35.1";
  - 1.2.29 (2023-10-09): "upgrade mpv to 0.36.0";
  - 1.3.29 (2024-11-23): "add AV1 decode feature to mpv player";
  - 1.3.43 (2025-08-11): "fix MPV player screenshot size issue".
- **Verified:** the newest changelog entry is 1.4.13, dated 2026-07-20.

### 1.2 Closed-source long tail

Each of these credits mpv in its App Store description or release notes. The text was read through the Lookup API on 2026-10-30 (verified). None publishes its FFmpeg configuration. The sweep that found them searched the store for "mpv" and "libmpv" and is not exhaustive.

| App | ID | Version, date | Text (field) |
|---|---|---|---|
| SeeClap IPTV Player & Xtream | 6446091614 | 2.16.0, 2026-10-29 | "Three playback engines to pick from (KSPlayer, VLC, MPV)" (description) |
| LillyPlayer - IPTV Player | 1446967273 | 4.2, 2026-10-25 | "Better subtitle tracking (mpv)" (release notes) |
| VLT Player: IPTV | 6793105863 | 1.3, 2026-10-02 | "Video engine picker — Automatic, VLC, MPV or the system player" (release notes) |
| CapyPlayer - NAS Video Player | 6755650660 | 1.1.7, 2026-10-21 | "Choose from MPV and AetherEngine playback engines" (description) |
| StreamClient | 6759009987 | 1.6, 2026-10-12 | "playback powered by MPV with Metal rendering" (description) |
| Livedio - M3U & Video Player | 6788334969 | 2.0, 2026-10-21 | "A native engine backed by libmpv" (description) |
| Unraid Drive | 6809862123 | 1.5.2, 2026-10-26 | "an mpv player (MKV, AVI, WebM, FLAC…)" (description) |
| Noctra | 6811375568 | 1.0.1, 2026-10-24 | "优化 CineCore、MPV 字幕避边" (release notes) |
| CastFlow | 6448221325 | 5.0.6, 2026-07-19 | "MPV‑powered playback" (description) |
| Cinematic Player | 6763082533 | 1.4, 2026-06-03 | "Powered by the industry-leading MPV engine" (description) |
| IP Digi - IPTV & Media Player | 6774709538 | 1.0.6, 2026-06-21 | "mpv-backed engine" (description) |
| Popvee: AI Media Player (Mac) | 6784186034 | 1.0.7, 2026-08-03 | "Custom libmpv + gpu-next" (description) |

### 1.3 Excluded

- **IINA: not on the App Store.**
  - Verified: an iTunes Search for "iina" with `entity=macSoftware` returns no IINA.
  - Verified: [iina/iina#2152](https://github.com/iina/iina/issues/2152), "Mac App Store release", has been open since 2018-12-31.
- **Yattee: not on the App Store.**
  - Verified: the lookup for id1595136629 returns nothing.
  - Verified: the maintainer wrote on 2026-02-08 that "App is gone from the App Store because the last approved build was heavily outdated and not working so I removed it" ([comment](https://github.com/yattee/yattee/issues/906#issuecomment-3868227394)).
- **Swiftfin: the store build is VLCKit.**
  - Verified: the store has 1.6.1 (2026-08-24).
  - Verified: [`Cartfile` at tag 1.6.1](https://github.com/jellyfin/Swiftfin/blob/1.6.1/Cartfile) pins `MobileVLCKit` and `TVVLCKit` 3.7.2.
  - mpv reached `main` on 2026-09-06 ("mpv player (#2274)"), but no release ships it yet.
- **Stremio: not on the US App Store.** Verified: an iTunes Search for "stremio" in `software` and `macSoftware` returns no Stremio app, and the lookup for id6741710156 returns nothing.
- **Strimr: on the store, but AetherEngine.**
  - Verified: id6757491271, 1.3.2, 2026-10-27.
  - Verified: at tag `1.3.2`, `Strimr.xcodeproj/.../Package.resolved` pins `wunax/AetherEngine` and `superuser404notfound/FFmpegBuild` 3.10.0, and no MPVKit or libmpv.
  - "mpv" appears only as an external-player option in `StrimrTests/Models/AppSettingsTests.swift`.
- **Moonfin: on the store, but AetherEngine on Apple.**
  - Verified: id6761283970, 2.5.1, 2026-08-28.
  - Verified: [`pubspec.yaml` at tag 2.5.1](https://github.com/Moonfin-Client/Moonfin-Core/blob/2.5.1/pubspec.yaml) says "Apple runs on AetherEngine" and "Apple keeps libmpv out entirely".
- **Plex: not shown to use mpv on Apple today.**
  - Verified: id383457673, 2026.20.0, 2026-10-13.
  - Secondary: in a [forum thread](https://forums.plex.tv/t/911626) dated 2025-04-04, the user BigWheel wrote: "I was told it is not mpv anymore". The fetched page showed no staff badge.
  - Secondary: users report that the redesigned tvOS app, rolling out since 2026-09, dropped libmpv.
  - Plex's mpv-based desktop apps (Plex for Mac, Plex HTPC) are not on the Mac App Store. Verified: a `macSoftware` search for "plex" returns no Plex Inc. app.
- **Infuse: its own player on FFmpeg.**
  - Verified: id1136220934, 8.5.9, 2026-10-26.
  - Verified: in a [Firecore community post](https://community.firecore.com/t/what-player-does-infuse-use/38003/3) dated 2022-06-18, "james" wrote: "we began creating our own player in 2010", and "Infuse's player application sits on top of other components, like FFmpeg."
- **SenPlayer: undetermined.**
  - Verified: id6443975850, 6.2.3, 2026-10-09.
  - Verified: the [KSPlayer README](https://github.com/kingslay/KSPlayer/blob/main/README.md) L104 lists it among "Apps Licensed to Use this SDK".
  - Verified: KSPlayer's `Package.swift` L25–38 offers an optional `MPVPlayer` product built on `libmpv` from FFmpegKit.
  - No source says whether SenPlayer uses it.
- **VidHub: undetermined on Apple.**
  - Verified: id1659622164, 3.0.9, 2026-10-26.
  - Secondary: its Android APK contains `libmpv.so`.
  - No public statement names the Apple engine.

## 2. What each player ships

Every player decodes through libavcodec. Verified: mpv v0.41.0 has one video decoder wrapper, `video/decode/vd_lavc.c`, and one audio decoder wrapper, `audio/decode/ad_lavc.c`, beside the `ad_spdif.c` passthrough. Its subtitle decoders, `sub/sd_lavc.c` and `sub/sd_ass.c` with `sub/lavc_conv.c`, also run through libavcodec. So a player's codec set is its FFmpeg build's decoder set.

### 2.1 Summary

Notes on the columns:

- "License string" is the `libavcodec license:` string in the shipped binary (verified).
- "Native decoders" counts the `ff_*_decoder` symbols in the binary that `allcodecs.c` of that FFmpeg version declares, excluding `lib*` wrappers (verified).

| Player | Build it ships | FFmpeg | License string | Native decoders | External decoder libraries |
|---|---|---|---|---|---|
| Streamyfin | streamyfin/MPVKit `0.41.0-av5` (GPL asset) | n8.1 | "nonfree and unredistributable" | subset, 204 | libdav1d, libuavs3d |
| AerioTV | mpvkit/MPVKit `1.0.0`, product `MPVKit` | n8.1.2 | "LGPL version 3 or later" | subset, 196 | libdav1d, libuavs3d |
| Tentacle TV (iOS) | Tentacle's LGPL rebuild of `0.41.0-av5` | n8.1 | "LGPL version 3 or later" | subset, 196 | libdav1d, libuavs3d |
| Plezy | edde746/mpv-build `3b9f38a` | n8.0.1 | "GPL version 3 or later" | **all**, 517 | libdav1d, libuavs3d |
| Airwave | edde746/MPVKit `v1.0.12` | n8.0.1 | "GPL version 3 or later" | **all**, 517 | libdav1d, libuavs3d |
| Tentacle TV (macOS) | `build-mpv-lgpl-macos.sh` | n7.1.1 | not inspected (no binary published) | **all** (script) | libdav1d |
| NipaPlay | media-kit/libmpv-darwin-build `v0.6.0` video-full | 6.0 | "LGPL version 3 or later" | **all** (configure string) | libdav1d |
| Outplayer | OutplayerApp/FFmpeg `outplayer` | n8.1.1 | unknown | unknown | unknown |
| Filebar | unknown | unknown | unknown | unknown | unknown |

### 2.2 Details

**MPVKit, the packaging most of these builds descend from.**

- **Verified:** [mpvkit/MPVKit](https://github.com/mpvkit/MPVKit) offers two products, `MPVKit` (LGPL) and `MPVKit-GPL`.
- **Verified:** its "LGPL" product is LGPLv3. At tag `1.0.0` (`288527d`, 2026-07-25), [`main.swift` L653](https://github.com/mpvkit/MPVKit/blob/288527dffbc6d3e63cce147fc7b520c64a791603/Sources/BuildScripts/XCFrameworkBuild/main.swift#L653) passes `--enable-version3` to every variant. `--enable-gpl` is added only for the GPL variant (L579).
- **Verified:** the build uses a decoder subset. [L705](https://github.com/mpvkit/MPVKit/blob/288527dffbc6d3e63cce147fc7b520c64a791603/Sources/BuildScripts/XCFrameworkBuild/main.swift#L705-L732) passes `--disable-decoders`, then L707–732 add 71 distinct patterns. Among them are `adpcm*` (L722) and `sonic` (L726).
- **Verified:** L612 adds `--enable-libdav1d` and `--enable-libuavs3d` with their decoders.
- **Verified:** the FFmpeg pin is `n8.1.2` (L53).
- **Verified:** the current release `1.1.0-n9.0.2` (2026-10-07) moves to FFmpeg n9.0.2 and drops `sonic`. No store app was found pinning it.

**Streamyfin**

- **Verified:** it ships streamyfin/MPVKit at tag `0.41.0-av5` (`0933194`, 2026-09-02). That is a fork of upstream `0.41.0-n8.1`, with the same 71 decoder patterns (L738–765).
- **Verified:** [`MPVKit.podspec` L18–20](https://github.com/streamyfin/MPVKit/blob/0.41.0-av5/MPVKit.podspec#L18-L20) declares GPL-3.0 and downloads the release asset `MPVKit.xcframework.zip`, built by `make build enable-gpl` (`.github/workflows/release-combined.yml` L47).
- **Verified:** [`main.swift` L685–686](https://github.com/streamyfin/MPVKit/blob/0.41.0-av5/Sources/BuildScripts/XCFrameworkBuild/main.swift#L685-L686) passes `--enable-nonfree` and `--enable-version3`. L79 pins `n8.1`.
- **Verified, binary (`ios-arm64`):**
  - the configure string contains `--enable-gpl --enable-nonfree --enable-version3 --enable-libsmbclient --disable-decoders --enable-decoder='adpcm*'`;
  - every FFmpeg library reports "nonfree and unredistributable";
  - the decoder symbols include `sonic` and eight ADPCM decoders that FFmpeg 8.1 builds only with `--enable-gpl`: `adpcm_circus`, `adpcm_ima_escape`, `adpcm_ima_hvqm2`, `adpcm_ima_hvqm4`, `adpcm_ima_magix`, `adpcm_ima_pda`, `adpcm_n64` and `adpcm_psxc`.

**AerioTV**

- **Verified, binary:** the `Libavcodec.xcframework.zip` of MPVKit 1.0.0 (`ios-arm64`) reports "LGPL version 3 or later".
- **Verified, binary:** the configure string has `--enable-version3 --disable-decoders --enable-libdav1d --enable-libuavs3d`.
- **Verified, binary:** it holds 196 native decoders, including `sonic`, plus `libdav1d` and `libuavs3d`.

**Tentacle TV**

- **iOS: the subset, under LGPLv3.**
  - Verified: [`.github/workflows/mpvkit.yml`](https://github.com/Knaox/Tentacle-TV/blob/mobile-v1.30.0/.github/workflows/mpvkit.yml) L72 strips `--enable-nonfree` from streamyfin's script. L88 builds without `enable-gpl`, and L98 deletes libsmbclient and LuaJIT.
  - Verified: the podspec comment (L8–13) says this build is the App Store binary, and that mobile releases up to 1.10.x shipped the fork's GPL binaries.
  - Verified, binary (`mpvkit-lgpl-0.41.0-av5`, `ios-arm64`): every library reports "LGPL version 3 or later". It holds 196 native decoders, without the eight GPL-gated ADPCM decoders, plus `libdav1d` and `libuavs3d`.
- **macOS: all native decoders, under LGPL-2.1.**
  - Verified: [`build-mpv-lgpl-macos.sh`](https://github.com/Knaox/Tentacle-TV/blob/desktop-v1.40.0/apps/desktop-electron/scripts/build-mpv-lgpl-macos.sh) L21–22 pins FFmpeg `n7.1.1` and mpv `v0.40.0`.
  - Verified: L60–69 configure `--disable-gpl --disable-nonfree --disable-lzma --disable-sdl2 --enable-videotoolbox --enable-audiotoolbox --enable-libdav1d`, with no `--disable-decoders` and no `--enable-version3`.
  - Inferred: this enables every native decoder under LGPL-2.1-or-later. No binary was inspected.

**Plezy**

- **Verified:** edde746/mpv-build at [`3b9f38a`](https://github.com/edde746/mpv-build/tree/3b9f38affe3c4171f8e6bc47331feffd3d13be1d) (2026-10-27) pins FFmpeg `n8.0.1` in [`versions.json` L28–30](https://github.com/edde746/mpv-build/blob/3b9f38affe3c4171f8e6bc47331feffd3d13be1d/versions.json#L28-L30).
- **Verified:** [`main.swift`](https://github.com/edde746/mpv-build/blob/3b9f38affe3c4171f8e6bc47331feffd3d13be1d/Sources/BuildScripts/XCFrameworkBuild/main.swift) passes:
  - `--enable-gpl` unconditionally (L471);
  - `--enable-version3` (L552);
  - `--enable-decoders` (L589);
  - external libraries freetype, harfbuzz, fribidi, libass, Vulkan, shaderc, lcms2, libplacebo, libdav1d, libdovi, libuavs3d and OpenSSL (L507–510). Only dav1d and uavs3d get decoders.
- **Verified:** its FFmpeg patch series (`patches/ffmpeg/series.common`, `series.apple`) adds no decoder.
- **Verified, binary:** release asset `Libavcodec-c5f752f80b7e.xcframework.zip` (`ios-arm64`) reports "GPL version 3 or later". It contains all 517 native decoders that n8.0.1 declares, after excluding hardware wrappers for other platforms, plus `libdav1d` and `libuavs3d`.

**Airwave**

- **Verified:** edde746/MPVKit at [`v1.0.12`](https://github.com/edde746/MPVKit/blob/a453d675493a8abe26dc90f9dc484bc582628358/Sources/BuildScripts/XCFrameworkBuild/main.swift) (`a453d67`, 2026-07-11) passes:
  - FFmpeg `n8.0.1` (L45);
  - `--enable-gpl` unconditionally (L554);
  - `--enable-version3` (L630);
  - `--enable-decoders` (L667);
  - libdav1d, libuavs3d and OpenSSL among its libraries (L586–589).
- **Verified, binary:** the `tvos-arm64_arm64e` slice, which matters because the app is Apple TV only, reports "GPL version 3 or later". Its decoder set equals the `ios-arm64` slice and Plezy's: 517 native plus `libdav1d` and `libuavs3d`.

**NipaPlay**

- **Verified:** libmpv-darwin-build `v0.6.0` [`downloads.lock` L5–7 and L53–55](https://github.com/media-kit/libmpv-darwin-build/blob/v0.6.0/downloads.lock#L5-L7) pins FFmpeg 6.0 and mpv 0.36.0.
- **Verified:** [`scripts/ffmpeg/meson.build`](https://github.com/media-kit/libmpv-darwin-build/blob/v0.6.0/scripts/ffmpeg/meson.build) builds the `full` flavor (L316) from:
  - `--disable-autodetect` (L28);
  - `--enable-version3` and `--enable-mbedtls` (L49–50);
  - zlib and AudioToolbox;
  - `--enable-libdav1d` (L72);
  - `--enable-decoders` (L264).
- **Verified:** it also passes `--disable-decoder=h264` (L279), which `video_full_options` re-enables (L283).
- **Verified:** libvpx is linked only in the `encodersgpl` flavor (L295).
- **Verified, binary** (`ios-universal-video-full`, `Avcodec.framework`, `ios-arm64`): it reports "LGPL version 3 or later", and its configure string matches. Its symbols are hidden, so decoders were not counted.

**Outplayer and Filebar**

- **Verified:** neither publishes a configure line, a decoder list or its external libraries.
  - Outplayer's FFmpeg fork holds source only, with no build script.
  - Filebar publishes no license or source page.
- **Inferred:** Outplayer's FFmpeg is n8.1.1. So its native decoders can add nothing to the union in section 3 except `ahx` and the eight ADPCM codecs, and those only if it builds with `--enable-gpl`. Its external libraries are unknown. Filebar's "AV1 decode" entry (2024-11-23) suggests a software AV1 decoder, but the changelog does not name one.

## 3. The union, filtered

### 3.1 The union

The union was computed from the decoder symbols of the five inspected binaries and the configure flags of the two others. It contains 528 decoder names across FFmpeg 6.0 to 8.1.2:

- **517 native decoders of n8.0.1** (Plezy, Airwave). Verified: every native decoder n8.0.1 declares, except hardware wrappers for other platforms, is in both binaries.
- **8 GPL-gated ADPCM decoders** (Streamyfin only, verified).
- **`ayuv`**, present in FFmpeg 6.0 only (NipaPlay, inferred from `--enable-decoders`).
- **`libdav1d`** (every public build) and **`libuavs3d`** (every MPVKit-derived build).

The subset builds (AerioTV, Tentacle iOS, Streamyfin) and the n7.1.1 and 6.0 builds add nothing else.

### 3.2 Mapping onto FFmpeg 9.0 under R8

Section 4 builds FFmpeg 9.0 with a default LGPL-2.1 configure. Comparing the union with that build leaves these differences:

| Union members | Why they are in the union | FFmpeg 9.0 under R8 | Outcome |
|---|---|---|---|
| `adpcm_circus`, `adpcm_ima_escape`, `adpcm_ima_hvqm2`, `adpcm_ima_hvqm4`, `adpcm_ima_magix`, `adpcm_ima_pda`, `adpcm_n64`, `adpcm_psxc` (8 codec IDs of the same names) | Streamyfin's GPL build matches them with `adpcm*` | Present, but `configure` [L3129–3138](https://github.com/FFmpeg/FFmpeg/blob/7adfbe40dcde598f93a6963d2f7b22cd75202ccc/configure#L3129-L3138) gives each `deps="lgpl_gpl"`, and [L4837](https://github.com/FFmpeg/FFmpeg/blob/7adfbe40dcde598f93a6963d2f7b22cd75202ccc/configure#L4837) enables `lgpl_gpl` only with `--enable-gpl` | **Removed: needs `--enable-gpl`.** No other decoder covers these IDs. |
| `sonic` (`AV_CODEC_ID_SONIC`) | every MPVKit-derived build lists it; every all-decoders build from 6.0 to 8.1 has it | Decoder deleted by [`ca1d253`](https://github.com/FFmpeg/FFmpeg/commit/ca1d253621) (2026-03-08, "avcodec/sonic: Remove sonic codecs"). The codec ID and descriptor are kept, with no decoder. | **Removed: no FFmpeg 9 decoder exists.** Not a license reason. |
| `v308`, `v408`, `v410` (n6.0–n8.1), `ayuv` (n6.0) | the all-decoders builds | `v308`, `v408` and `v410` decoders and codec IDs were deleted by [`0438966`](https://github.com/FFmpeg/FFmpeg/commit/0438966d84) (2026-03-09, "Remove FF_API_V408_CODECID", deprecated 2024-10-12). `ayuv` went earlier, in [`9ee59b6`](https://github.com/FFmpeg/FFmpeg/commit/9ee59b63f5) (2024-01-20, "remove deprecated FF_API_AYUV_CODECID"). FFmpeg 9.0 maps all four FourCCs to `AV_CODEC_ID_RAWVIDEO` (`libavformat/riff.c` L244 and L303–305; `libavformat/isom_tags.c` L36–38). | **Kept:** `rawvideo` covers them. |
| `libdav1d`, `libuavs3d` | every public build | Ordinary external libraries, on none of the GPL, nonfree or version3 lists (`configure` L2029–2064; listed at L2085 and L2138) | **Kept** (section 3.3). |

- **Verified, about the ADPCM gating:** commit [`745cb6f`](https://github.com/FFmpeg/FFmpeg/commit/745cb6f8c7ffb957c598d12e83791c9f480a157e) introduced it on 2025-08-25, first released in n8.1, with the message "Put modules added from almpeg under --enable-gpl as suggested by several members of the GA".
  - Its own comment calls these "Files that are marked as LGPL but some developers prefer only building them with --enable-gpl".
  - `libavcodec/adpcm.c` carries the LGPL-2.1-or-later header.
- **Inferred:** a patched `configure` in the public FFmpeg fork could build them without `--enable-gpl`. But FFmpeg gated them at the suggestion of members of its General Assembly, and the commit gives no other reason, so this research treats them as removed. Restoring them is the owner's call.
- **Not in the union:** `webp_anim`, new in FFmpeg 9.0 (`Changelog`: "Animated WebP decoder"), is the only 9.0 decoder outside the union that a default LGPL configure enables on Apple. `ahx` is GPL-gated too, but no player ships it.

### 3.3 External libraries that remain

| Library | Codec ID | FFmpeg 9.0 decoder | License (from its license file) |
|---|---|---|---|
| dav1d | `AV_CODEC_ID_AV1` | `libdav1d` | BSD 2-Clause. [`COPYING`](https://github.com/videolan/dav1d/blob/master/COPYING): "Copyright © 2018-2025, VideoLAN and dav1d authors". Verified. |
| uavs3d | `AV_CODEC_ID_AVS3` | `libuavs3d` | BSD 3-Clause. [`COPYING`](https://github.com/uavs3/uavs3d/blob/master/COPYING): "Copyright (c) 2018-2022 Peking University Shenzhen Graduate School, Peng Cheng Laboratory, Guangdong Bohua UHD Innovation Corporation". Verified. MPVKit's `libuavs3d-build` builds from `https://github.com/uavs3/uavs3d`. |

- **libuavs3d:** AVS3 has no native FFmpeg decoder, so libuavs3d is the only way to cover it.
- **libdav1d:** AV1 also has a native decoder, but see section 3.4.

### 3.4 What the GPL, nonfree and version3 flags bought

- **Verified:** in FFmpeg 9.0's `configure`, no `*_decoder_deps` line names `gpl`, `version3` or `nonfree`. The only license gate on native decoders is `lgpl_gpl`.
- **Verified:** external libraries are license-gated through four lists ([L2029–2064](https://github.com/FFmpeg/FFmpeg/blob/7adfbe40dcde598f93a6963d2f7b22cd75202ccc/configure#L2029-L2064)). The decoder libraries on them are:
  - GPL: libdavs2, the only decoder library on that list;
  - nonfree: libfdk_aac and libmpeghdec;
  - version3: libaribb24, libopencore_amrnb, libopencore_amrwb, and rkmpp (Rockchip hardware, not on Apple);
  - GPLv3: none (the list holds only libsmbclient, a protocol).
- **Verified:** none of the inspected binaries enables any of those decoder libraries.
- **Inferred:** the flags serve components outside this scope:
  - gmp and mbedtls sit on the version3 list;
  - libsmbclient is a GPLv3 protocol (`libsmbclient_protocol_deps="libsmbclient gplv3"`, L4134);
  - the GPL-only filters.
- So dropping all three flags loses the eight ADPCM codecs and nothing else.

### 3.5 Caveats

- **AV1 needs libdav1d in practice.** Verified: `libavcodec/av1dec.c` L668–678 says "the av1 decoder doesn't support native decode" and returns `ENOSYS` without a hardware accelerator. `configure` L3423–3424 makes `av1_videotoolbox_hwaccel` select that decoder. So `AV_CODEC_ID_AV1` counts as covered by `av1`, but software AV1 decoding depends on libdav1d.
- **AudioToolbox wrappers.** Fifteen codec IDs have an `*_at` decoder, which wraps Apple's AudioToolbox (`configure` L3788, `ilbc_at_decoder_deps="audiotoolbox"`). Verified: every one of them also has a software decoder in the 9.0 build, so coverage does not depend on AudioToolbox.

## 4. The codec list for FFmpeg 9.0

**Result.** The set is all native decoders, not a hand-picked subset:

- every decoder that FFmpeg 9.0's `configure` enables by default under LGPL-2.1 on Apple: 514 decoders covering 489 codec IDs, of which `webp_anim` alone is outside the union;
- plus `libdav1d` (a second decoder for `AV_CODEC_ID_AV1`) and `libuavs3d` (adds `AV_CODEC_ID_AVS3`).

**Counts.**

| Type | Codec IDs in the union | Decoders |
|---|---|---|
| Video | 266 | 268, including `libdav1d` and `libuavs3d` |
| Audio | 203 | 225 |
| Subtitle | 20 | 22 |
| **Total** | **489** | **515** |

- **Verified:** `webp_anim` / `AV_CODEC_ID_WEBP_ANIM` is enabled by the same default configure, but no player ships it. With it the totals are 516 decoders and 490 IDs.
- **Verified, how this was measured.** `./configure --list-decoders` on `release/9.0` lists 603 decoders. The macOS build in section 6 enables 514 of them. The other 89 are:
  - 9 decoders gated by `lgpl_gpl`: the 8 ADPCM decoders and `ahx`;
  - 27 external-library wrappers (`lib*`);
  - 53 hardware wrappers for other platforms: `*_cuvid`, `*_qsv`, `*_mediacodec`, `*_v4l2m2m`, `*_rkmpp`, `*_mmal`, `*_amf` and `*_oh`.
- **Inferred, on other Apple targets:** no Apple-native decoder depends on anything beyond zlib, AudioToolbox and the system frameworks. So an iOS or tvOS cross-build enables the same 514.
- **Inferred, how to express it in `configure`:** keep the default decoder set, so no `--disable-decoders`, and add `--enable-libdav1d --enable-libuavs3d`.

The full table is appendix A.

## 5. What could not be verified

- **Closed-source builds:**
  - Outplayer's FFmpeg configure line and external libraries; only the n8.1.1 source fork is public.
  - Filebar's mpv and FFmpeg versions after 0.36.0, and whatever gives it AV1.
  - Every app in the long tail (section 1.2).
- **Engines on Apple:**
  - whether SenPlayer uses KSPlayer's optional `MPVPlayer`;
  - whether VidHub uses libmpv on Apple platforms (it does on Android, secondary);
  - which engine Plex's current iOS and tvOS apps use (secondary reports say not mpv).
- **Which build a listing ships:**
  - Airwave's store build 1.3 is mapped to the MPVKit 1.0.12 pin by file history, because there are no release tags.
  - Tentacle TV's Mac App Store build is mapped to `desktop-v1.40.0`, because the lookup reports only the iOS version.
- **Unexpanded builds:** Tentacle TV's macOS FFmpeg n7.1.1 and NipaPlay's FFmpeg 6.0 decoder sets are inferred from their configure flags, not counted from binaries. Neither can add anything beyond `ayuv`, which section 3.2 covers.
- **Completeness:** no list of App Store apps that embed mpv exists. Apps that ship mpv without saying so on GitHub or in their store text were not found.

## 6. Method

- **Store presence:**
  - `https://itunes.apple.com/lookup?id=<ids>&country=us` gave the version, `currentVersionReleaseDate`, `supportedDevices`, description and release notes.
  - `https://itunes.apple.com/search?term=<name>&entity=software|macSoftware&country=us` was used to show absence.
- **Binaries:** downloaded from the GitHub releases named in section 2. For each `ios-arm64` (and Airwave `tvos-arm64_arm64e`) slice of libavcodec:
  - `strings -a` gave the embedded configure line and `license:` strings;
  - `nm` gave `_ff_<name>_decoder` symbols, intersected with the `ff_<name>_decoder` declarations in `libavcodec/allcodecs.c` of the pinned FFmpeg tag.
- **FFmpeg 9.0 decoder set:** built from `release/9.0` at `7adfbe4` on macOS (Apple M4) with
  `./configure --disable-programs --disable-doc --disable-encoders --disable-muxers --disable-filters --disable-avfilter --disable-avdevice --disable-network`.
  - `configure` reported "License: LGPL version 2.1 or later" and wrote 514 decoders to `libavcodec/codec_list.c`.
  - A small program linked against the built `libavcodec` walked `av_codec_iterate()` for each decoder's media type and `AVCodecID`.
  - `AVCodecID` enum names come from `libavcodec/codec_id.h`.
- **Version diffs:** the decoder declarations in `libavcodec/allcodecs.c` at `n6.0`, `n7.1.1`, `n8.0.1`, `n8.1`, `n8.1.2` and `release/9.0` were compared to find decoders added or removed between the players' FFmpeg versions and 9.0.

## Appendix A. FFmpeg 9.0 decoders in the filtered set, by `AVCodecID`

What is listed:

- Every decoder that a default LGPL-2.1 `configure` of FFmpeg `release/9.0` enables on Apple, plus `libdav1d` and `libuavs3d`. Verified by the build in section 6.
- Decoder names are the `configure` component names, as in `--enable-decoder=<name>`.
- `*_at` decoders wrap AudioToolbox.
- The one decoder outside the union is marked.

### A.1 Video: 267 codec IDs, 269 decoders (both counts include `webp_anim`)

| `AVCodecID` | FFmpeg 9.0 decoders |
|---|---|
| `AV_CODEC_ID_012V` | `zero12v` |
| `AV_CODEC_ID_4XM` | `fourxm` |
| `AV_CODEC_ID_8BPS` | `eightbps` |
| `AV_CODEC_ID_AASC` | `aasc` |
| `AV_CODEC_ID_AGM` | `agm` |
| `AV_CODEC_ID_AIC` | `aic` |
| `AV_CODEC_ID_ALIAS_PIX` | `alias_pix` |
| `AV_CODEC_ID_AMV` | `amv` |
| `AV_CODEC_ID_ANM` | `anm` |
| `AV_CODEC_ID_ANSI` | `ansi` |
| `AV_CODEC_ID_APNG` | `apng` |
| `AV_CODEC_ID_APV` | `apv` |
| `AV_CODEC_ID_ARBC` | `arbc` |
| `AV_CODEC_ID_ARGO` | `argo` |
| `AV_CODEC_ID_ASV1` | `asv1` |
| `AV_CODEC_ID_ASV2` | `asv2` |
| `AV_CODEC_ID_AURA` | `aura` |
| `AV_CODEC_ID_AURA2` | `aura2` |
| `AV_CODEC_ID_AV1` | `av1`, `libdav1d` (external) |
| `AV_CODEC_ID_AVRN` | `avrn` |
| `AV_CODEC_ID_AVRP` | `avrp` |
| `AV_CODEC_ID_AVS` | `avs` |
| `AV_CODEC_ID_AVS3` | `libuavs3d` (external) |
| `AV_CODEC_ID_AVUI` | `avui` |
| `AV_CODEC_ID_BETHSOFTVID` | `bethsoftvid` |
| `AV_CODEC_ID_BFI` | `bfi` |
| `AV_CODEC_ID_BINKVIDEO` | `bink` |
| `AV_CODEC_ID_BINTEXT` | `bintext` |
| `AV_CODEC_ID_BITPACKED` | `bitpacked` |
| `AV_CODEC_ID_BMP` | `bmp` |
| `AV_CODEC_ID_BMV_VIDEO` | `bmv_video` |
| `AV_CODEC_ID_BRENDER_PIX` | `brender_pix` |
| `AV_CODEC_ID_C93` | `c93` |
| `AV_CODEC_ID_CAVS` | `cavs` |
| `AV_CODEC_ID_CDGRAPHICS` | `cdgraphics` |
| `AV_CODEC_ID_CDTOONS` | `cdtoons` |
| `AV_CODEC_ID_CDXL` | `cdxl` |
| `AV_CODEC_ID_CFHD` | `cfhd` |
| `AV_CODEC_ID_CINEPAK` | `cinepak` |
| `AV_CODEC_ID_CLEARVIDEO` | `clearvideo` |
| `AV_CODEC_ID_CLJR` | `cljr` |
| `AV_CODEC_ID_CLLC` | `cllc` |
| `AV_CODEC_ID_CMV` | `eacmv` |
| `AV_CODEC_ID_CPIA` | `cpia` |
| `AV_CODEC_ID_CRI` | `cri` |
| `AV_CODEC_ID_CSCD` | `cscd` |
| `AV_CODEC_ID_CYUV` | `cyuv` |
| `AV_CODEC_ID_DDS` | `dds` |
| `AV_CODEC_ID_DFA` | `dfa` |
| `AV_CODEC_ID_DIRAC` | `dirac` |
| `AV_CODEC_ID_DNXHD` | `dnxhd` |
| `AV_CODEC_ID_DPX` | `dpx` |
| `AV_CODEC_ID_DSICINVIDEO` | `dsicinvideo` |
| `AV_CODEC_ID_DVVIDEO` | `dvvideo` |
| `AV_CODEC_ID_DXA` | `dxa` |
| `AV_CODEC_ID_DXTORY` | `dxtory` |
| `AV_CODEC_ID_DXV` | `dxv` |
| `AV_CODEC_ID_ESCAPE124` | `escape124` |
| `AV_CODEC_ID_ESCAPE130` | `escape130` |
| `AV_CODEC_ID_EXR` | `exr` |
| `AV_CODEC_ID_FFV1` | `ffv1` |
| `AV_CODEC_ID_FFVHUFF` | `ffvhuff` |
| `AV_CODEC_ID_FIC` | `fic` |
| `AV_CODEC_ID_FITS` | `fits` |
| `AV_CODEC_ID_FLASHSV` | `flashsv` |
| `AV_CODEC_ID_FLASHSV2` | `flashsv2` |
| `AV_CODEC_ID_FLIC` | `flic` |
| `AV_CODEC_ID_FLV1` | `flv` |
| `AV_CODEC_ID_FMVC` | `fmvc` |
| `AV_CODEC_ID_FRAPS` | `fraps` |
| `AV_CODEC_ID_FRWU` | `frwu` |
| `AV_CODEC_ID_G2M` | `g2m` |
| `AV_CODEC_ID_GDV` | `gdv` |
| `AV_CODEC_ID_GEM` | `gem` |
| `AV_CODEC_ID_GIF` | `gif` |
| `AV_CODEC_ID_H261` | `h261` |
| `AV_CODEC_ID_H263` | `h263` |
| `AV_CODEC_ID_H263I` | `h263i` |
| `AV_CODEC_ID_H263P` | `h263p` |
| `AV_CODEC_ID_H264` | `h264` |
| `AV_CODEC_ID_HAP` | `hap` |
| `AV_CODEC_ID_HEVC` | `hevc` |
| `AV_CODEC_ID_HNM4_VIDEO` | `hnm4_video` |
| `AV_CODEC_ID_HQX` | `hqx` |
| `AV_CODEC_ID_HQ_HQA` | `hq_hqa` |
| `AV_CODEC_ID_HUFFYUV` | `huffyuv` |
| `AV_CODEC_ID_HYMT` | `hymt` |
| `AV_CODEC_ID_IDCIN` | `idcin` |
| `AV_CODEC_ID_IDF` | `idf` |
| `AV_CODEC_ID_IFF_ILBM` | `iff_ilbm` |
| `AV_CODEC_ID_IMM4` | `imm4` |
| `AV_CODEC_ID_IMM5` | `imm5` |
| `AV_CODEC_ID_INDEO2` | `indeo2` |
| `AV_CODEC_ID_INDEO3` | `indeo3` |
| `AV_CODEC_ID_INDEO4` | `indeo4` |
| `AV_CODEC_ID_INDEO5` | `indeo5` |
| `AV_CODEC_ID_INTERPLAY_VIDEO` | `interplay_video` |
| `AV_CODEC_ID_IPU` | `ipu` |
| `AV_CODEC_ID_JPEG2000` | `jpeg2000` |
| `AV_CODEC_ID_JPEGLS` | `jpegls` |
| `AV_CODEC_ID_JV` | `jv` |
| `AV_CODEC_ID_KGV1` | `kgv1` |
| `AV_CODEC_ID_KMVC` | `kmvc` |
| `AV_CODEC_ID_LAGARITH` | `lagarith` |
| `AV_CODEC_ID_LEAD` | `lead` |
| `AV_CODEC_ID_LOCO` | `loco` |
| `AV_CODEC_ID_LSCR` | `lscr` |
| `AV_CODEC_ID_M101` | `m101` |
| `AV_CODEC_ID_MAD` | `eamad` |
| `AV_CODEC_ID_MAGICYUV` | `magicyuv` |
| `AV_CODEC_ID_MDEC` | `mdec` |
| `AV_CODEC_ID_MEDIA100` | `media100` |
| `AV_CODEC_ID_MIMIC` | `mimic` |
| `AV_CODEC_ID_MJPEG` | `mjpeg` |
| `AV_CODEC_ID_MJPEGB` | `mjpegb` |
| `AV_CODEC_ID_MMVIDEO` | `mmvideo` |
| `AV_CODEC_ID_MOBICLIP` | `mobiclip` |
| `AV_CODEC_ID_MOTIONPIXELS` | `motionpixels` |
| `AV_CODEC_ID_MPEG1VIDEO` | `mpeg1video` |
| `AV_CODEC_ID_MPEG2VIDEO` | `mpeg2video`, `mpegvideo` |
| `AV_CODEC_ID_MPEG4` | `mpeg4` |
| `AV_CODEC_ID_MSA1` | `msa1` |
| `AV_CODEC_ID_MSCC` | `mscc` |
| `AV_CODEC_ID_MSMPEG4V1` | `msmpeg4v1` |
| `AV_CODEC_ID_MSMPEG4V2` | `msmpeg4v2` |
| `AV_CODEC_ID_MSMPEG4V3` | `msmpeg4v3` |
| `AV_CODEC_ID_MSP2` | `msp2` |
| `AV_CODEC_ID_MSRLE` | `msrle` |
| `AV_CODEC_ID_MSS1` | `mss1` |
| `AV_CODEC_ID_MSS2` | `mss2` |
| `AV_CODEC_ID_MSVIDEO1` | `msvideo1` |
| `AV_CODEC_ID_MSZH` | `mszh` |
| `AV_CODEC_ID_MTS2` | `mts2` |
| `AV_CODEC_ID_MV30` | `mv30` |
| `AV_CODEC_ID_MVC1` | `mvc1` |
| `AV_CODEC_ID_MVC2` | `mvc2` |
| `AV_CODEC_ID_MVDV` | `mvdv` |
| `AV_CODEC_ID_MVHA` | `mvha` |
| `AV_CODEC_ID_MWSC` | `mwsc` |
| `AV_CODEC_ID_MXPEG` | `mxpeg` |
| `AV_CODEC_ID_NOTCHLC` | `notchlc` |
| `AV_CODEC_ID_NUV` | `nuv` |
| `AV_CODEC_ID_PAF_VIDEO` | `paf_video` |
| `AV_CODEC_ID_PAM` | `pam` |
| `AV_CODEC_ID_PBM` | `pbm` |
| `AV_CODEC_ID_PCX` | `pcx` |
| `AV_CODEC_ID_PDV` | `pdv` |
| `AV_CODEC_ID_PFM` | `pfm` |
| `AV_CODEC_ID_PGM` | `pgm` |
| `AV_CODEC_ID_PGMYUV` | `pgmyuv` |
| `AV_CODEC_ID_PGX` | `pgx` |
| `AV_CODEC_ID_PHM` | `phm` |
| `AV_CODEC_ID_PHOTOCD` | `photocd` |
| `AV_CODEC_ID_PICTOR` | `pictor` |
| `AV_CODEC_ID_PIXLET` | `pixlet` |
| `AV_CODEC_ID_PNG` | `png` |
| `AV_CODEC_ID_PPM` | `ppm` |
| `AV_CODEC_ID_PRORES` | `prores` |
| `AV_CODEC_ID_PRORES_RAW` | `prores_raw` |
| `AV_CODEC_ID_PROSUMER` | `prosumer` |
| `AV_CODEC_ID_PSD` | `psd` |
| `AV_CODEC_ID_PTX` | `ptx` |
| `AV_CODEC_ID_QDRAW` | `qdraw` |
| `AV_CODEC_ID_QOI` | `qoi` |
| `AV_CODEC_ID_QPEG` | `qpeg` |
| `AV_CODEC_ID_QTRLE` | `qtrle` |
| `AV_CODEC_ID_R10K` | `r10k` |
| `AV_CODEC_ID_R210` | `r210` |
| `AV_CODEC_ID_RADIANCE_HDR` | `hdr` |
| `AV_CODEC_ID_RASC` | `rasc` |
| `AV_CODEC_ID_RAWVIDEO` | `rawvideo` |
| `AV_CODEC_ID_RL2` | `rl2` |
| `AV_CODEC_ID_ROQ` | `roq` |
| `AV_CODEC_ID_RPZA` | `rpza` |
| `AV_CODEC_ID_RSCC` | `rscc` |
| `AV_CODEC_ID_RTV1` | `rtv1` |
| `AV_CODEC_ID_RV10` | `rv10` |
| `AV_CODEC_ID_RV20` | `rv20` |
| `AV_CODEC_ID_RV30` | `rv30` |
| `AV_CODEC_ID_RV40` | `rv40` |
| `AV_CODEC_ID_RV60` | `rv60` |
| `AV_CODEC_ID_SANM` | `sanm` |
| `AV_CODEC_ID_SCPR` | `scpr` |
| `AV_CODEC_ID_SCREENPRESSO` | `screenpresso` |
| `AV_CODEC_ID_SGA_VIDEO` | `sga` |
| `AV_CODEC_ID_SGI` | `sgi` |
| `AV_CODEC_ID_SGIRLE` | `sgirle` |
| `AV_CODEC_ID_SHEERVIDEO` | `sheervideo` |
| `AV_CODEC_ID_SIMBIOSIS_IMX` | `simbiosis_imx` |
| `AV_CODEC_ID_SMACKVIDEO` | `smacker` |
| `AV_CODEC_ID_SMC` | `smc` |
| `AV_CODEC_ID_SMVJPEG` | `smvjpeg` |
| `AV_CODEC_ID_SNOW` | `snow` |
| `AV_CODEC_ID_SP5X` | `sp5x` |
| `AV_CODEC_ID_SPEEDHQ` | `speedhq` |
| `AV_CODEC_ID_SRGC` | `srgc` |
| `AV_CODEC_ID_SUNRAST` | `sunrast` |
| `AV_CODEC_ID_SVQ1` | `svq1` |
| `AV_CODEC_ID_SVQ3` | `svq3` |
| `AV_CODEC_ID_TARGA` | `targa` |
| `AV_CODEC_ID_TARGA_Y216` | `targa_y216` |
| `AV_CODEC_ID_TDSC` | `tdsc` |
| `AV_CODEC_ID_TGQ` | `eatgq` |
| `AV_CODEC_ID_TGV` | `eatgv` |
| `AV_CODEC_ID_THEORA` | `theora` |
| `AV_CODEC_ID_THP` | `thp` |
| `AV_CODEC_ID_TIERTEXSEQVIDEO` | `tiertexseqvideo` |
| `AV_CODEC_ID_TIFF` | `tiff` |
| `AV_CODEC_ID_TMV` | `tmv` |
| `AV_CODEC_ID_TQI` | `eatqi` |
| `AV_CODEC_ID_TRUEMOTION1` | `truemotion1` |
| `AV_CODEC_ID_TRUEMOTION2` | `truemotion2` |
| `AV_CODEC_ID_TRUEMOTION2RT` | `truemotion2rt` |
| `AV_CODEC_ID_TSCC` | `tscc` |
| `AV_CODEC_ID_TSCC2` | `tscc2` |
| `AV_CODEC_ID_TXD` | `txd` |
| `AV_CODEC_ID_ULTI` | `ulti` |
| `AV_CODEC_ID_UTVIDEO` | `utvideo` |
| `AV_CODEC_ID_V210` | `v210` |
| `AV_CODEC_ID_V210X` | `v210x` |
| `AV_CODEC_ID_VB` | `vb` |
| `AV_CODEC_ID_VBLE` | `vble` |
| `AV_CODEC_ID_VBN` | `vbn` |
| `AV_CODEC_ID_VC1` | `vc1` |
| `AV_CODEC_ID_VC1IMAGE` | `vc1image` |
| `AV_CODEC_ID_VCR1` | `vcr1` |
| `AV_CODEC_ID_VIXL` | `xl` |
| `AV_CODEC_ID_VMDVIDEO` | `vmdvideo` |
| `AV_CODEC_ID_VMIX` | `vmix` |
| `AV_CODEC_ID_VMNC` | `vmnc` |
| `AV_CODEC_ID_VNULL` | `vnull` |
| `AV_CODEC_ID_VP3` | `vp3` |
| `AV_CODEC_ID_VP4` | `vp4` |
| `AV_CODEC_ID_VP5` | `vp5` |
| `AV_CODEC_ID_VP6` | `vp6` |
| `AV_CODEC_ID_VP6A` | `vp6a` |
| `AV_CODEC_ID_VP6F` | `vp6f` |
| `AV_CODEC_ID_VP7` | `vp7` |
| `AV_CODEC_ID_VP8` | `vp8` |
| `AV_CODEC_ID_VP9` | `vp9` |
| `AV_CODEC_ID_VQC` | `vqc` |
| `AV_CODEC_ID_VVC` | `vvc` |
| `AV_CODEC_ID_WBMP` | `wbmp` |
| `AV_CODEC_ID_WCMV` | `wcmv` |
| `AV_CODEC_ID_WEBP` | `webp` |
| `AV_CODEC_ID_WEBP_ANIM` | `webp_anim` (new in 9.0, not in the union) |
| `AV_CODEC_ID_WMV1` | `wmv1` |
| `AV_CODEC_ID_WMV2` | `wmv2` |
| `AV_CODEC_ID_WMV3` | `wmv3` |
| `AV_CODEC_ID_WMV3IMAGE` | `wmv3image` |
| `AV_CODEC_ID_WNV1` | `wnv1` |
| `AV_CODEC_ID_WRAPPED_AVFRAME` | `wrapped_avframe` |
| `AV_CODEC_ID_WS_VQA` | `vqa` |
| `AV_CODEC_ID_XAN_WC3` | `xan_wc3` |
| `AV_CODEC_ID_XAN_WC4` | `xan_wc4` |
| `AV_CODEC_ID_XBIN` | `xbin` |
| `AV_CODEC_ID_XBM` | `xbm` |
| `AV_CODEC_ID_XFACE` | `xface` |
| `AV_CODEC_ID_XPM` | `xpm` |
| `AV_CODEC_ID_XWD` | `xwd` |
| `AV_CODEC_ID_Y41P` | `y41p` |
| `AV_CODEC_ID_YLC` | `ylc` |
| `AV_CODEC_ID_YOP` | `yop` |
| `AV_CODEC_ID_YUV4` | `yuv4` |
| `AV_CODEC_ID_ZEROCODEC` | `zerocodec` |
| `AV_CODEC_ID_ZLIB` | `zlib` |
| `AV_CODEC_ID_ZMBV` | `zmbv` |

### A.2 Audio: 203 codec IDs, 225 decoders

| `AVCodecID` | FFmpeg 9.0 decoders |
|---|---|
| `AV_CODEC_ID_8SVX_EXP` | `eightsvx_exp` |
| `AV_CODEC_ID_8SVX_FIB` | `eightsvx_fib` |
| `AV_CODEC_ID_AAC` | `aac`, `aac_at`, `aac_fixed` |
| `AV_CODEC_ID_AAC_LATM` | `aac_latm` |
| `AV_CODEC_ID_AC3` | `ac3`, `ac3_at`, `ac3_fixed` |
| `AV_CODEC_ID_ACELP_KELVIN` | `acelp_kelvin` |
| `AV_CODEC_ID_ADPCM_4XM` | `adpcm_4xm` |
| `AV_CODEC_ID_ADPCM_ADX` | `adpcm_adx` |
| `AV_CODEC_ID_ADPCM_AFC` | `adpcm_afc` |
| `AV_CODEC_ID_ADPCM_AGM` | `adpcm_agm` |
| `AV_CODEC_ID_ADPCM_AICA` | `adpcm_aica` |
| `AV_CODEC_ID_ADPCM_ARGO` | `adpcm_argo` |
| `AV_CODEC_ID_ADPCM_CT` | `adpcm_ct` |
| `AV_CODEC_ID_ADPCM_DTK` | `adpcm_dtk` |
| `AV_CODEC_ID_ADPCM_EA` | `adpcm_ea` |
| `AV_CODEC_ID_ADPCM_EA_MAXIS_XA` | `adpcm_ea_maxis_xa` |
| `AV_CODEC_ID_ADPCM_EA_R1` | `adpcm_ea_r1` |
| `AV_CODEC_ID_ADPCM_EA_R2` | `adpcm_ea_r2` |
| `AV_CODEC_ID_ADPCM_EA_R3` | `adpcm_ea_r3` |
| `AV_CODEC_ID_ADPCM_EA_XAS` | `adpcm_ea_xas` |
| `AV_CODEC_ID_ADPCM_G722` | `adpcm_g722` |
| `AV_CODEC_ID_ADPCM_G726` | `adpcm_g726` |
| `AV_CODEC_ID_ADPCM_G726LE` | `adpcm_g726le` |
| `AV_CODEC_ID_ADPCM_IMA_ACORN` | `adpcm_ima_acorn` |
| `AV_CODEC_ID_ADPCM_IMA_ALP` | `adpcm_ima_alp` |
| `AV_CODEC_ID_ADPCM_IMA_AMV` | `adpcm_ima_amv` |
| `AV_CODEC_ID_ADPCM_IMA_APC` | `adpcm_ima_apc` |
| `AV_CODEC_ID_ADPCM_IMA_APM` | `adpcm_ima_apm` |
| `AV_CODEC_ID_ADPCM_IMA_CUNNING` | `adpcm_ima_cunning` |
| `AV_CODEC_ID_ADPCM_IMA_DAT4` | `adpcm_ima_dat4` |
| `AV_CODEC_ID_ADPCM_IMA_DK3` | `adpcm_ima_dk3` |
| `AV_CODEC_ID_ADPCM_IMA_DK4` | `adpcm_ima_dk4` |
| `AV_CODEC_ID_ADPCM_IMA_EA_EACS` | `adpcm_ima_ea_eacs` |
| `AV_CODEC_ID_ADPCM_IMA_EA_SEAD` | `adpcm_ima_ea_sead` |
| `AV_CODEC_ID_ADPCM_IMA_ISS` | `adpcm_ima_iss` |
| `AV_CODEC_ID_ADPCM_IMA_MOFLEX` | `adpcm_ima_moflex` |
| `AV_CODEC_ID_ADPCM_IMA_MTF` | `adpcm_ima_mtf` |
| `AV_CODEC_ID_ADPCM_IMA_OKI` | `adpcm_ima_oki` |
| `AV_CODEC_ID_ADPCM_IMA_QT` | `adpcm_ima_qt`, `adpcm_ima_qt_at` |
| `AV_CODEC_ID_ADPCM_IMA_RAD` | `adpcm_ima_rad` |
| `AV_CODEC_ID_ADPCM_IMA_SMJPEG` | `adpcm_ima_smjpeg` |
| `AV_CODEC_ID_ADPCM_IMA_SSI` | `adpcm_ima_ssi` |
| `AV_CODEC_ID_ADPCM_IMA_WAV` | `adpcm_ima_wav` |
| `AV_CODEC_ID_ADPCM_IMA_WS` | `adpcm_ima_ws` |
| `AV_CODEC_ID_ADPCM_IMA_XBOX` | `adpcm_ima_xbox` |
| `AV_CODEC_ID_ADPCM_MS` | `adpcm_ms` |
| `AV_CODEC_ID_ADPCM_MTAF` | `adpcm_mtaf` |
| `AV_CODEC_ID_ADPCM_PSX` | `adpcm_psx` |
| `AV_CODEC_ID_ADPCM_SANYO` | `adpcm_sanyo` |
| `AV_CODEC_ID_ADPCM_SBPRO_2` | `adpcm_sbpro_2` |
| `AV_CODEC_ID_ADPCM_SBPRO_3` | `adpcm_sbpro_3` |
| `AV_CODEC_ID_ADPCM_SBPRO_4` | `adpcm_sbpro_4` |
| `AV_CODEC_ID_ADPCM_SWF` | `adpcm_swf` |
| `AV_CODEC_ID_ADPCM_THP` | `adpcm_thp` |
| `AV_CODEC_ID_ADPCM_THP_LE` | `adpcm_thp_le` |
| `AV_CODEC_ID_ADPCM_VIMA` | `adpcm_vima` |
| `AV_CODEC_ID_ADPCM_XA` | `adpcm_xa` |
| `AV_CODEC_ID_ADPCM_XMD` | `adpcm_xmd` |
| `AV_CODEC_ID_ADPCM_YAMAHA` | `adpcm_yamaha` |
| `AV_CODEC_ID_ADPCM_ZORK` | `adpcm_zork` |
| `AV_CODEC_ID_ALAC` | `alac`, `alac_at` |
| `AV_CODEC_ID_AMR_NB` | `amr_nb_at`, `amrnb` |
| `AV_CODEC_ID_AMR_WB` | `amrwb` |
| `AV_CODEC_ID_ANULL` | `anull` |
| `AV_CODEC_ID_APAC` | `apac` |
| `AV_CODEC_ID_APE` | `ape` |
| `AV_CODEC_ID_APTX` | `aptx` |
| `AV_CODEC_ID_APTX_HD` | `aptx_hd` |
| `AV_CODEC_ID_ATRAC1` | `atrac1` |
| `AV_CODEC_ID_ATRAC3` | `atrac3` |
| `AV_CODEC_ID_ATRAC3AL` | `atrac3al` |
| `AV_CODEC_ID_ATRAC3P` | `atrac3p` |
| `AV_CODEC_ID_ATRAC3PAL` | `atrac3pal` |
| `AV_CODEC_ID_ATRAC9` | `atrac9` |
| `AV_CODEC_ID_BINKAUDIO_DCT` | `binkaudio_dct` |
| `AV_CODEC_ID_BINKAUDIO_RDFT` | `binkaudio_rdft` |
| `AV_CODEC_ID_BMV_AUDIO` | `bmv_audio` |
| `AV_CODEC_ID_BONK` | `bonk` |
| `AV_CODEC_ID_CBD2_DPCM` | `cbd2_dpcm` |
| `AV_CODEC_ID_COMFORT_NOISE` | `comfortnoise` |
| `AV_CODEC_ID_COOK` | `cook` |
| `AV_CODEC_ID_DERF_DPCM` | `derf_dpcm` |
| `AV_CODEC_ID_DFPWM` | `dfpwm` |
| `AV_CODEC_ID_DOLBY_E` | `dolby_e` |
| `AV_CODEC_ID_DSD_LSBF` | `dsd_lsbf` |
| `AV_CODEC_ID_DSD_LSBF_PLANAR` | `dsd_lsbf_planar` |
| `AV_CODEC_ID_DSD_MSBF` | `dsd_msbf` |
| `AV_CODEC_ID_DSD_MSBF_PLANAR` | `dsd_msbf_planar` |
| `AV_CODEC_ID_DSICINAUDIO` | `dsicinaudio` |
| `AV_CODEC_ID_DSS_SP` | `dss_sp` |
| `AV_CODEC_ID_DST` | `dst` |
| `AV_CODEC_ID_DTS` | `dca` |
| `AV_CODEC_ID_DVAUDIO` | `dvaudio` |
| `AV_CODEC_ID_EAC3` | `eac3`, `eac3_at` |
| `AV_CODEC_ID_EVRC` | `evrc` |
| `AV_CODEC_ID_FASTAUDIO` | `fastaudio` |
| `AV_CODEC_ID_FFWAVESYNTH` | `ffwavesynth` |
| `AV_CODEC_ID_FLAC` | `flac` |
| `AV_CODEC_ID_FTR` | `ftr` |
| `AV_CODEC_ID_G723_1` | `g723_1` |
| `AV_CODEC_ID_G728` | `g728` |
| `AV_CODEC_ID_G729` | `g729` |
| `AV_CODEC_ID_GREMLIN_DPCM` | `gremlin_dpcm` |
| `AV_CODEC_ID_GSM` | `gsm` |
| `AV_CODEC_ID_GSM_MS` | `gsm_ms`, `gsm_ms_at` |
| `AV_CODEC_ID_HCA` | `hca` |
| `AV_CODEC_ID_HCOM` | `hcom` |
| `AV_CODEC_ID_IAC` | `iac` |
| `AV_CODEC_ID_ILBC` | `ilbc`, `ilbc_at` |
| `AV_CODEC_ID_IMC` | `imc` |
| `AV_CODEC_ID_INTERPLAY_ACM` | `interplay_acm` |
| `AV_CODEC_ID_INTERPLAY_DPCM` | `interplay_dpcm` |
| `AV_CODEC_ID_MACE3` | `mace3` |
| `AV_CODEC_ID_MACE6` | `mace6` |
| `AV_CODEC_ID_METASOUND` | `metasound` |
| `AV_CODEC_ID_MISC4` | `misc4` |
| `AV_CODEC_ID_MLP` | `mlp` |
| `AV_CODEC_ID_MP1` | `mp1`, `mp1_at`, `mp1float` |
| `AV_CODEC_ID_MP2` | `mp2`, `mp2_at`, `mp2float` |
| `AV_CODEC_ID_MP3` | `mp3`, `mp3_at`, `mp3float` |
| `AV_CODEC_ID_MP3ADU` | `mp3adu`, `mp3adufloat` |
| `AV_CODEC_ID_MP3ON4` | `mp3on4`, `mp3on4float` |
| `AV_CODEC_ID_MP4ALS` | `als` |
| `AV_CODEC_ID_MSNSIREN` | `msnsiren` |
| `AV_CODEC_ID_MUSEPACK7` | `mpc7` |
| `AV_CODEC_ID_MUSEPACK8` | `mpc8` |
| `AV_CODEC_ID_NELLYMOSER` | `nellymoser` |
| `AV_CODEC_ID_ON2AVC` | `on2avc` |
| `AV_CODEC_ID_OPUS` | `opus` |
| `AV_CODEC_ID_OSQ` | `osq` |
| `AV_CODEC_ID_PAF_AUDIO` | `paf_audio` |
| `AV_CODEC_ID_PCM_ALAW` | `pcm_alaw`, `pcm_alaw_at` |
| `AV_CODEC_ID_PCM_BLURAY` | `pcm_bluray` |
| `AV_CODEC_ID_PCM_DVD` | `pcm_dvd` |
| `AV_CODEC_ID_PCM_F16LE` | `pcm_f16le` |
| `AV_CODEC_ID_PCM_F24LE` | `pcm_f24le` |
| `AV_CODEC_ID_PCM_F32BE` | `pcm_f32be` |
| `AV_CODEC_ID_PCM_F32LE` | `pcm_f32le` |
| `AV_CODEC_ID_PCM_F64BE` | `pcm_f64be` |
| `AV_CODEC_ID_PCM_F64LE` | `pcm_f64le` |
| `AV_CODEC_ID_PCM_LXF` | `pcm_lxf` |
| `AV_CODEC_ID_PCM_MULAW` | `pcm_mulaw`, `pcm_mulaw_at` |
| `AV_CODEC_ID_PCM_S16BE` | `pcm_s16be` |
| `AV_CODEC_ID_PCM_S16BE_PLANAR` | `pcm_s16be_planar` |
| `AV_CODEC_ID_PCM_S16LE` | `pcm_s16le` |
| `AV_CODEC_ID_PCM_S16LE_PLANAR` | `pcm_s16le_planar` |
| `AV_CODEC_ID_PCM_S24BE` | `pcm_s24be` |
| `AV_CODEC_ID_PCM_S24DAUD` | `pcm_s24daud` |
| `AV_CODEC_ID_PCM_S24LE` | `pcm_s24le` |
| `AV_CODEC_ID_PCM_S24LE_PLANAR` | `pcm_s24le_planar` |
| `AV_CODEC_ID_PCM_S32BE` | `pcm_s32be` |
| `AV_CODEC_ID_PCM_S32LE` | `pcm_s32le` |
| `AV_CODEC_ID_PCM_S32LE_PLANAR` | `pcm_s32le_planar` |
| `AV_CODEC_ID_PCM_S64BE` | `pcm_s64be` |
| `AV_CODEC_ID_PCM_S64LE` | `pcm_s64le` |
| `AV_CODEC_ID_PCM_S8` | `pcm_s8` |
| `AV_CODEC_ID_PCM_S8_PLANAR` | `pcm_s8_planar` |
| `AV_CODEC_ID_PCM_SGA` | `pcm_sga` |
| `AV_CODEC_ID_PCM_U16BE` | `pcm_u16be` |
| `AV_CODEC_ID_PCM_U16LE` | `pcm_u16le` |
| `AV_CODEC_ID_PCM_U24BE` | `pcm_u24be` |
| `AV_CODEC_ID_PCM_U24LE` | `pcm_u24le` |
| `AV_CODEC_ID_PCM_U32BE` | `pcm_u32be` |
| `AV_CODEC_ID_PCM_U32LE` | `pcm_u32le` |
| `AV_CODEC_ID_PCM_U8` | `pcm_u8` |
| `AV_CODEC_ID_PCM_VIDC` | `pcm_vidc` |
| `AV_CODEC_ID_QCELP` | `qcelp` |
| `AV_CODEC_ID_QDM2` | `qdm2`, `qdm2_at` |
| `AV_CODEC_ID_QDMC` | `qdmc`, `qdmc_at` |
| `AV_CODEC_ID_QOA` | `qoa` |
| `AV_CODEC_ID_RALF` | `ralf` |
| `AV_CODEC_ID_RA_144` | `ra_144` |
| `AV_CODEC_ID_RA_288` | `ra_288` |
| `AV_CODEC_ID_RKA` | `rka` |
| `AV_CODEC_ID_ROQ_DPCM` | `roq_dpcm` |
| `AV_CODEC_ID_S302M` | `s302m` |
| `AV_CODEC_ID_SBC` | `sbc` |
| `AV_CODEC_ID_SDX2_DPCM` | `sdx2_dpcm` |
| `AV_CODEC_ID_SHORTEN` | `shorten` |
| `AV_CODEC_ID_SIPR` | `sipr` |
| `AV_CODEC_ID_SIREN` | `siren` |
| `AV_CODEC_ID_SMACKAUDIO` | `smackaud` |
| `AV_CODEC_ID_SOL_DPCM` | `sol_dpcm` |
| `AV_CODEC_ID_SPEEX` | `speex` |
| `AV_CODEC_ID_TAK` | `tak` |
| `AV_CODEC_ID_TRUEHD` | `truehd` |
| `AV_CODEC_ID_TRUESPEECH` | `truespeech` |
| `AV_CODEC_ID_TTA` | `tta` |
| `AV_CODEC_ID_TWINVQ` | `twinvq` |
| `AV_CODEC_ID_VMDAUDIO` | `vmdaudio` |
| `AV_CODEC_ID_VORBIS` | `vorbis` |
| `AV_CODEC_ID_WADY_DPCM` | `wady_dpcm` |
| `AV_CODEC_ID_WAVARC` | `wavarc` |
| `AV_CODEC_ID_WAVPACK` | `wavpack` |
| `AV_CODEC_ID_WESTWOOD_SND1` | `ws_snd1` |
| `AV_CODEC_ID_WMALOSSLESS` | `wmalossless` |
| `AV_CODEC_ID_WMAPRO` | `wmapro` |
| `AV_CODEC_ID_WMAV1` | `wmav1` |
| `AV_CODEC_ID_WMAV2` | `wmav2` |
| `AV_CODEC_ID_WMAVOICE` | `wmavoice` |
| `AV_CODEC_ID_XAN_DPCM` | `xan_dpcm` |
| `AV_CODEC_ID_XMA1` | `xma1` |
| `AV_CODEC_ID_XMA2` | `xma2` |

### A.3 Subtitle: 20 codec IDs, 22 decoders

| `AVCodecID` | FFmpeg 9.0 decoders |
|---|---|
| `AV_CODEC_ID_ASS` | `ass`, `ssa` |
| `AV_CODEC_ID_DVB_SUBTITLE` | `dvbsub` |
| `AV_CODEC_ID_DVD_SUBTITLE` | `dvdsub` |
| `AV_CODEC_ID_EIA_608` | `ccaption` |
| `AV_CODEC_ID_HDMV_PGS_SUBTITLE` | `pgssub` |
| `AV_CODEC_ID_JACOSUB` | `jacosub` |
| `AV_CODEC_ID_MICRODVD` | `microdvd` |
| `AV_CODEC_ID_MOV_TEXT` | `movtext` |
| `AV_CODEC_ID_MPL2` | `mpl2` |
| `AV_CODEC_ID_PJS` | `pjs` |
| `AV_CODEC_ID_REALTEXT` | `realtext` |
| `AV_CODEC_ID_SAMI` | `sami` |
| `AV_CODEC_ID_STL` | `stl` |
| `AV_CODEC_ID_SUBRIP` | `srt`, `subrip` |
| `AV_CODEC_ID_SUBVIEWER` | `subviewer` |
| `AV_CODEC_ID_SUBVIEWER1` | `subviewer1` |
| `AV_CODEC_ID_TEXT` | `text` |
| `AV_CODEC_ID_VPLAYER` | `vplayer` |
| `AV_CODEC_ID_WEBVTT` | `webvtt` |
| `AV_CODEC_ID_XSUB` | `xsub` |
