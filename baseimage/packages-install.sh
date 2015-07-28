#!/bin/bash

# This script sets up an Ubuntu Linux installation with the correct packages, building them from source if necessary.

rm -r ~/eventstreamr

## Comment out the source archives
sed -i 's/deb-src/#deb-src/g' /etc/apt/sources.list

## APT remove unneeded stuff and get needed stuff
apt-get update
apt-get dist-upgrade -y
apt-get install -y ubuntu-desktop
apt-get remove --purge -y ffmpeg unity-lens-shopping unity-scope-musicstores whoopsie example-content libreoffice-common shotwell thunderbird evolution-data-server
apt-get autoremove --purge -y
apt-get install -y openssh-server build-essential vlc xchat mumble melt vim libdbd-mysql-perl libdbd-pg-perl indicator-multiload dvgrab tmux iotop git cmake libgtkmm-2.4-dev libboost1.54-all-dev libjack-dev liblo-dev libasound2-dev libxv-dev curl autoconf automake build-essential libass-dev libtheora-dev libopus-dev libtool libvorbis-dev yasm libx264-dev libfdk-aac-dev libmp3lame-dev libopus-dev libvpx-dev libdancer-perl libipc-shareable-perl libproc-daemon-perl libjson-perl libconfig-json-perl libproc-processtable-perl libfile-slurp-perl libmoo-perl libhash-merge-simple-perl liblog-log4perl-perl libfile-readbackwards-perl libhttp-tiny-perl nodejs-legacy libfile-rsync-perl libanyevent-perl liblinux-inotify2-perl libfreetype6-dev libgpac-dev libtool pkg-config opus-tools cmake guake plymouth-theme-ubuntu-logo

## Get the latest eventstreamr
cd ~
git clone https://github.com/joeladdison/eventstreamr eventstreamr
cd ~/eventstreamr
git checkout pyconau-2015

## Setup ffmpeg
mkdir -p ~/eventstreamr/baseimage/src
cd ~/eventstreamr/baseimage/src
git clone git://source.ffmpeg.org/ffmpeg.git ffmpeg
cd ffmpeg
./configure --enable-gpl \
   --enable-libass --enable-libfdk-aac --enable-libfreetype --enable-libmp3lame --enable-libopus \
   --enable-libtheora --enable-libvorbis --enable-libvpx --enable-libx264 --enable-nonfree --enable-shared --disable-static
make
make install
make distclean
ldconfig

## Setup DVSwitch
cd ..
wget "https://alioth.debian.org/plugins/scmgit/cgi-bin/gitweb.cgi?p=dvswitch/dvswitch.git;a=snapshot;h=1f98a6d22b18fa080b38e2abee3b2202807633d4;sf=tgz" -O dvswitch.tar.gz
tar -xvf dvswitch.tar.gz
cd dvswitch-1f98a6d
make
make install
make clean
chown -R av: ~/eventstreamr
