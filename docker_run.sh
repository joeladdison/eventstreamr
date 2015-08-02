#!/bin/bash

set -e
rpcbind
mkdir -p /srv/av
mount -t nfs -o nolock,proto=tcp,port=2049 10.4.4.3:/srv/av /srv/av
cd station && celery -A api.celery worker -c 1
