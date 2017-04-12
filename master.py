#!/usr/bin/env python2
import os
import time
from urlparse import urlparse
import subprocess
from multiprocessing import Pool
from multiprocessing import cpu_count
from functools import partial
from itertools import ifilter
import argparse
import numpy as np
from skopt import forest_minimize, dump
import ROOT as r
import shipunit as u
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
from common import magnetMass, magnetLength, FCN, load_results


def retrieve_result(outFile):
    print 'Retrieving results from {}.'.format(outFile)
    if not args.local:
        while True:
            if check_file(outFile):
                break
            time.sleep(60)  # Wait for job to finish
    return load_results(outFile)


def check_file(fileName, strict=True):
    if args.local:
        return os.path.isfile(fileName)
    else:
        parser_ = urlparse(fileName)
        try:
            command = ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]]
            if strict:
                command += ['-q', 'IsReadable']
            output = subprocess.check_output(command)
            for line in output.split('\n'):
                if 'Size' in line:
                    size = line.split(' ')[-1]
                    if int(size) != 0:
                        print output
                    return int(size) != 0
            print output
        except subprocess.CalledProcessError:
            return False


def check_path(path):
    if args.local:
        return os.path.isdir(path)
    else:
        parser_ = urlparse(path)
        try:
            subprocess.check_output(
                ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]])
            return True
        except subprocess.CalledProcessError as e:
            print e.returncode, e.output
            return False


def worker(id_, geoFile):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    n = (ntotal / args.njobs) + (ntotal % args.njobs
                                 if id_ == args.njobs else 0)
    outFile = '{}/output_files/iteration_{}/{}/result.root'.format(
        args.workDir, os.path.basename(geoFile), id_)
    if args.local:
        path = os.path.dirname(outFile)
        if not os.path.isdir(path):
            os.makedirs(path)
        subprocess.call(
            [
                './slave.py', '--geofile', geoFile, '--jobid', str(id_), '-f',
                worker_filename, '-n', str(n), '--results', outFile, '--lofi'
            ],
            shell=False)
    print 'Master: Worker process {} done.'.format(id_)
    return retrieve_result(outFile)


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


def get_bounds():
    dZgap = 0.1 * u.m
    zGap = 0.5 * dZgap  # halflengh of gap
    dZ3 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ4 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ5 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ6 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ7 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ8 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    bounds = [dZ3, dZ4, dZ5, dZ6, dZ7, dZ8]
    for _ in range(8):
        minimum = 0.1 * u.m
        dXIn = (minimum, 2.5 * u.m)
        dXOut = (minimum, 2.5 * u.m)
        dYIn = (minimum, 2.5 * u.m)
        dYOut = (minimum, 2.5 * u.m)
        gapIn = (2., 4.98 * u.m)
        gapOut = (2., 4.98 * u.m)
        bounds += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return bounds


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), np.array(params))
    parray.Write('params')
    f.Close()
    print 'Geofile constructed at ' + geofile
    return geofile


def check_worker_file(id_):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename, strict=False):
        print worker_filename, 'exists.'
    else:
        return id_


f, tree = None, None


def init_filemaker():
    global f, tree
    f = r.TFile.Open(args.input)
    tree = f.Get('pythia8-Geant4')


def filemaker(id_):
    # requires init_worker_files to initialise worker process
    assert id_
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename):
        print worker_filename, 'exists.'
    else:
        print 'Creating workerfile: ', worker_filename
        worker_file = r.TFile.Open(worker_filename, 'recreate')
        n = (ntotal / args.njobs)
        firstEvent = n * (id_ - 1)
        n += (ntotal % args.njobs if id_ == args.njobs else 0)
        worker_data = tree.CopyTree('', '', n, firstEvent)
        worker_data.Write()
        worker_file.Close()


def compute_FCN(params):
    params = [0.7 * u.m, 1.7 * u.m] + params  # Add constant parameters
    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, compute_FCN.counter), params)
    geoFileLocal = generate_geo('{}/input_files/geo_{}.root'.format(
        '.', compute_FCN.counter), params) if not args.local else geoFile
    pool = Pool(processes=min(args.njobs,
                              cpu_count() - 1 if args.local else 2 * cpu_count() - 2))
    geo_result = pool.apply_async(get_geo, [geoFileLocal])
    if not args.local:
        expected_time = 2400  # seconds
        time.sleep(expected_time / 4)
    partial_worker = partial(worker, geoFile=geoFile)
    ids = range(1, args.njobs + 1)
    results = pool.map(partial_worker, ids)
    L, W = geo_result.get()
    print 'Processing results...'
    xs = [x for xs in results for x in xs]
    fcn = FCN(W, np.array(xs), L)
    assert np.isclose(
        L / 2.,
        sum(params[:8]) + 5), 'Analytical and ROOT lengths are not the same.'
    print fcn
    with open('geo/fcns.csv', 'a') as f:
        f.write('{},{},{},{},{},{} \n'.format(
            compute_FCN.counter, fcn, L, W, sum(xs), len(xs)
        ))
    pool.close()
    pool.join()
    del pool
    compute_FCN.counter += 1
    return fcn


compute_FCN.counter = 107


def main():
    pool = Pool(
        processes=min(args.njobs, cpu_count()))
    assert check_path('{}/worker_files'.format(args.workDir))
    ids = range(1, args.njobs + 1)
    missing_files = pool.imap_unordered(check_worker_file, ids)
    pool.close()
    pool.join()
    pool = Pool(
        processes=min(args.njobs, cpu_count()), initializer=init_filemaker)
    missing_ids = ifilter(None, missing_files)
    pool.imap_unordered(filemaker, missing_ids)
    pool.close()
    pool.join()
    del pool
    bounds = get_bounds()
    start = [
        # Lengths:
        2.0 * u.m + 5 * u.cm,
        2.0 * u.m + 5 * u.cm,
        2.75 * u.m + 5 * u.cm,
        2.4 * u.m + 5 * u.cm,
        3.0 * u.m + 5 * u.cm,
        2.35 * u.m + 5 * u.cm,
        # MagnAbsorb1:
        0.4 * u.m,
        0.4 * u.m,
        1.5 * u.m,
        1.5 * u.m,
        0.02 * u.m,
        0.02 * u.m,
        # MagnAbsorb2:
        0.8 * u.m,
        0.8 * u.m,
        1.5 * u.m,
        1.5 * u.m,
        0.02 * u.m,
        0.02 * u.m,
        # Magn1:
        0.87 * u.m,
        0.65 * u.m,
        0.35 * u.m,
        1.21 * u.m,
        0.11 * u.m,
        0.02 * u.m,
        # Magn2:
        0.65 * u.m,
        0.43 * u.m,
        1.21 * u.m,
        2.07 * u.m,
        0.11 * u.m,
        0.02 * u.m,
        # Magn3:
        0.06 * u.m,
        0.33 * u.m,
        0.32 * u.m,
        0.13 * u.m,
        0.7 * u.m,
        0.11 * u.m,
        # Magn4:
        0.05 * u.m,
        0.16 * u.m,
        1.12 * u.m,
        0.05 * u.m,
        0.04 * u.m,
        0.02 * u.m,
        # Magn5:
        0.15 * u.m,
        0.34 * u.m,
        2.35 * u.m,
        0.32 * u.m,
        0.05 * u.m,
        0.08 * u.m,
        # Magn6:
        0.31 * u.m,
        0.9 * u.m,
        1.86 * u.m,
        3.1 * u.m,
        0.02 * u.m,
        0.55 * u.m,
    ]
    res = forest_minimize(compute_FCN, bounds, x0=start, n_calls=100)
    print res
    compute_FCN(res.x)
    dump(res, 'minimisation_result')


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/data/Mbias/'
        'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '--workDir',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/user/olantwin/skygrid')
    parser.add_argument(
        '-j',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    assert args.local ^ ('root://' in args.workDir), (
        'Please specify a local workDir if not working on EOS.\n')
    ntotal = 17786274
    if args.local:
        args.input = './fast_muons.root'
        ntotal = 86229
    # TODO read total number from muon file directly
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    simEngine = 'MuonBack'
    sameSeed = 1
    theSeed = 1
    main()
