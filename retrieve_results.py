#!/bin/env python2
import os
import time
from urlparse import urlparse
import subprocess
from multiprocessing import Pool
from multiprocessing import cpu_count
from functools import partial
import argparse
import numpy as np
import ROOT as r
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
from common import magnetMass, magnetLength, FCN, load_results


def get_geo(geoFile):
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=vessel_design,
        muShieldDesign=shield_design,
        muShieldGeo=geoFile)

    print 'Config created with ' + geoFile

    outFile = r.TMemFile('output', 'create')
    run = r.FairRunSim()
    run.SetName('TGeant4')
    run.SetOutputFile(outFile)
    run.SetUserConfig('g4Config.C')
    shipDet_conf.configure(run, ship_geo)
    run.Init()
    run.CreateGeometryFile('./geo/' + os.path.basename(geoFile))
    sGeo = r.gGeoManager
    muonShield = sGeo.GetVolume('MuonShieldArea')
    L = magnetLength(muonShield)
    W = magnetMass(muonShield)
    return L, W


def worker(id_, geoFile):
    outFile = '{}/output_files/iteration_{}/{}/result.root'.format(
        args.workDir, os.path.basename(geoFile), id_)
    print 'Master: Worker process {} done.'.format(id_)
    return retrieve_result(outFile)


def retrieve_result(outFile):
    print 'Retrieving results from {}.'.format(outFile)
    while True:
        if check_file(outFile):
            return load_results(outFile)
        time.sleep(60)  # Wait for job to finish


def check_file(fileName):
    parser_ = urlparse(fileName)
    try:
        output = subprocess.check_output(
            ['xrdfs', parser_.netloc, 'stat', parser_.path[1:], '-q', 'IsReadable'])
        for line in output.split('\n'):
            if 'Size' in line:
                size = line.split(' ')[-1]
                return int(size) != 0
        print output
    except subprocess.CalledProcessError:
        return False


def main():
    geofile = args.workDir + "/input_files/" + os.path.basename(args.geofile)
    pool = Pool(processes=min(args.njobs, 2 * cpu_count()))
    geo_result = pool.apply_async(get_geo, [geofile])
    partial_worker = partial(worker, geoFile=geofile)
    ids = range(1, args.njobs + 1)
    results = pool.map(partial_worker, ids)
    L, W = geo_result.get()
    print 'Processing results...'
    xs = [x for xs_ in results for x in xs_]
    fcn = FCN(W, np.array(xs), L)
    print fcn
    with open("results.csv", "a") as f:
        f.write("{},{}\n".format(geofile, fcn))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g',
        '--geofile')
    parser.add_argument(
        '--workDir',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/user/olantwin/skygrid')
    parser.add_argument(
        '-j',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    args = parser.parse_args()
    dy = 10.
    vessel_design = 5
    shield_design = 8
    main()
