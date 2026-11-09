/*
 * This file is part of FFmpeg.
 *
 * FFmpeg is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * FFmpeg is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with FFmpeg; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */

/*
 * stream_read <file> <schedule> [<option>...]
 *
 * Reads file with av_read_frame() and av_read_stream_packet() as the
 * schedule says, then prints every packet the reads returned after the last
 * seek, stream by stream in the order they came, and how each stream ended.
 * The output of a schedule that reads everything equals the output of "p"
 * on an unmodified libavformat.
 *
 * A schedule is steps separated by '/'. A step "s<ms>" seeks every stream to
 * ms milliseconds. Any other step is reads separated by '+', "p" for
 * av_read_frame() and "t<n>" for av_read_stream_packet() on stream n,
 * done in turn until each has ended, or ":<count>" rounds. A read that ends
 * its stream is repeated once and must end it the same way. Every read that
 * fails must leave the packet blank.
 *
 * Options:
 *   noinfo       skip avformat_find_stream_info()
 *   enosys       every stream must refuse av_read_stream_packet() with
 *                AVERROR(ENOSYS) and leave the input position as it was
 *   einval       a stream that does not exist or is discarded must be refused
 *                with AVERROR(EINVAL)
 *   genpts       open with AVFMT_FLAG_GENPTS
 *   ignidx       open with AVFMT_FLAG_IGNIDX
 *   wallclock    open with use_wallclock_as_timestamps
 *   nonseekable  read through an AVIOContext that cannot seek
 *   ioerror=<n>  read through an AVIOContext that fails reads from byte n on
 *   eagain=<n>   read through an AVIOContext whose first read from byte n on
 *                after the file is open returns AVERROR(EAGAIN)
 *   ends         print only how each stream ended
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libavutil/adler32.h"
#include "libavutil/avstring.h"
#include "libavutil/macros.h"
#include "libavutil/bprint.h"
#include "libavutil/error.h"
#include "libavutil/mem.h"

#include "libavformat/avformat.h"
#include "libavformat/avio.h"

#define MAX_STREAMS 8
#define MAX_READS 16
#define IO_BUFFER_SIZE 4096
#define NOT_ENDED 1

typedef struct Input {
    AVIOContext *file;
    int64_t fail_from;
    int64_t again_from;
    int armed;
} Input;

typedef struct Reader {
    AVFormatContext *fmt;
    AVPacket *pkt;
    AVBPrint out[MAX_STREAMS];
    int ended[MAX_STREAMS];
    int failed;
} Reader;

static int input_read(void *opaque, uint8_t *buf, int size)
{
    Input *in = opaque;
    int64_t pos = avio_tell(in->file);

    if (in->armed && in->again_from >= 0 && pos + size > in->again_from) {
        in->again_from = -1;
        return AVERROR(EAGAIN);
    }
    if (in->fail_from >= 0 && pos + size > in->fail_from)
        return AVERROR(EIO);
    return avio_read(in->file, buf, size);
}

static int64_t input_seek(void *opaque, int64_t offset, int whence)
{
    Input *in = opaque;

    return avio_seek(in->file, offset, whence);
}

static const char *status(int ret)
{
    static char buf[AV_ERROR_MAX_STRING_SIZE];
    switch (ret) {
    case NOT_ENDED:            return "not ended";
    case AVERROR_EOF:          return "eof";
    case AVERROR_INVALIDDATA:  return "invalid data";
    case AVERROR(EIO):         return "io error";
    case AVERROR(EAGAIN):      return "again";
    case AVERROR(ENOSYS):      return "enosys";
    default:
        return av_make_error_string(buf, sizeof(buf), ret);
    }
}

static void record(Reader *r, const AVPacket *pkt)
{
    AVBPrint *bp = &r->out[pkt->stream_index];

    if (r->ended[pkt->stream_index] != NOT_ENDED) {
        fprintf(stderr, "stream %d returned a packet after it ended with %s\n",
                pkt->stream_index, status(r->ended[pkt->stream_index]));
        r->failed = 1;
    }

    av_bprintf(bp, "%d, dts %"PRId64", pts %"PRId64", duration %"PRId64", flags 0x%x, size %d, pos %"PRId64", adler 0x%08"PRIx32,
               pkt->stream_index, pkt->dts, pkt->pts, pkt->duration, pkt->flags, pkt->size, pkt->pos,
               (uint32_t)av_adler32_update(0, pkt->data, pkt->size));
    for (int i = 0; i < pkt->side_data_elems; i++) {
        const AVPacketSideData *sd = &pkt->side_data[i];
        av_bprintf(bp, ", side %d size %zu adler 0x%08"PRIx32, sd->type, sd->size,
                   (uint32_t)av_adler32_update(0, sd->data, sd->size));
    }
    av_bprintf(bp, "\n");
}

static void check_blank(Reader *r, int stream, int ret)
{
    const AVPacket *pkt = r->pkt;

    if (pkt->buf || pkt->data || pkt->size || pkt->side_data_elems) {
        fprintf(stderr, "%s read returned %s with a packet that is not blank\n",
                stream < 0 ? "av_read_frame" : "stream", status(ret));
        r->failed = 1;
    }
}

/* Returns 0 after a packet, else the stream's end. */
static int read_once(Reader *r, int stream)
{
    int ret = stream < 0 ? av_read_frame(r->fmt, r->pkt)
                         : av_read_stream_packet(r->fmt, stream, r->pkt);
    if (ret < 0)
        check_blank(r, stream, ret);
    if (ret >= 0) {
        if (stream >= 0 && r->pkt->stream_index != stream) {
            fprintf(stderr, "stream %d read returned a packet of stream %d\n", stream, r->pkt->stream_index);
            r->failed = 1;
        }
        record(r, r->pkt);
        av_packet_unref(r->pkt);
    }
    return ret;
}

static int read_until_end(Reader *r, int stream)
{
    int ret = read_once(r, stream);
    int again;

    if (ret >= 0)
        return ret;
    again = read_once(r, stream);
    if (again != ret) {
        fprintf(stderr, "%s read ended with %s, then returned %s\n",
                stream < 0 ? "av_read_frame" : "stream", status(ret), status(again));
        r->failed = 1;
    }
    return ret;
}

static void reset_output(Reader *r)
{
    for (int i = 0; i < MAX_STREAMS; i++) {
        av_bprint_finalize(&r->out[i], NULL);
        av_bprint_init(&r->out[i], 0, AV_BPRINT_SIZE_UNLIMITED);
        r->ended[i] = NOT_ENDED;
    }
}

static int run_reads(Reader *r, char *step)
{
    int streams[MAX_READS], n = 0, rounds = -1, open;
    unsigned done = 0;
    char *count = strchr(step, ':'), *token, *save = NULL;

    if (count) {
        *count = 0;
        rounds = atoi(count + 1);
    }
    for (token = av_strtok(step, "+", &save); token && n < MAX_READS; token = av_strtok(NULL, "+", &save)) {
        if (token[0] == 'p')
            streams[n++] = -1;
        else if (token[0] == 't' && atoi(token + 1) < (int)r->fmt->nb_streams)
            streams[n++] = atoi(token + 1);
        else
            return AVERROR(EINVAL);
    }
    do {
        open = 0;
        for (int i = 0; i < n; i++) {
            int ret;
            if (done & 1u << i)
                continue;
            ret = read_until_end(r, streams[i]);
            if (ret < 0) {
                done |= 1u << i;
                if (streams[i] >= 0)
                    r->ended[streams[i]] = ret;
                else
                    for (int j = 0; j < MAX_STREAMS; j++)
                        if (r->ended[j] == NOT_ENDED)
                            r->ended[j] = ret;
            } else {
                open = 1;
            }
        }
    } while (open && (rounds < 0 || --rounds > 0));
    return 0;
}

static void check_einval(Reader *r)
{
    int streams[] = { -1, r->fmt->nb_streams, 0 };

    for (int i = 0; i < FF_ARRAY_ELEMS(streams); i++) {
        enum AVDiscard discard = r->fmt->streams[0]->discard;
        int ret;
        if (i == 2)
            r->fmt->streams[0]->discard = AVDISCARD_ALL;
        ret = av_read_stream_packet(r->fmt, streams[i], r->pkt);
        r->fmt->streams[0]->discard = discard;
        check_blank(r, streams[i], ret);
        if (ret != AVERROR(EINVAL)) {
            fprintf(stderr, "stream %d%s: %s, expected EINVAL\n", streams[i], i == 2 ? " discarded" : "", status(ret));
            r->failed = 1;
        }
        av_packet_unref(r->pkt);
    }
}

static int check_enosys(Reader *r)
{
    int64_t pos = avio_tell(r->fmt->pb);

    for (unsigned i = 0; i < r->fmt->nb_streams; i++) {
        int ret = av_read_stream_packet(r->fmt, i, r->pkt);
        check_blank(r, i, ret);
        if (ret != AVERROR(ENOSYS) || avio_tell(r->fmt->pb) != pos) {
            fprintf(stderr, "stream %u: %s at %"PRId64", expected enosys at %"PRId64"\n",
                    i, status(ret), avio_tell(r->fmt->pb), pos);
            r->failed = 1;
        }
        av_packet_unref(r->pkt);
    }
    return 0;
}

int main(int argc, char **argv)
{
    Reader r = { 0 };
    Input in = { .fail_from = -1, .again_from = -1 };
    AVIOContext *pb = NULL;
    AVDictionary *opts = NULL;
    char *schedule, *step, *save = NULL;
    int info = 1, enosys = 0, einval = 0, seekable = 1, custom = 0, ends_only = 0, ret;

    if (argc < 3) {
        fprintf(stderr, "usage: %s <file> <schedule> [<option>...]\n", argv[0]);
        return 2;
    }
    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "noinfo"))
            info = 0;
        else if (!strcmp(argv[i], "enosys"))
            enosys = 1;
        else if (!strcmp(argv[i], "einval"))
            einval = 1;
        else if (!strcmp(argv[i], "genpts"))
            av_dict_set(&opts, "fflags", "+genpts", 0);
        else if (!strcmp(argv[i], "ignidx"))
            av_dict_set(&opts, "fflags", "+ignidx", 0);
        else if (!strcmp(argv[i], "wallclock"))
            av_dict_set(&opts, "use_wallclock_as_timestamps", "1", 0);
        else if (!strcmp(argv[i], "nonseekable"))
            seekable = 0, custom = 1;
        else if (!strncmp(argv[i], "ioerror=", 8))
            in.fail_from = atoll(argv[i] + 8), custom = 1;
        else if (!strncmp(argv[i], "eagain=", 7))
            in.again_from = atoll(argv[i] + 7), custom = 1;
        else if (!strcmp(argv[i], "ends"))
            ends_only = 1;
        else {
            fprintf(stderr, "unknown option %s\n", argv[i]);
            return 2;
        }
    }

    r.fmt = avformat_alloc_context();
    r.pkt = av_packet_alloc();
    if (!r.fmt || !r.pkt)
        return 1;
    if (custom) {
        uint8_t *buf = av_malloc(IO_BUFFER_SIZE);
        if (!buf || avio_open(&in.file, argv[1], AVIO_FLAG_READ) < 0)
            return 1;
        pb = avio_alloc_context(buf, IO_BUFFER_SIZE, 0, &in, input_read, NULL,
                                seekable ? input_seek : NULL);
        if (!pb)
            return 1;
        pb->seekable = seekable ? AVIO_SEEKABLE_NORMAL : 0;
        r.fmt->pb = pb;
    }
    ret = avformat_open_input(&r.fmt, argv[1], NULL, &opts);
    av_dict_free(&opts);
    if (ret < 0) {
        printf("open: %s\n", status(ret));
        return 0;
    }
    if (info && (ret = avformat_find_stream_info(r.fmt, NULL)) < 0) {
        printf("find_stream_info: %s\n", status(ret));
        return 0;
    }
    if (r.fmt->nb_streams > MAX_STREAMS)
        return 1;
    reset_output(&r);
    if (enosys)
        check_enosys(&r);
    if (einval)
        check_einval(&r);
    in.armed = 1;

    schedule = av_strdup(argv[2]);
    for (step = av_strtok(schedule, "/", &save); step; step = av_strtok(NULL, "/", &save)) {
        if (step[0] == 's') {
            int64_t ts = atoll(step + 1) * (AV_TIME_BASE / 1000);
            if ((ret = avformat_seek_file(r.fmt, -1, INT64_MIN, ts, ts, 0)) < 0) {
                printf("seek: %s\n", status(ret));
                return 0;
            }
            reset_output(&r);
        } else if (run_reads(&r, step) < 0) {
            fprintf(stderr, "bad step %s\n", step);
            return 2;
        }
    }

    for (unsigned i = 0; i < r.fmt->nb_streams; i++) {
        if (!ends_only)
            printf("stream %u\n%s", i, r.out[i].str);
        printf("end %u: %s\n", i, status(r.ended[i]));
        av_bprint_finalize(&r.out[i], NULL);
    }
    av_free(schedule);
    av_packet_free(&r.pkt);
    avformat_close_input(&r.fmt);
    if (pb) {
        av_freep(&pb->buffer);
        avio_context_free(&pb);
    }
    avio_closep(&in.file);
    return r.failed;
}
