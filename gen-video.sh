#!/bin/bash

ffmpeg \
-hide_banner -re -f lavfi \
-i "testsrc2=size=1280x720:rate=30" \
-pix_fmt yuv420p \
-c:v libx264 \
-x264opts keyint=30:min-keyint=30:scenecut=-1 \
-tune zerolatency \
-profile:v baseline -preset veryfast \
-bf 0 -refs 3 \
-b:v 500k -bufsize 500k \
-vf "drawtext=fontfile='/Library/Fonts/\
Arial.ttf':text='%{localtime}:box=1:\
fontcolor=black:boxcolor=white:fontsize=100':\
x=40:y=400'" \
-utc_timing_url "https://time.akamai.com/?iso" \
-use_timeline 0 \
-format_options "movflags=cmaf" \
-frag_type duration \
-adaptation_sets "id=0, seg_duration=1, \
frag_duration=0.1, streams=v" \
-streaming 1 \
-ldash 1 \
-export_side_data prft \
-write_prft 1 \
-target_latency 0.5 \
-window_size 5  \
-extra_window_size 10 \
-remove_at_exit 1 \
-method PUT \
-f dash \
http://localhost:8000/test/manifest.mpd