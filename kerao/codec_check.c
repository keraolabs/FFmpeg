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
 * Prints av_version_info(), two stream-read lines and every decoder with its
 * AVCodecID name, one "kerao-codec-check" line each, then an end line with the
 * decoder count. Lines without that prefix come from elsewhere and carry no
 * result.
 *
 * "stream-read plain <video packets> <video CRC> <audio packets> <audio CRC>
 * <end>" is what av_read_frame() alone returns of stream_read_media.
 * "stream-read stream <audio packets> <audio CRC> <end> <video packets>
 * <video CRC> <audio packets> <end>" is what av_read_stream_packet() of
 * the audio until it ends returns, then what av_read_frame() returns after it.
 * An end is "eof" or "error" and the AVERROR code; a CRC covers each packet's
 * pts, dts, duration, flags, size and data.
 */

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/crc.h>
#include <libavutil/mem.h>

#include "stream_read_media.h"

#define STREAMS 2
#define IO_BUFFER_SIZE 4096

typedef struct Media {
    int64_t pos;
} Media;

static int media_read(void *opaque, uint8_t *buf, int size)
{
    Media *media = opaque;
    int64_t left = (int64_t)sizeof(stream_read_media) - media->pos;

    if (left <= 0)
        return AVERROR_EOF;
    if (size > left)
        size = left;
    memcpy(buf, stream_read_media + media->pos, size);
    media->pos += size;
    return size;
}

static int64_t media_seek(void *opaque, int64_t offset, int whence)
{
    Media *media = opaque;

    switch (whence & ~AVSEEK_FORCE) {
    case AVSEEK_SIZE: return sizeof(stream_read_media);
    case SEEK_SET:    media->pos = offset; break;
    case SEEK_CUR:    media->pos += offset; break;
    case SEEK_END:    media->pos = sizeof(stream_read_media) + offset; break;
    default:          return AVERROR(EINVAL);
    }
    return media->pos;
}

static uint32_t packet_crc(uint32_t crc, const AVPacket *pkt)
{
    const AVCRC *table = av_crc_get_table(AV_CRC_32_IEEE_LE);
    int64_t fields[] = { pkt->pts, pkt->dts, pkt->duration, pkt->flags, pkt->size };

    crc = av_crc(table, crc, (const uint8_t *)fields, sizeof(fields));
    return av_crc(table, crc, pkt->data, pkt->size);
}

static const char *status(int ret, char *buf, size_t size)
{
    if (ret == AVERROR_EOF)
        return "eof";
    snprintf(buf, size, "error%d", ret);
    return buf;
}

typedef struct Reads {
    int packets[STREAMS];
    uint32_t crc[STREAMS];
    int end;
} Reads;

static void add(Reads *reads, const AVPacket *pkt)
{
    reads->crc[pkt->stream_index] = packet_crc(reads->crc[pkt->stream_index], pkt);
    reads->packets[pkt->stream_index]++;
}

/* Returns < 0 if stream_read_media can't be opened. */
static int read_media(int stream_first, Reads *stream, Reads *plain)
{
    Media media = { 0 };
    AVFormatContext *fmt = avformat_alloc_context();
    AVPacket *pkt = av_packet_alloc();
    uint8_t *buffer = av_malloc(IO_BUFFER_SIZE);
    AVIOContext *pb = NULL;
    int ret = AVERROR(ENOMEM);

    if (buffer)
        pb = avio_alloc_context(buffer, IO_BUFFER_SIZE, 0, &media, media_read, NULL, media_seek);
    if (fmt && pkt && pb) {
        fmt->pb = pb;
        ret = avformat_open_input(&fmt, NULL, NULL, NULL);
    }
    if (ret >= 0 && fmt->nb_streams != STREAMS)
        ret = AVERROR_INVALIDDATA;
    while (ret >= 0 && stream_first && !stream->end) {
        int err = av_read_stream_packet(fmt, 1, pkt);
        if (err < 0)
            stream->end = err;
        else if (pkt->stream_index != 1)
            stream->end = AVERROR_BUG;
        else
            add(stream, pkt);
        av_packet_unref(pkt);
    }
    while (ret >= 0 && !plain->end) {
        int err = av_read_frame(fmt, pkt);
        if (err < 0)
            plain->end = err;
        else
            add(plain, pkt);
        av_packet_unref(pkt);
    }

    avformat_close_input(&fmt);
    av_packet_free(&pkt);
    if (pb)
        av_freep(&pb->buffer);
    else
        av_free(buffer);
    avio_context_free(&pb);
    return ret;
}

static void stream_read(void)
{
    Reads plain = { 0 }, stream = { 0 }, after = { 0 };
    char end[3][16];
    int ret = read_media(0, NULL, &plain);

    if (ret >= 0)
        ret = read_media(1, &stream, &after);
    if (ret < 0) {
        printf("kerao-codec-check stream-read open %s\n", status(ret, end[0], sizeof(end[0])));
        return;
    }
    printf("kerao-codec-check stream-read plain %d %08"PRIx32" %d %08"PRIx32" %s\n",
           plain.packets[0], plain.crc[0], plain.packets[1], plain.crc[1],
           status(plain.end, end[0], sizeof(end[0])));
    printf("kerao-codec-check stream-read stream %d %08"PRIx32" %s %d %08"PRIx32" %d %s\n",
           stream.packets[1], stream.crc[1], status(stream.end, end[1], sizeof(end[1])),
           after.packets[0], after.crc[0], after.packets[1],
           status(after.end, end[2], sizeof(end[2])));
}

int main(void)
{
    const AVCodec *codec;
    void *opaque = NULL;
    int decoders = 0;

    printf("kerao-codec-check version %s\n", av_version_info());
    stream_read();
    while ((codec = av_codec_iterate(&opaque))) {
        if (!av_codec_is_decoder(codec))
            continue;
        printf("kerao-codec-check decoder %s %s\n", codec->name,
               avcodec_get_name(codec->id));
        decoders++;
    }
    printf("kerao-codec-check end %d\n", decoders);
    return fflush(stdout) == 0 ? 0 : 1;
}
