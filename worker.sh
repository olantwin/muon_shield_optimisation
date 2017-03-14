#!/bin/env bash
source /opt/FairShipRun/config.sh
JOBID=$1
GEOFILE=$2
TOTAL=4
echo "python2 /input/slave.py --geofile /input/$GEOFILE --jobid $JOBID -f /input/muons_${JOBID}_${TOTAL}.root --lofi --results /output/result_${JOBID}.root"
python2 /input/slave.py --geofile /input/$GEOFILE --jobid $JOBID -f /input/muons_${JOBID}_${TOTAL}.root --lofi --results /output/result.root
