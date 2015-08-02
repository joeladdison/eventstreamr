FROM ubuntu:15.04
MAINTAINER Ryan Stuart <ryan@kapiche.com>

# Install packages
RUN apt-get update && apt-get install -y \
                                build-essential \
                                ca-certificates \
                                ffmpeg \
                                imagemagick \
                                nfs-client \
                                python \
                                python-dev \
                                python-setuptools

# Setup the application
RUN easy_install -U pip
ADD . /eventstreamr
WORKDIR eventstreamr
RUN pip install -r requirements.txt
