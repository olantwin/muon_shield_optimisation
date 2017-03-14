#!/bin/env bash
source /opt/FairShipRun/config.sh
JOBID=$1
GEOFILE=$2
/input/slave.py --geofile /input/$GEOFILE --jobid $JOBID -f /input/muons.root --lofi --results /output/result_$JOBID.root
