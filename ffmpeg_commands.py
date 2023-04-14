import copy
from loguru import logger

from fastll_stream import Stream

# noinspection SpellCheckingInspection
ffmpeg_gen_video_command = \
    ["ffmpeg",  # 0
     "-hide_banner",  # 1
     "-re",  # 2
     "-f",  # 3
     "lavfi",  # 4
     "-i",  # 5
     "testsrc2=size=320x240:rate=30",  # 6
     "-pix_fmt",  # 7
     "yuv420p",  # 8
     "-c:v",  # 9
     "libx264",  # 10
     "-x264opts",  # 11
     "keyint=15:min-keyint=15:scenecut=-1",  # 12
     "-tune",  # 13
     "zerolatency",  # 14
     "-profile:v",  # 15
     "baseline",  # 16
     "-preset",  # 17
     "veryfast",  # 18
     "-bf",  # 19
     "0",  # 20
     "-refs",  # 21
     "3",  # 22
     "-b:v",  # 23
     "500k",  # 24
     "-bufsize",  # 25
     "500k",  # 26
     "-vf",  # 27
     "drawtext=fontfile='/Library/Fonts/Arial.ttf':text='%{localtime}"
     ":box=1:fontcolor=black:boxcolor=white:fontsize=100':x=40:y=400'",  # 28
     "-utc_timing_url",  # 29
     "https://time.akamai.com/?iso",  # 30
     "-use_timeline",  # 31
     "0",  # 32
     "-format_options",  # 33
     "movflags=cmaf",  # 34
     "-frag_type",  # 35
     "duration",  # 36
     "-adaptation_sets",  # 37
     "id=0, seg_duration=1, frag_duration=0.1, streams=v",  # 38
     "-streaming",  # 39
     "1",  # 40
     "-ldash",  # 41
     "1",  # 42
     "-export_side_data",  # 43
     "prft",  # 44
     "-write_prft",  # 45
     "1",  # 46
     "-target_latency",  # 47
     "0.5",  # 48
     "-window_size",  # 49
     "5",  # 50
     "-extra_window_size",  # 51
     "10",  # 52
     "-remove_at_exit",  # 53
     "1",  # 54
     "-method",  # 55
     "PUT",  # 56
     "-f",  # 57
     "dash",  # 58
     "http://fakehost/fakestream/manifest.mpd"  # 59
     ]
ffmpeg_gen_video_command_time_server = "{http_url}/isotime"
ffmpeg_gen_video_command_output = "{http_url}/{stream}/manifest.mpd"
# noinspection SpellCheckingInspection
ffmpeg_rtsp_video_command = \
    ["ffmpeg",  # 0
     "-fflags",
     "nobuffer",
     "-flags",
     "low_delay",
     "-avioflags",
     "direct",
     "-f",
     "rtsp",
     "-i",
     "rtsp://fakeuser:fakepassword@fakeshost:554/axis-media/media.amp",  # 10
     "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX mapping and qualities",
     "-utc_timing_url",
     "https://time.akamai.com/?iso",
     "-use_timeline",
     "0",
     "-use_template",
     "1",
     "-format_options",
     "movflags=cmaf",
     "-frag_type",  # 20
     "duration",
     "-adaptation_sets",
     "id=0, seg_duration=X, frag_duration=X.X, streams=v",
     "-streaming",
     "1",
     "-ldash",
     "1",
     "-export_side_data",
     "prft",
     "-write_prft",  # 30
     "1",
     "-target_latency",
     "X.X",
     "-window_size",
     "10",
     "-extra_window_size",
     "120",
     "-remove_at_exit",
     "1",
     "-method",  # 40
     "PUT",
     "-f",
     "dash",
     "http://fakehost/fakestream/manifest.mpd"  # 44
     ]

ffmpeg_rtsp_video_fps = "fps={fps}, scale={width}:-2"
# noinspection SpellCheckingInspection
# ffmpeg_rtsp_video_x264opts = "keyint={fps}:min-keyint={fps}:scenecut=-1"
ffmpeg_rtsp_video_bitrate = "{bitrate}k"
ffmpeg_rtsp_video_time_server = "{http_url}/isotime"
ffmpeg_rtsp_video_segmentation = "id=0,streams=v,seg_duration={seg_duration},frag_duration={frag_duration}"
# ffmpeg_rtsp_video_segmentation = "id=0,streams=v"
ffmpeg_rtsp_video_target_latency = "{latency}"
ffmpeg_rtsp_video_command_output = "{http_url}/{stream}/manifest.mpd"

ffmpeg_rtsp_video_map_v_stream_param = "-map"
ffmpeg_rtsp_video_map_v_stream_option = "0:v:0"

ffmpeg_rtsp_video_bitrate_param = "-b:v:{index}"
ffmpeg_rtsp_video_bitrate_option = "{bitrate}k"

ffmpeg_rtsp_video_buff_size_param = "-bufsize:v:{index}"
ffmpeg_rtsp_video_buff_size_option = "{bitrate}k"

ffmpeg_rtsp_video_filter_param = "-filter:v:{index}"
ffmpeg_rtsp_video_filter_option = "fps={fps},scale={width}:-2"

ffmpeg_rtsp_video_codec_param = "-c:v:{index}"
ffmpeg_rtsp_video_codec_option = "libx264"

ffmpeg_rtsp_video_x264opts_param = "-x264opts:v:{index}"
ffmpeg_rtsp_video_x264opts_option = "keyint={fps}:min-keyint={fps}:scenecut=-1"

ffmpeg_rtsp_video_tune_param = "-tune:v:{index}"
ffmpeg_rtsp_video_tune_option = "zerolatency"

ffmpeg_rtsp_video_profile_param = "-profile:v:{index}"
ffmpeg_rtsp_video_profile_option = "baseline"

ffmpeg_rtsp_video_preset_param = "-preset:v:{index}"
ffmpeg_rtsp_video_preset_option = "veryfast"

ffmpeg_rtsp_video_b_frames_param = "-bf:v:{index}"
ffmpeg_rtsp_video_b_frames_option = "0"

ffmpeg_rtsp_video_refs_param = "-refs:v:{index}"
ffmpeg_rtsp_video_refs_option = "0"


def ffmpeg_command(http_url: str, stream: Stream):
    if stream.type == "GEN":
        command = copy.deepcopy(ffmpeg_gen_video_command)
        command[30] = ffmpeg_gen_video_command_time_server.format(http_url=http_url)
        command[59] = ffmpeg_gen_video_command_output.format(http_url=http_url, stream=stream.name)
        return command

    if stream.type == "RTSP":
        command = copy.deepcopy(ffmpeg_rtsp_video_command)
        # input stream
        command[10] = stream.input

        # command[12] = ffmpeg_rtsp_video_fps.format(fps=stream.frame_rate, width=stream.width)
        # command[15] = ffmpeg_rtsp_video_x264opts.format(fps=stream.intra_interval)
        # command[30] = ffmpeg_rtsp_video_bitrate.format(bitrate=stream.bitrate)
        # command[32] = ffmpeg_rtsp_video_bitrate.format(bitrate=stream.bitrate)
        command[13] = ffmpeg_rtsp_video_time_server.format(http_url=http_url)
        command[23] = ffmpeg_rtsp_video_segmentation.format(seg_duration=stream.segment_duration,
                                                            frag_duration=stream.fragment_duration)
        # command[23] = ffmpeg_rtsp_video_segmentation
        command[33] = ffmpeg_rtsp_video_target_latency.format(latency=stream.target_latency)
        command[44] = ffmpeg_rtsp_video_command_output.format(http_url=http_url, stream=stream.name)

        # stream qualities
        stream_qualities_base_pos = 11
        stream_mapping = []
        stream_bitrate = []
        stream_bufsize = []
        stream_filter = []
        stream_codec = []
        stream_x264opts = []
        stream_tune = []
        stream_profile = []
        stream_preset = []
        stream_b_frames = []
        stream_refs = []
        for i, q in stream.qualities.items():
            logger.debug(f"i {i}, {q}")

            stream_mapping.append(ffmpeg_rtsp_video_map_v_stream_param)
            stream_mapping.append(ffmpeg_rtsp_video_map_v_stream_option)

            stream_bitrate.append(ffmpeg_rtsp_video_bitrate_param.format(index=i))
            stream_bitrate.append(ffmpeg_rtsp_video_bitrate_option.format(bitrate=q.targetBitrate, fps=stream.frame_rate))

            stream_bufsize.append(ffmpeg_rtsp_video_buff_size_param.format(index=i))
            stream_bufsize.append(ffmpeg_rtsp_video_buff_size_option.format(bitrate=q.targetBitrate))

            stream_filter.append(ffmpeg_rtsp_video_filter_param.format(index=i))
            stream_filter.append(ffmpeg_rtsp_video_filter_option.format(fps=stream.frame_rate, width=q.targetWidth))

            stream_codec.append(ffmpeg_rtsp_video_codec_param.format(index=i))
            stream_codec.append(ffmpeg_rtsp_video_codec_option)

            stream_x264opts.append(ffmpeg_rtsp_video_x264opts_param.format(index=i))
            stream_x264opts.append(ffmpeg_rtsp_video_x264opts_option.format(fps=stream.intra_interval))

            stream_tune.append(ffmpeg_rtsp_video_tune_param.format(index=i))
            stream_tune.append(ffmpeg_rtsp_video_tune_option)

            stream_profile.append(ffmpeg_rtsp_video_profile_param.format(index=i))
            stream_profile.append(ffmpeg_rtsp_video_profile_option)

            stream_preset.append(ffmpeg_rtsp_video_preset_param.format(index=i))
            stream_preset.append(ffmpeg_rtsp_video_preset_option)

            stream_b_frames.append(ffmpeg_rtsp_video_b_frames_param.format(index=i))
            stream_b_frames.append(ffmpeg_rtsp_video_b_frames_option)

            stream_refs.append(ffmpeg_rtsp_video_refs_param.format(index=i))
            stream_refs.append(ffmpeg_rtsp_video_refs_option)

        logger.debug(f"Size of stream_mapping: {len(stream_mapping)}")
        logger.debug(f"Size of stream_bitrate: {len(stream_mapping)}")

        # mapping
        current_pos = stream_qualities_base_pos
        del command[current_pos]
        for idx, i in enumerate(stream_mapping):
            command.insert(current_pos + idx, i)

        # bitrate
        current_pos = current_pos + len(stream_mapping)
        for idx, i in enumerate(stream_bitrate):
            command.insert(current_pos + idx, i)

        # bufsize
        current_pos = current_pos + len(stream_bitrate)
        for idx, i in enumerate(stream_bufsize):
            command.insert(current_pos + idx, i)

        # filter
        current_pos = current_pos + len(stream_bufsize)
        for idx, i in enumerate(stream_filter):
            command.insert(current_pos + idx, i)

        # codec
        current_pos = current_pos + len(stream_filter)
        logger.debug(f"current_pos: {current_pos}")
        for idx, i in enumerate(stream_codec):
            command.insert(current_pos + idx, i)

        # x264opts
        current_pos = current_pos + len(stream_codec)
        for idx, i in enumerate(stream_x264opts):
            command.insert(current_pos + idx, i)

        # stream_tune
        current_pos = current_pos + len(stream_x264opts)
        for idx, i in enumerate(stream_tune):
            command.insert(current_pos + idx, i)

        # stream_profile
        current_pos = current_pos + len(stream_tune)
        for idx, i in enumerate(stream_profile):
            command.insert(current_pos + idx, i)

        # stream_preset
        current_pos = current_pos + len(stream_profile)
        for idx, i in enumerate(stream_preset):
            command.insert(current_pos + idx, i)

        # stream_b_frames
        current_pos = current_pos + len(stream_preset)
        for idx, i in enumerate(stream_b_frames):
            command.insert(current_pos + idx, i)

        # stream_refs
        current_pos = current_pos + len(stream_b_frames)
        for idx, i in enumerate(stream_refs):
            command.insert(current_pos + idx, i)

        return command

    return None
