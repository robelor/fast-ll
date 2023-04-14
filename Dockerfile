FROM python:3.8.5

# This is a work in progress not even tested!!

# install dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean

# copy certificate
WORKDIR /
COPY cert cert

# copy the app and install python dependencies
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY fastllapp.py fastllapp.py
COPY fastll.py fastll.py
COPY fastll_stream.py fastll_stream.py
COPY fastll_conf.py fastll_conf.py
COPY fastll_defaults.py fastll_defaults.py
COPY ffmpeg_commands.py ffmpeg_commands.py
COPY config_ssl.json fastll_ssl.json
COPY streams.json teststreams.json
COPY cert cert

# run the app
CMD [ "python3", "fastllapp.py", "-v", "-c", "fastll_ssl.json"]