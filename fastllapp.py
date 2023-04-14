import argparse
import logging
import os
import sys
import json
import distutils.spawn

from loguru import logger
from uvicorn import Config, Server
from fastll_conf import fastll_conf
from fastll import VERSION
from fastll_defaults import DEFAULT_TIME_DISPLACEMENT

LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
JSON_LOGS = True if os.environ.get("JSON_LOGS", "0") == "1" else False


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(LOG_LEVEL)

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # configure loguru
    logger.configure(handlers=[{"sink": sys.stdout, "serialize": JSON_LOGS}])


def file_contents(s):
    try:
        with open(s) as f:
            data = f.read()  # Decode, if desired
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"Problem reading from {s}") from exc
    if len(data) == 0:
        raise argparse.ArgumentTypeError(f"{s} cannot be empty")
    return data


def parse_arguments():
    # Argument parsing
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--version", action='version', version=f"{VERSION}",
                       help="shows fast-ll version")
    parser.add_argument("-c", "--config", dest="config", required=True,
                        help="input file containing Fast-ll configuration", metavar="FILE", type=file_contents)

    return parser.parse_args()


if __name__ == '__main__':
    # argument parsing
    args = parse_arguments()
    config = json.loads(args.config)
    verbose = False
    if "verbose" in config:
        verbose = config["verbose"]
    host = config["host"]
    port = config["port"]
    ssl_key = None
    if "sslKeyFile" in config:
        ssl_key = config["sslKeyFile"]
    ssl_cert = None
    if "sslCertFile" in config:
        ssl_cert = config["sslCertFile"]
    https = False
    if ssl_key is not None and ssl_cert is not None:
        https = True

    streams = None
    if "streams" in config:
        streams_config = config["streams"]
        try:
            with open(streams_config) as json_file:
                streams = json.load(json_file)
        except FileNotFoundError:
            logger.error(f"Stream configuration file can't be read")

    timeDisplacement = DEFAULT_TIME_DISPLACEMENT
    if "timeDisplacement" in config:
        timeDisplacement = config["timeDisplacement"]

    waitForAbsentSegment = True
    if "waitForAbsentSegment" in config:
        waitForAbsentSegment = config["waitForAbsentSegment"]

    if verbose:
        LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "DEBUG"))
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # save configuration
    fastll_conf["host"] = host
    fastll_conf["port"] = port
    fastll_conf["https"] = https
    fastll_conf["streams"] = streams
    fastll_conf["timeDisplacement"] = timeDisplacement
    fastll_conf["waitForAbsentSegment"] = waitForAbsentSegment

    # create server
    server = Server(
        Config(
            "fastll:app",
            host=host,
            port=port,
            log_level=LOG_LEVEL,
            ssl_keyfile=ssl_key,
            ssl_certfile=ssl_cert,
        ),
    )

    # setup logging last, to make sure no library overwrites it
    # (they shouldn't, but it happens)
    setup_logging()

    logger.debug(f"Running on: {host}:{port}")
    logger.debug(f"Verbose: {verbose}")
    logger.debug(f"Cert key file: {ssl_key}")
    logger.debug(f"Cert cert file: {ssl_cert}")
    logger.debug(f"Streams: {streams}")
    if streams is None:
        logger.error(f"Can't go on without stream configuration")
        exit(-1)
    logger.debug(f"Time Displacement: {timeDisplacement}")
    logger.debug(f"Wait for absent segment: {waitForAbsentSegment}")

    # check ffmpeg
    ffprobe_present = distutils.spawn.find_executable("ffprobe")
    if ffprobe_present is None:
        logger.error("ffprobe not found. Please install it and try again")
        exit(-1)

    # server.install_signal_handlers = lambda: None
    server.run()
