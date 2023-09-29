import asyncio
import re
import subprocess
import time

import pandas as pd
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.requests import ClientDisconnect

import ffmpeg_commands
from fastll_conf import fastll_conf
from fastll_stream import *

VERSION = "Fastll 0.7.1"

tags_metadata = [
    {
        "name": "Service Information",
        "description": """
           Information regarding the service
       """
    },
    {
        "name": "Time Synchronization",
        "description": """
          Server time in ISO format form client-server time synchronization
      """
    },
    {
        "name": "Incoming Object",
        "description": """
            Incoming DASH objects: Manifest, Initial Segment and Segments
        """
    },
    {
        "name": "Object Request",
        "description": """
            DASH object requests: Manifest, Initial Segment and Segments
        """,
    },
    {
        "name": "Object Removal",
        "description": """
        Remove DASH objects that are not available in the manifest anymore
        """,
    },
    {
        "name": "Manual Server Side Stream Switching",
        "description": """
        Sets an adaptation set to force to all clients
        """,
    }
]

app = FastAPI(
    title="Fastll",
    description="""
Real Time DASH server for low latency streaming
""",
    version=VERSION,
    contact={
        "name": "Multimedia Communications Group",
        "url": "https://www.comm.upv.es/es/",
        "email": "robelor@iteam.upv.es"
    },
    openapi_tags=tags_metadata
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NO_CLIENT_WAIT_TIME = 15  # seconds

host: str = ""
port: str = ""
http_url: str = ""
timeDisplacement: int = 0
waitForAbsentSegment: bool = True

ffmpeg_lock = asyncio.Lock()
fll_streams: Dict[str, Stream] = {}
fll_streams_adaptation_set_override = {}

stream_pattern = r"stream(\d+)"
segment_number_pattern = r'-(\d+)\.m4s$'
conf_streams = {}
inits = {}
segments = {}
ffmpeg_status = {}  # 0:starting, 1: started
ffmpeg_pids = {}
stream_last_access = {}
request_stats = {}


class StreamCheckTask:
    def __init__(self):
        self.value = 0

    @staticmethod
    async def check():
        while True:
            await asyncio.sleep(2)
            dt = datetime.utcnow()
            now = datetime.timestamp(dt)
            for fll_stream in fll_streams.values():
                if fll_stream.status == StreamStatus.STARTED:
                    stream_last_access_time = fll_stream.last_access
                    delta = now - stream_last_access_time
                    if delta > NO_CLIENT_WAIT_TIME:
                        logger.debug(f"Stop stream: {fll_stream.name}")
                        fll_stream.stop()
                        if fll_stream.save_stats:
                            ClientStats.summary_stats(client_stats)


runner = StreamCheckTask()


class ClientStats:
    def __init__(self):
        self.stats = pd.DataFrame(columns=['timestamp', 'delta', 'jitter', 'users'])

    def update_timestamp(self, timestamp, users):
        # Add timestamp
        self.stats.loc[len(self.stats), ['timestamp', 'users']] = [timestamp, users]

        length = len(self.stats)
        if length > 1:
            # Calculate delta
            self.stats.loc[length - 1, 'delta'] = self.stats.loc[length - 1, 'timestamp'] - self.stats.loc[length - 2, 'timestamp']
        if length > 2:
            # Calculate jitter
            self.stats.loc[length - 1, 'jitter'] = abs(self.stats.loc[length - 1, 'delta'] - self.stats.loc[length - 2, 'delta'])

    def last_delta(self):
        delta = self.stats.loc[len(self.stats) - 1, 'delta']
        return delta if not pd.isna(delta) else 0

    def last_jitter(self):
        jitter = self.stats.loc[len(self.stats) - 1, 'jitter']
        return jitter if not pd.isna(jitter) else 0

    def average_jitter(self, count=10):
        return self.stats['jitter'][-count:].dropna().mean()

    def deltas(self, count=0, dropna=True):
        if 0 < count < len(self.stats):
            return self.stats['delta'][-count:].dropna() if dropna else self.stats['delta'][-count:]
        return self.stats['delta'].dropna() if dropna else self.stats['delta']

    def jitters(self, count=0, dropna=True):
        if 0 < count < len(self.stats):
            return self.stats['jitter'][-count:].dropna() if dropna else self.stats['jitter'][-count:]
        return self.stats['jitter'].dropna() if dropna else self.stats['jitter']

    def users(self, count=0, dropna=True):
        if 0 < count < len(self.stats):
            return self.stats.dropna()['users'][-count:] if dropna else self.stats['users'][-count:]
        return self.stats.dropna()['users'] if dropna else self.stats['users']

    @staticmethod
    def summary_stats(stats):
        names = list(stats.keys())
        # Data
        data = {}
        cols = []
        for name in names:
            # Columns with client id for jitter values
            hdr = name + '_jitter'
            data[hdr] = stats[name].jitters().to_list()
            cols.append(hdr)
            # Columns with client id for delay values
            hdr = name + '_delta'
            data[hdr] = stats[name].deltas().to_list()
            cols.append(hdr)
            # Columns with client id for concurrent users
            hdr = name + '_users'
            data[hdr] = stats[name].users().to_list()
            cols.append(hdr)

        print(data)
        # Dataset
        df = pd.DataFrame.from_dict(data=data, orient='index').transpose()
        df.to_csv('summary_jitter.csv')


client_stats = {}


@app.on_event("startup")
async def startup_event():
    global host
    global port
    global http_url
    global timeDisplacement
    global waitForAbsentSegment

    logger.debug("Fast-ll starting...")
    logger.debug(f"Fast-ll time...{datetime.timestamp(datetime.utcnow())}")

    # app configuration
    host = fastll_conf["host"]
    port = fastll_conf["port"]
    http_protocol = "http"
    if fastll_conf["https"]:
        http_protocol = "https"
    http_url = f"{http_protocol}://{host}:{port}"
    logger.debug(f"Fast-ll http url: {http_url}")
    streams = fastll_conf["streams"]
    logger.debug(f"Fast-ll streams: {streams}")
    timeDisplacement = fastll_conf["timeDisplacement"]

    # index streams by stream id
    for i in streams:
        conf_streams[i["stream"]] = i
        fll_stream = Stream(i)
        fll_streams[fll_stream.name] = fll_stream

    # start check task
    asyncio.create_task(runner.check())

    # to start a stream on startup (comment the line above to avoid stopping it)
    # fll_stream = fll_streams["hik"]
    # await start_ffmpeg(fll_stream)


@app.get("/")
@app.get("/version", tags=["Service Information"],
         description="Display version information")
async def version():
    return Response(content=VERSION, media_type="text/plain;charset=UTF-8", status_code=200)


@app.get("/conf", tags=["Service Information"],
         description="Dictionary of configured streams by stream ID")
async def conf():
    return JSONResponse(content=fastll_conf["streams"])


@app.get("/isotime", tags=["Time Synchronization"],
         description="Server time in ISO format")
async def iso_time():
    time_format = '%Y-%m-%dT%H:%M:%S.%fZ'
    t = datetime.utcnow() - timedelta(seconds=timeDisplacement)
    return Response(content=t.strftime(time_format), media_type="text/plain;charset=UTF-8", status_code=200)


@app.get("/ssss/{stream}/{adaptation_set_id}", tags=["Server Side Streaming Switching Request"],
         description="Forces an adaptation set to be used on the selected stream")
async def ssss_stream_selection(stream: str, adaptation_set_id: int):
    if stream in conf_streams:
        # stream
        fll_stream = fll_streams[stream]
        if adaptation_set_id < 0 or adaptation_set_id >= fll_stream.max_adaptation_set():
            return Response(content="Error", media_type="text/plain;charset=UTF-8", status_code=404)
        fll_streams_adaptation_set_override[stream] = adaptation_set_id
        return Response(content="OK", media_type="text/plain;charset=UTF-8", status_code=200)
    else:
        return Response(content="Error", media_type="text/plain;charset=UTF-8", status_code=404)


@app.get("/{stream_data}/{name}", tags=["Object Request"],
         description="Handles HTTP GET request to stream objects")
async def outgoing_data(stream_data: str, name: str):
    request_incoming_time = time.time()

    if "-" in stream_data:
        stream_components = stream_data.split("-")
        stream = stream_components[0]
        request_client = stream_components[1]
    else:
        stream = stream_data
        request_client = "unknown"

    if stream in conf_streams:
        # stream
        fll_stream = fll_streams[stream]
        update_access_time(fll_stream)

        if name.startswith("manifest"):
            # start ffmpeg
            await start_ffmpeg(fll_stream)

            # return manifest when available
            try:
                await asyncio.wait_for(fll_stream.manifest.event.wait(), 10.0)
                if fll_stream.server_side_streaming_switching:
                    return Response(content=fll_stream.manifest.get_ssss_manifest(), media_type="text/plain;charset=UTF-8", status_code=200)
                else:
                    return Response(content=fll_stream.manifest.get_manifest(), media_type="text/plain;charset=UTF-8", status_code=200)
            except asyncio.TimeoutError:
                return Response(status_code=404)

        if name.startswith("init"):
            # return init segment when available
            stream_id = int(re.search(stream_pattern, name).group(1))
            try:
                await asyncio.wait_for(fll_stream.init_segments[stream_id].event.wait(), 5.0)
                return Response(content=fll_stream.init_segments[stream_id].data, status_code=200)
            except asyncio.TimeoutError:
                return Response(status_code=404)

        if name.startswith("chunk"):

            # stats
            if fll_stream.save_stats:
                if request_client not in client_stats:
                    client_stats[request_client] = ClientStats()
                client_stats[request_client].update_timestamp(request_incoming_time, len(client_stats))
                logger.debug(f"Clients: {len(client_stats)}, avg. jitter: {request_client}/{client_stats[request_client].average_jitter()}")

            # get segment number
            if fll_stream.server_side_streaming_switching:
                segment_number = int(re.search(segment_number_pattern, name).group(1))
                delta_segments = fll_stream.current_segment - segment_number
                target_adaptation_set = fll_stream.max_adaptation_set()
                representation_ratio = int(delta_segments)

                # SSRS algorithm
                target_adaptation_set = target_adaptation_set - representation_ratio
                if target_adaptation_set < 0:
                    target_adaptation_set = 0

                logger.debug(f"SSRS Segment name: {name} -> adaptation set: {target_adaptation_set}")
                if target_adaptation_set <= fll_stream.max_adaptation_set():
                    old_name = name
                    name = re.sub(r"\d", str(target_adaptation_set), name, count=1)
                    logger.debug(f"SSRS Rewrite segment request: {old_name}->{name}")

            # return chunk
            waiting_time = 0
            if name not in fll_stream.segments:
                # segment is not in the server
                found = False
                if waitForAbsentSegment:
                    # create new segment
                    await fll_stream.segments_lock.acquire()
                    try:
                        fll_segment = Segment(name)
                        fll_stream.segments[name] = fll_segment
                    finally:
                        fll_stream.segments_lock.release()

                    # wait for the segment to start arriving
                    try:
                        start_wait = time.time()
                        await asyncio.wait_for(fll_segment.event.wait(), 2)
                        end_wait = time.time()
                        waiting_time = end_wait - start_wait
                    except asyncio.TimeoutError:
                        logger.warning(f"--> {name} - Segment wait timeout!")
                        return Response(status_code=404)
                else:
                    logger.warning(f"--> {name} - Segment not in server and not configured to retain the request!")
                    return Response(status_code=404)

            else:
                # segment is on the server
                found = True
                fll_segment = fll_stream.segments[name]

            if fll_segment.completed:
                log_outgoing_chunk(name, found, waiting_time, 'y')
                # return StreamingResponse(generate_segment(fll_segment.chunks))
                return Response(content=fll_segment.completed_data)
            else:
                log_outgoing_chunk(name, found, waiting_time, 'n')
                return StreamingResponse(generate_partial_segment(fll_segment))

    logger.warning(f"Can't serve {name}!")
    return Response(status_code=404)


def log_outgoing_chunk(name, found, wait, completed):
    chunk_log_found = "--> {name} - found:{found}, completed:{completed}"
    chunk_log_not_found = "--> {name} - found:{found}, wait:{wait}"
    if found:
        logger.debug(chunk_log_found.format(found='y', name=name, completed=completed))
    else:
        logger.debug(chunk_log_not_found.format(found='n', name=name, wait='{0:.2f}'.format(wait)))


@app.put("/{stream}/{name}", tags=["Incoming Object"],
         description="Handles incoming objects from the packaging tool (FFmpeg)")
async def incoming_data(request: Request, stream: str, name: str):
    try:
        fll_stream: Stream = fll_streams[stream]
        if name.startswith("chunk"):
            # incoming chunk
            segment_number = int(re.search(segment_number_pattern, name).group(1))
            fll_stream.current_segment = segment_number
            # create or get incoming segment
            if name not in fll_stream.segments:
                found = 'n'
                await fll_stream.segments_lock.acquire()
                try:
                    incoming_segment = Segment(name)
                    fll_stream.segments[name] = incoming_segment
                finally:
                    fll_stream.segments_lock.release()
            else:
                found = 'y'
                incoming_segment = fll_stream.segments[name]

            # incoming segment has begun to arrive
            incoming_segment.event.set()

            async for chunk in request.stream():
                current_number_of_chunks = len(incoming_segment.chunks)
                current_chunk = incoming_segment.chunks[current_number_of_chunks - 1]
                # add next chunk to let request wait on the Event
                incoming_segment.chunks.append(Chunk())
                # add the current chunk data
                current_chunk.data = chunk
                incoming_segment.completed_data = incoming_segment.completed_data + chunk
                # set the current chunk event
                current_chunk.event.set()

            incoming_segment.chunks[len(incoming_segment.chunks) - 1].event.set()
            incoming_segment.completed = True
            log_incoming_chunk(name, found, len(incoming_segment.chunks) - 1)

        else:
            # other type of objects can be read wholly
            if name.startswith("manifest"):
                req = await request.receive()
                fll_stream.manifest.set_manifest(req["body"].decode())
                logger.debug(f"Manifest: {name}")

            if name.startswith("init"):
                stream_id = int(re.search(stream_pattern, name).group(1))
                # This sleep is required for some cameras not having an empty init segment
                time.sleep(0.2)
                req = await request.receive()

                if "body" in req:
                    logger.debug(f"Init segment: {name}")
                    fll_stream.init_segments[stream_id].set_initial_segment(req["body"])
                else:
                    logger.warning("Init segment has no body!!!")

        response = Response(status_code=200)
        return response
    except KeyError:
        logger.warning(f"Stream {stream} is no longer in the server")
        response = Response(status_code=404)
        return response
    except ClientDisconnect:
        pass


def log_incoming_chunk(name, found, number_of_chunks):
    chunk_log_found = f"<-- {name} - f:{found}, c:{number_of_chunks}"
    logger.debug(chunk_log_found.format(name=name, found=found, number_of_chunks=number_of_chunks))


@app.delete("/{stream}/{name}", tags=["Object Removal"],
            description="Handles object removal from the packaging tool (FFmpeg)")
async def delete_data(stream: str, name: str):
    try:
        fll_stream: Stream = fll_streams[stream]
        if name.startswith("manifest"):
            fll_stream.clear_manifest()
            return Response(status_code=200)

        if name.startswith("init"):
            fll_stream.clear_init_segments()
            return Response(status_code=200)

        if name.startswith("chunk"):
            del (fll_stream.segments[name])
            return Response(status_code=200)

    except KeyError:
        logger.debug(f"Stream {stream} is no longer in the server")

    return Response(status_code=404)


def update_access_time(fll_stream: Stream):
    fll_stream.last_access = datetime.timestamp(datetime.utcnow())


async def start_ffmpeg(fll_stream: Stream):
    await ffmpeg_lock.acquire()
    try:
        if fll_stream.ffmpeg_state.status < FfmpegStatus.STARTING:
            fll_stream.status = StreamStatus.STARTED
            fll_stream.ffmpeg_state.status = FfmpegStatus.STARTING
            ffmpeg_command = ffmpeg_commands.ffmpeg_command(http_url, fll_stream)
            logger.debug(f"FFmpeg command: {ffmpeg_command}")
            fll_stream.ffmpeg_state.pid = subprocess.Popen(ffmpeg_command)
            fll_stream.ffmpeg_state.status = FfmpegStatus.STARTED
    finally:
        ffmpeg_lock.release()


async def generate_partial_segment(segment: Segment):
    chunks = segment.chunks
    aux = 0
    while aux < len(chunks):
        try:
            await asyncio.wait_for(chunks[aux].event.wait(), 1)
            data = chunks[aux].data
            if data is not None:
                yield data
            aux = aux + 1
        except asyncio.TimeoutError:
            return
