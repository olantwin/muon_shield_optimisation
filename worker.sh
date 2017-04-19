#!/bin/env bash
set -eux
source /opt/FairShipRun/config.sh
JOBID=$1
GEOFILE=$2
TOTAL=4
python2 /input/slave.py --geofile /input/"$GEOFILE" --jobid "$JOBID" -f /input/muons_"${JOBID}"_"${TOTAL}".root --results /output/result.csv
