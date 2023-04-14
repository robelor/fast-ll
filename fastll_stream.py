from asyncio import Event, Lock
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from subprocess import Popen
from typing import List, Dict
from fastll_defaults import *
from loguru import logger
import xml.etree.ElementTree as eT


class FfmpegStatus(IntEnum):
    STOPPED = 0
    STARTING = 1
    STARTED = 2


class StreamStatus(IntEnum):
    STOPPED = 0
    STARTED = 1


@dataclass
class Chunk:
    data: bytes = None
    event: Event = field(default_factory=Event, init=False)


@dataclass
class Segment:
    name: str
    completed: bool
    event: Event
    chunks: List[Chunk]
    completed_data: bytes

    def __init__(self, name: str):
        self.name = name
        self.completed = False
        self.event = Event()
        self.chunks = list()
        self.chunks.append(Chunk())
        self.completed_data = bytes()


@dataclass
class FfmpegState:
    pid: Popen = None
    status: FfmpegStatus = FfmpegStatus.STOPPED

    def stop(self):
        self.pid.kill()


@dataclass
class Manifest:
    _skip_count = 0
    _data: str = None
    _ssss_data: str = None
    event: Event = field(default_factory=Event, init=False)

    def set_manifest(self, manifest: str):
        if self._skip_count <= 4:
            self._skip_count = self._skip_count + 1
            return
        # unmodified manifest
        self._data = manifest
        # ssss manifest

        # Parse the MPD XML string
        mpd_root = eT.fromstring(self._data)

        # Define the XML namespace dictionary
        ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}

        # Remove the namespace prefix from the tag names
        for elem in mpd_root.iter():
            if elem.tag.startswith('{'):
                elem.tag = elem.tag.split('}', 1)[1]
                if '}' in elem.attrib:
                    del elem.attrib['}']

        # Iterate over periods
        for period in mpd_root.findall('Period', ns):

            # Iterate over adaptation sets
            for adaptation_set in period.findall('AdaptationSet', ns):
                # Delete representations whose id isn't 0
                for representation in adaptation_set.findall('Representation', ns):
                    if representation.attrib['id'] != '0':
                        adaptation_set.remove(representation)

        # Save the modified MPD XML to a string
        self._ssss_data = eT.tostring(mpd_root, encoding='utf-8', xml_declaration=True)

        # fire manifest ready event
        self.event.set()

    def get_manifest(self):
        return self._data

    def get_ssss_manifest(self):
        return self._ssss_data


@dataclass
class InitialSegment:
    data: bytes = None
    event: Event = field(default_factory=Event, init=False)

    def set_initial_segment(self, segment: bytes):
        self.data = segment
        self.event.set()


@dataclass
class Quality:
    targetWidth: str = None
    targetBitrate: str = None


@dataclass
class Stream:
    name: str
    showName: str
    type: str
    input: str
    frame_rate: str
    segment_duration: str
    fragment_duration: str
    intra_interval: str
    width: str
    bitrate: str
    target_latency: str
    last_access: float
    status: StreamStatus
    manifest: Manifest
    init_segments: Dict[int, InitialSegment]
    segments: Dict[str, Segment]
    qualities: Dict[int, Quality]
    server_side_streaming_switching: bool
    save_stats: bool
    segments_lock: Lock
    ffmpeg_state: FfmpegState
    current_segment: int

    def __init__(self, config_stream):
        self.name = config_stream["stream"]
        self.showName = config_stream["name"]
        self.type = config_stream["type"]
        if self.type != "GEN":
            self.input = config_stream["input"]
        else:
            self.input = ""

        if "targetFps" in config_stream:
            self.frame_rate = config_stream["targetFps"]
        else:
            self.frame_rate = DEFAULT_FRAME_RATE

        if "intraInterval" in config_stream:
            self.intra_interval = config_stream["intraInterval"]
        else:
            self.intra_interval = DEFAULT_INTRA_INTERVAL

        if "segmentDuration" in config_stream:
            self.segment_duration = config_stream["segmentDuration"]
        else:
            self.segment_duration = DEFAULT_SEGMENT_DURATION

        if "fragmentDuration" in config_stream:
            self.fragment_duration = config_stream["fragmentDuration"]
        else:
            self.fragment_duration = DEFAULT_FRAGMENT_DURATION

        if "targetWidth" in config_stream:
            self.width = config_stream["targetWidth"]
        else:
            self.width = DEFAULT_WIDTH

        if "targetBitrate" in config_stream:
            self.bitrate = config_stream["targetBitrate"]
        else:
            self.bitrate = DEFAULT_BITRATE_KBPS

        if "targetLatency" in config_stream:
            self.target_latency = config_stream["targetLatency"]
        else:
            self.target_latency = DEFAULT_TARGET_LATENCY

        if "serverSideRepresentationSwitching" in config_stream:
            self.server_side_streaming_switching = config_stream["serverSideRepresentationSwitching"]
        else:
            self.server_side_streaming_switching = DEFAULT_SERVER_SIDE_REPRESENTATION_SWITCHING

        if "saveStats" in config_stream:
            self.save_stats = config_stream["saveStats"]
        else:
            self.save_stats = DEFAULT_SAVE_STATS

        self.qualities = dict()
        if "qualities" in config_stream:
            qualities = config_stream['qualities']
            logger.debug(f"Qualities {qualities}")
            if "video" in qualities:
                video_qualities = enumerate(qualities['video'])
                for idx, i in video_qualities:
                    video_quality = i
                    logger.debug(f"Quality {idx}: {video_quality}")
                    quality = Quality(video_quality["targetWidth"], video_quality["targetBitrate"])
                    self.qualities[idx] = quality
        self.init_segments = dict()
        for idx, i in enumerate(self.qualities):
            self.init_segments[idx] = InitialSegment()
            logger.debug(f"init_segments {idx}: {self.init_segments[idx]}")
        self.status = StreamStatus.STOPPED
        self.last_access = datetime.timestamp(datetime.utcnow() - timedelta(hours=1))
        self.manifest = Manifest()
        self.ffmpeg_state = FfmpegState()
        self.segments_lock = Lock()
        self.segments = dict()
        self.current_segment = 0

    def max_adaptation_set(self):
        return len(self.qualities) - 1

    def clear_manifest(self):
        self.manifest = Manifest()

    def clear_init_segments(self):
        self.init_segments = dict()
        for idx, i in enumerate(self.qualities):
            self.init_segments[idx] = InitialSegment()

    def clear_segments(self):
        self.segments = dict()

    def stop_ffmpeg(self):
        self.ffmpeg_state.stop()
        self.ffmpeg_state = FfmpegState()

    def reset_last_access(self):
        self.last_access = datetime.timestamp(datetime.utcnow() - timedelta(hours=1))

    def stop(self):
        self.status = StreamStatus.STOPPED
        self.stop_ffmpeg()
        self.clear_manifest()
        self.clear_init_segments()
        self.clear_segments()
