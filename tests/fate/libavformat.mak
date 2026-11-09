#FATE_LIBAVFORMAT-$(HAVE_PTHREADS) += fate-async
#fate-async: libavformat/tests/async$(EXESUF)
#fate-async: CMD = run libavformat/tests/async

FATE_LIBAVFORMAT += fate-mkdir
fate-mkdir: libavformat/tests/mkdir$(EXESUF)
fate-mkdir: CMD = run libavformat/tests/mkdir$(EXESUF)
fate-mkdir: CMP = null

FATE_LIBAVFORMAT += fate-rename
fate-rename: libavformat/tests/rename$(EXESUF)
fate-rename: CMD = run libavformat/tests/rename$(EXESUF)
fate-rename: CMP = null

FATE_LIBAVFORMAT-$(CONFIG_NETWORK) += fate-noproxy
fate-noproxy: libavformat/tests/noproxy$(EXESUF)
fate-noproxy: CMD = run libavformat/tests/noproxy$(EXESUF)

FATE_LIBAVFORMAT-$(CONFIG_FFRTMPCRYPT_PROTOCOL) += fate-rtmpdh
fate-rtmpdh: libavformat/tests/rtmpdh$(EXESUF)
fate-rtmpdh: CMD = run libavformat/tests/rtmpdh$(EXESUF)

FATE_LIBAVFORMAT-$(CONFIG_SRTP) += fate-srtp
fate-srtp: libavformat/tests/srtp$(EXESUF)
fate-srtp: CMD = run libavformat/tests/srtp$(EXESUF)

FATE_LIBAVFORMAT-yes += fate-url
fate-url: libavformat/tests/url$(EXESUF)
fate-url: CMD = run libavformat/tests/url$(EXESUF)

FATE_LIBAVFORMAT-$(call ALLYES, MP4_MUXER ISMV_MUXER) += fate-movenc
fate-movenc: libavformat/tests/movenc$(EXESUF)
fate-movenc: CMD = run libavformat/tests/movenc$(EXESUF)

FATE_LIBAVFORMAT-$(CONFIG_IMF_DEMUXER) += fate-imf
fate-imf: libavformat/tests/imf$(EXESUF)
fate-imf: CMD = run libavformat/tests/imf$(EXESUF)

FATE_LIBAVFORMAT += fate-seek_utils
fate-seek_utils: libavformat/tests/seek_utils$(EXESUF)
fate-seek_utils: CMD = run libavformat/tests/seek_utils$(EXESUF)
fate-seek_utils: CMP = null

# fate-stream-read-<name> reads stream-read/<file> of the samples with libavformat/tests/stream_read;
# kerao/stream_read_tests.py writes this block and the refs.

FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-plain
fate-stream-read-interleaved-plain: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-plain: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 p
fate-stream-read-interleaved-plain: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-video
fate-stream-read-interleaved-video: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-video: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t0/p
fate-stream-read-interleaved-video: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-audio
fate-stream-read-interleaved-audio: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-audio: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1/p
fate-stream-read-interleaved-audio: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-alternate
fate-stream-read-interleaved-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1+p
fate-stream-read-interleaved-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-both
fate-stream-read-interleaved-both: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-both: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1+t0
fate-stream-read-interleaved-both: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-noinfo
fate-stream-read-interleaved-noinfo: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-noinfo: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1+t0+p noinfo
fate-stream-read-interleaved-noinfo: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved-noinfo
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-interleaved-eagain
fate-stream-read-interleaved-eagain: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-interleaved-eagain: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1/t0 eagain=20000 ends
fate-stream-read-interleaved-eagain: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved-eagain
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-late
fate-stream-read-audio-late: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-late: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-late.mp4 t1+p
fate-stream-read-audio-late: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-late
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-late-first
fate-stream-read-audio-late-first: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-late-first: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-late.mp4 t1/p
fate-stream-read-audio-late-first: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-late
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-early-end
fate-stream-read-audio-early-end: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-early-end: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-early-end.mp4 t1/p
fate-stream-read-audio-early-end: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-early-end
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-early-end-alternate
fate-stream-read-audio-early-end-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-early-end-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-early-end.mp4 t1+p
fate-stream-read-audio-early-end-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-early-end
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-early-end-past-end
fate-stream-read-audio-early-end-past-end: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-early-end-past-end: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-early-end.mp4 s7000/t1+p
fate-stream-read-audio-early-end-past-end: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-early-end-s7000
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-early-end-seek-back
fate-stream-read-audio-early-end-seek-back: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-early-end-seek-back: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-early-end.mp4 t1/p:20/s0/t1+p
fate-stream-read-audio-early-end-seek-back: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-early-end-s0
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-early-end-eagain
fate-stream-read-audio-early-end-eagain: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-early-end-eagain: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-early-end.mp4 t1/p/t1 eagain=45000 ends
fate-stream-read-audio-early-end-eagain: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-early-end-eagain
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-audio-gap
fate-stream-read-audio-gap: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-audio-gap: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/audio-gap.mp4 t1+p
fate-stream-read-audio-gap: REF = $(SRC_PATH)/tests/ref/fate/stream-read-audio-gap
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-b-frames
fate-stream-read-b-frames: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-b-frames: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/b-frames.mp4 t0+p
fate-stream-read-b-frames: REF = $(SRC_PATH)/tests/ref/fate/stream-read-b-frames
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-b-frames-audio
fate-stream-read-b-frames-audio: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-b-frames-audio: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/b-frames.mp4 t1/p
fate-stream-read-b-frames-audio: REF = $(SRC_PATH)/tests/ref/fate/stream-read-b-frames
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-ac3
fate-stream-read-parser-ac3: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-ac3: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 t1/p
fate-stream-read-parser-ac3: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-eac3
fate-stream-read-parser-eac3: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-eac3: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 t2/t1/p
fate-stream-read-parser-eac3: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-alternate
fate-stream-read-parser-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 t2+t1+p
fate-stream-read-parser-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-video
fate-stream-read-parser-video: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-video: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 t0/p
fate-stream-read-parser-video: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-noinfo
fate-stream-read-parser-noinfo: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-noinfo: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 t2+p noinfo
fate-stream-read-parser-noinfo: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams-noinfo
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-queued
fate-stream-read-parser-queued: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-queued: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 p+t2 noinfo
fate-stream-read-parser-queued: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams-noinfo
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-parser-queued-info
fate-stream-read-parser-queued-info: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-parser-queued-info: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/parser-streams.mp4 p+t2
fate-stream-read-parser-queued-info: REF = $(SRC_PATH)/tests/ref/fate/stream-read-parser-streams
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-indexed
fate-stream-read-frag-indexed: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-indexed: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-indexed.mp4 t1+p
fate-stream-read-frag-indexed: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-indexed
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-video
fate-stream-read-frag-sidx-video: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-video: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 t0/p
fate-stream-read-frag-sidx-video: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-alternate
fate-stream-read-frag-sidx-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 t1+p
fate-stream-read-frag-sidx-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-both
fate-stream-read-frag-sidx-both: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-both: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 t0+t1
fate-stream-read-frag-sidx-both: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-seek
fate-stream-read-frag-sidx-seek: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-seek: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 t0/s3000/t0+p
fate-stream-read-frag-sidx-seek: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-s3000
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-hole-plain
fate-stream-read-frag-sidx-hole-plain: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-hole-plain: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 s9000/p:5/s3000/p noinfo
fate-stream-read-frag-sidx-hole-plain: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-hole
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-hole-video
fate-stream-read-frag-sidx-hole-video: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-hole-video: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 s9000/p:5/s3000/t0/p noinfo
fate-stream-read-frag-sidx-hole-video: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-hole
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-hole-audio
fate-stream-read-frag-sidx-hole-audio: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-hole-audio: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 s9000/p:5/s3000/t1/p noinfo
fate-stream-read-frag-sidx-hole-audio: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-hole
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-hole-alternate
fate-stream-read-frag-sidx-hole-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-hole-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 s9000/p:5/s3000/t0+p noinfo
fate-stream-read-frag-sidx-hole-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-hole
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-hole-both
fate-stream-read-frag-sidx-hole-both: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-hole-both: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 s9000/t0:5/s3000/t1+t0 noinfo
fate-stream-read-frag-sidx-hole-both: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-hole
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-ioerror
fate-stream-read-frag-sidx-ioerror: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-ioerror: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx.mp4 t0+p ioerror=40000 ends
fate-stream-read-frag-sidx-ioerror: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-ioerror
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-audio-late
fate-stream-read-frag-sidx-audio-late: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-audio-late: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx-audio-late.mp4 t1+p
fate-stream-read-frag-sidx-audio-late: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-audio-late
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-audio-late-first
fate-stream-read-frag-sidx-audio-late-first: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-audio-late-first: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx-audio-late.mp4 t1/p
fate-stream-read-frag-sidx-audio-late-first: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-audio-late
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-audio-early-end
fate-stream-read-frag-sidx-audio-early-end: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-audio-early-end: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx-audio-early-end.mp4 t1/p
fate-stream-read-frag-sidx-audio-early-end: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-audio-early-end
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-frag-sidx-audio-early-end-alternate
fate-stream-read-frag-sidx-audio-early-end-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-frag-sidx-audio-early-end-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-sidx-audio-early-end.mp4 t1+p
fate-stream-read-frag-sidx-audio-early-end-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-sidx-audio-early-end
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-mixed-lazy-video
fate-stream-read-mixed-lazy-video: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-mixed-lazy-video: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/mixed-lazy.mp4 t0/p
fate-stream-read-mixed-lazy-video: REF = $(SRC_PATH)/tests/ref/fate/stream-read-mixed-lazy
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-mixed-lazy-alternate
fate-stream-read-mixed-lazy-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-mixed-lazy-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/mixed-lazy.mp4 t0+p
fate-stream-read-mixed-lazy-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-mixed-lazy
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-faststart
fate-stream-read-faststart: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-faststart: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/faststart.mp4 t1+p
fate-stream-read-faststart: REF = $(SRC_PATH)/tests/ref/fate/stream-read-faststart
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-cover-open
fate-stream-read-cover-open: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-cover-open: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/cover.mp4 t0/p noinfo
fate-stream-read-cover-open: REF = $(SRC_PATH)/tests/ref/fate/stream-read-cover-noinfo
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-cover-open-picture
fate-stream-read-cover-open-picture: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-cover-open-picture: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/cover.mp4 t1/p noinfo
fate-stream-read-cover-open-picture: REF = $(SRC_PATH)/tests/ref/fate/stream-read-cover-noinfo
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-cover-seek
fate-stream-read-cover-seek: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-cover-seek: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/cover.mp4 s0/t0/p
fate-stream-read-cover-seek: REF = $(SRC_PATH)/tests/ref/fate/stream-read-cover-s0
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-cover-seek-alternate
fate-stream-read-cover-seek-alternate: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-cover-seek-alternate: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/cover.mp4 s0/t0+t1+p
fate-stream-read-cover-seek-alternate: REF = $(SRC_PATH)/tests/ref/fate/stream-read-cover-s0
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-einval
fate-stream-read-einval: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-einval: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 t1+p einval
fate-stream-read-einval: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-enosys-genpts
fate-stream-read-enosys-genpts: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-genpts: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 p genpts enosys
fate-stream-read-enosys-genpts: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved-genpts
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-enosys-ignidx
fate-stream-read-enosys-ignidx: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-ignidx: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 p ignidx enosys
fate-stream-read-enosys-ignidx: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved-ignidx
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-enosys-wallclock
fate-stream-read-enosys-wallclock: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-wallclock: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/interleaved.mp4 p wallclock enosys ends
fate-stream-read-enosys-wallclock: REF = $(SRC_PATH)/tests/ref/fate/stream-read-interleaved-ends
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-enosys-nonseekable
fate-stream-read-enosys-nonseekable: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-nonseekable: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/frag-indexed.mp4 p nonseekable enosys
fate-stream-read-enosys-nonseekable: REF = $(SRC_PATH)/tests/ref/fate/stream-read-frag-indexed-nonseekable
FATE_STREAM_READ-$(call ALLYES, MOV_DEMUXER AC3_PARSER FILE_PROTOCOL) += fate-stream-read-enosys-encrypted
fate-stream-read-enosys-encrypted: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-encrypted: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/encrypted.mp4 p enosys
fate-stream-read-enosys-encrypted: REF = $(SRC_PATH)/tests/ref/fate/stream-read-encrypted
FATE_STREAM_READ-$(call ALLYES, MATROSKA_DEMUXER FILE_PROTOCOL) += fate-stream-read-enosys-matroska
fate-stream-read-enosys-matroska: libavformat/tests/stream_read$(EXESUF)
fate-stream-read-enosys-matroska: CMD = run libavformat/tests/stream_read$(EXESUF) $(TARGET_SAMPLES)/stream-read/enosys.mkv p enosys
fate-stream-read-enosys-matroska: REF = $(SRC_PATH)/tests/ref/fate/stream-read-enosys

FATE_STREAM_READ += $(FATE_STREAM_READ-yes)
FATE_EXTERN-$(CONFIG_AVFORMAT) += $(FATE_STREAM_READ)
fate-stream-read: $(FATE_STREAM_READ)

FATE_LIBAVFORMAT += $(FATE_LIBAVFORMAT-yes)
FATE-$(CONFIG_AVFORMAT) += $(FATE_LIBAVFORMAT)
fate-libavformat: $(FATE_LIBAVFORMAT)
