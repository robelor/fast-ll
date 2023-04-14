# Fast-ll

Fast-ll is a LL-DASH web server. It handles segment PUT and GET requests, so
they can arrive even before the actual segments have arrived. Then, it uses
HTTP chunked transfer to serve segments as they arrive.

## Fast-ll request diagram

```mermaid
sequenceDiagram
    autonumber
    participant FFmpeg
    participant Server
    participant Client
    FFmpeg->>Server: PUT manifest.mpd
    FFmpeg->>Server: PUT init.mp4
      Client->>Server: GET manifest.mpd
    Client->>Server: GET init.mp4
    loop segment number: X
        Client->>Server: GET segmentX.mp4
        activate Server
        FFmpeg->>Server: PUT segmentX.mp4
        deactivate Server
        loop chunked transmission
            Server->>Client: segmentX.mp4 chunk
        end
    end

```

## Standard DASH timing diagram

```mermaid
gantt
    
    dateFormat HH:mm:SS
    axisFormat %S
    todayMarker off

    section Encoding
    Segment 1            : segment1, 01-01-01, 3s
    Segment 2            : segment2, after segment1, 3s

    section Upload 
    HTTP PUT Segment 1       : put1, after segment1, 1s
     HTTP PUT Segment 2       : put2, after segment2, 1s
    
    section Download
    Backoff        : backoff1, after put1, 2s
    Segment 1        : get1, after backoff1, 1s
    Backoff        : backoff2, after put2, 2s
    Segment 2        : get2, after backoff2, 1s

    section Playback
    Segment 1        : p1, after get1, 3s
    Segment 2        : p2, after get2, 3s

```

## Low Latency DASH timing diagram

There are a few differences between DASH and Low Latency DASH that are aimed,
precisely, to reduce latency:

1. Segments must be different resources
2. Segments can have fragments in order to enable partial segment playback
3. Segments are downloaded by clients as they are uploaded to the server
4. Segment request can arrive even before the segment has started to arrive
   to the server

```mermaid
gantt
    dateFormat HH:mm:ss
    axisFormat %S
    todayMarker off
    
    section Encoding
    Segment             : s1, 00:00:00, 10s
    Fragment 1          : f1, 00:00:00, 2s
    Fragment 2          : f2, after f1, 2s
    Fragment 3          : f3, after f2, 2s
    Fragment 4          : f4, after f3, 2s
    Fragment 5          : f5, after f4, 2s
    section Upload
    HTTP PUT            : t1, 00:00:01, 10s
    
    section Download
    HTTP Retention      :crit, 00:00:00, 1s
    HTTP GET        : b1, 00:00:00, 11s
    Fragment 1         : fr1, 00:00:01, 2s
    Fragment 2         : fr1, 00:00:03, 2s
    Fragment 3         : fr1, 00:00:05, 2s
    Fragment 4         : fr1, 00:00:07, 2s
    Fragment 5         : fr1, 00:00:09, 2s

    section Playback
    Fragment 1         : fr1, 00:00:03, 2s
    Fragment 2         : fr1, 00:00:05, 2s
    Fragment 3         : fr1, 00:00:07, 2s
    Fragment 4         : fr1, 00:00:09, 2s
    Fragment 5         : fr1, 00:00:11, 2s

```

## Run Fast-ll

We recommend using Python's virtual environment to use Fast-ll. To create one
just run this inside your project's folder:

```bash
python3 -m venv venv
```

After that, and every time you want to run Fast-ll, activate the virtual
environment:

```bash
source venv/bin/activate
```

With the virtual environment active, install requirements the first time you run
it:

```bash
pip install -r requirements.txt
```

> **Note:** FFmpeg must be installed on the running system

Start running:

```bash
python3 fastllapp.py
```

To get a list of the supported parameters:

```bash
python3 fastllapp.py -h
usage: fastllapp.py [-h] [--version] [-v] -c FILE

optional arguments:
  -h, --help            show this help message and exit
  --version             shows fast-ll version
  -v, --verbose         increase output verbosity
  -c FILE, --config FILE
                        input file containing Fast-ll configuration
```

It is mandatory to provide a configuration with `(-c param)` like this one:

```json
{
  "verbose": true,
  "host": "device.owndevice.net",
  "port": 8000,
  "streams": "streams.json",
  "sslKeyFile": "/path/to/cert.key",
  "sslCertFile": "/path/to/cert.pem",
  "timeDisplacement": 0,
  "waitForAbsentSegment": true
}
```

The previous configuration shows all possible configuration params where:

* `host` and `port` are mandatory
* `verbose` increases logging verbosity
* `stremas` defines a file containing the definition of configured streams
* When `sslKeyFile` and `sslCertFile` are provided the service will be provided
  over HTTPS. Otherwise, HTTP is used
* `timeDisplacement`(seconds, optional, default: `0`): Is the numbers of seconds that the
  time service subtracts to the system clock to make clients believe their clock is ahead of
  stream time and, consequently, delay its HTTP requests
* `waitForAbsentSegment`(boolean, option, default: `true`): Whether Fast-ll will retain HTTP
requests that arrive before the actual segment has arrived

`timeDisplacement` can be used to make clients request segments that are complete so the server
does not have to serve-as-receive. This way it can avoid some coroutine synchronization. On the 
other hand, if `waitForAbsentSegment` is set to `false` the server will answer with 404 status 
code to request for segments that are not yet available on the server. Hence, avoiding `asyncio` 
waits. Most players will simpli generate another request that, after a couple of ms, will
provably be a hit.

The file defined in `streams` must contain an array of streams like the example
below:

```json
[
  {
    "name": "Another Stream",
    "stream": "hik1",
    "type": "RTSP",
    "input": "rtsp://admin2:Admin!!!@192.168.0.89:554/h264/ch1/main/av_stream",
    "targetFps": "10",
    "segmentDuration": "1",
    "fragmentDuration": "0.1",
    "intraInterval": "10",
    "serverSideRepresentationSwitching": true,
    "saveStats": false,
    "qualities": {
      "video": [
        {
          "targetWidth": "640",
          "targetBitrate": "250"
        },
        {
          "targetWidth": "640",
          "targetBitrate": "500"
        },
        {
          "targetWidth": "640",
          "targetBitrate": "1000"
        }
      ]
    }
  },
  {
    "name": "Another Stream",
    "stream": "hik2",
    "type": "RTSP",
    "input": "rtsp://admin2:Admin!!!@192.168.0.89:554/h264/ch1/main/av_stream",
    "targetFps": "10",
    "segmentDuration": "1",
    "fragmentDuration": "0.1",
    "intraInterval": "10",
    "saveStats": true,
    "qualities": {
      "video": [
        {
          "targetWidth": "640",
          "targetBitrate": "250"
        },
        {
          "targetWidth": "640",
          "targetBitrate": "500"
        },
        {
          "targetWidth": "640",
          "targetBitrate": "1000"
        }
      ]
    },
    "targetLatency": "0.2"
  }
]
```

In the `streams` example above each stream has:

* A `name`(mandatory, string): Does nothing. Just for convenience.
* A `stream`(mandatory, string) key that will determine the URL used to access the stream using
  DASH according to this pattern: `http[s]://host:port/{stream}/manifest.mpd`
* A `type`(mandatory, string) that can be either `GEN`, for FFmpeg generated video, or `RTSP` for
  RTSP sources
* When a `type` is "RTSP" it is mandatory to provide:
    * `input`(mandatory, string): URL used to access the RTSP with credentials, if needed
* `targetFps`(string, optional, default: `"24"`): The number of frames per seconds of the generated Low Latency DASH stream 
regardless the frame rate of the input source
* `segmentDuration`(string, optional, default: `"1"`): The duration of DASH segments
* `fragmentDuration`(string, optional, default: `"0,1"`): The duration of segment's fragments
* `targetLatency`(string, optional, default: `"0.5"`): The time (seconds) that the server will 
  signal to clients. Meaning the time since the frame was re-encoded by the server. 
  Clients are not forced to use this parameter and will always be in a best-effort basis
* `intraInterval`(string, optional, default: `"24"`): Interval between Intra frames. At least, every first segment frame
should be an Intra
* `serverSideRepresentationSwitching`(boolean, optional, default: `"false"`): Whether to use SSRS. Note that all
  representations must have the same resolution
* `saveStats`(boolean, optional, default: `"false"`): Same some stats to file. Work in progress
* `qualities`(array of qualities, mandatory): At the momento only video qualities are supported
  * `video`(array of video qualities, mandatory): At least, one video quality must be provided
    * `targetWidth`(string, mandatory): Width of the video stream. Height will be a even proportion 
    * `targetBitrate`(string, mandatory): Target bitrate of the video stream in Kbps

A complete start command could be:

```
python3 fastllapp.py -c config.json
```

## Media playback

In order to play the media content you can use any player you want. For
reference, you can try [Dash.js](https://reference.dashif.org/dash.js/).
Configure it as wanted and use the URL of the manifest in Fast-ll. It is always
a good idea to check the availability of the manifest with a regular web
browser.
