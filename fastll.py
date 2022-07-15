"""
Fast-ll
Copyright (C) 2022  Multimedia Communication Group

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import asyncio
import distutils.spawn

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
logging.basicConfig(level=logging.DEBUG)   # add this line
logger = logging.getLogger("fastll")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manifests = {}
inits = {}
segments = {}


@app.on_event("startup")
def startup_event():
    logger.debug("Fast-ll starting...")
    ffprobe_present = distutils.spawn.find_executable("ffprobe")
    if ffprobe_present is None:
        logger.error("ffprobe not found. Please install it and try again")
        exit(-1)


@app.get("/{stream}/{name}")
async def outgoing_data(stream: str, name: str):
    if name.startswith("manifest"):
        if stream in manifests:
            return Response(content=manifests[stream], media_type="text/plain;charset=UTF-8", status_code=200)
        else:
            return Response(status_code=500)

    if name.startswith("init"):
        if stream in inits:
            return Response(content=inits[stream], status_code=200)
        else:
            return Response(status_code=500)

    if name.startswith("chunk"):
        if stream in segments:
            if name in segments[stream]:
                segment = segments[stream][name]
                if segment["complete"]:
                    return StreamingResponse(generate_segment(segment["chunks"]))
                else:
                    return StreamingResponse(generate_partial_segment(segment))
            else:
                logger.debug("name not found")
                return Response(status_code=500)
        else:
            return Response(status_code=500)

    return Response(status_code=404)


@app.put("/{stream}/{name}")
async def incoming_data(request: Request, stream: str, name: str):
    logger.debug(f"incoming_data: stream: {stream}, object: {name}")

    if name.startswith("chunk"):

        if stream not in segments:
            segments[stream] = {}
            segments[stream][name] = {}
            segments[stream][name]["chunks"] = []
            segments[stream][name]["complete"] = False

        if stream in segments:
            if name not in segments[stream]:
                segments[stream][name] = {}
                segments[stream][name]["chunks"] = []
                segments[stream][name]["complete"] = False

        async for chunk in request.stream():
            segments[stream][name]["chunks"].append(chunk)

        segments[stream][name]["complete"] = True

    else:
        req = await request.receive()

        if name.startswith("manifest"):
            manifests[stream] = req["body"].decode()

        if name.startswith("init"):
            inits[stream] = req["body"]
            pass

    response = Response(status_code=200)
    return response


@app.delete("/{stream}/{name}")
async def delete_data(request: Request, stream: str, name: str):
    logger.debug(f"delete_data: stream: {stream}, object: {name}")

    if name.startswith("manifest"):
        if stream in manifests:
            del(manifests[stream])
            return Response(status_code=200)

    if name.startswith("init"):
        if stream in inits:
            del (inits[stream])
            return Response(status_code=200)

    if name.startswith("chunk"):
        if stream in segments:
            if name in segments[stream]:
                del(segments[stream][name])
                return Response(status_code=200)

    return Response(status_code=404)


async def generate_segment(chunks):
    for i in chunks:
        yield i


async def generate_partial_segment(seg):
    aux = 0
    chunks = seg["chunks"]
    while not seg["complete"]:
        size = len(chunks)
        r = range(aux, size)
        for i in r:
            aux += 1
            yield chunks[i]
        await asyncio.sleep(5e-3)
