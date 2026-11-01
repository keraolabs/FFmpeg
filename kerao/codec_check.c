/*
 * Prints av_version_info() and every decoder with its AVCodecID name, one
 * "kerao-codec-check" line each, then an end line with the decoder count.
 * Lines without that prefix come from elsewhere and carry no result.
 */

#include <stdio.h>

#include <libavcodec/avcodec.h>
#include <libavutil/avutil.h>

int main(void)
{
    const AVCodec *codec;
    void *opaque = NULL;
    int decoders = 0;

    printf("kerao-codec-check version %s\n", av_version_info());
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
