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
from common import FCN, load_results, get_geo


def retrieve_result(outFile, local):
    print 'Retrieving results from {}.'.format(outFile)
    if not local:
        while True:
            if check_file(outFile, local):
                break
            time.sleep(60)  # Wait for job to finish
    return load_results(outFile)


def check_file(fileName, local, strict=True):
    if local:
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


def check_path(path, local):
    if local:
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


def worker(id_, geoFile, lofi, backend):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    n = (ntotal / args.njobs) + (ntotal % args.njobs
                                 if id_ == args.njobs else 0)
    outFile = '{}/output_files/iteration_{}/{}/result.root'.format(
        args.workDir, os.path.basename(geoFile), id_)
    if backend == 'local':
        path = os.path.dirname(outFile)
        if not os.path.isdir(path):
            os.makedirs(path)
        command = [
            './slave.py', '--geofile', geoFile, '--jobid', str(id_), '-f',
            worker_filename, '-n', str(n), '--results', outFile
        ]
        if lofi:
            command += ['--lofi']
        subprocess.call(
            command,
            shell=False)
    print 'Master: Worker process {} done.'.format(id_)
    return retrieve_result(outFile, backend == 'local')


def get_bounds():
    dZgap = 10.
    zGap = 0.5 * dZgap  # halflengh of gap
    dZ3 = (20. + zGap, 300. + zGap)
    dZ4 = (20. + zGap, 300. + zGap)
    dZ5 = (20. + zGap, 300. + zGap)
    dZ6 = (20. + zGap, 300. + zGap)
    dZ7 = (20. + zGap, 300. + zGap)
    dZ8 = (20. + zGap, 300. + zGap)
    bounds = [dZ3, dZ4, dZ5, dZ6, dZ7, dZ8]
    for _ in range(2):
        minimum = 10.
        dXIn = (minimum, 250.)
        dXOut = (minimum, 250.)
        dYIn = (minimum, 250.)
        dYOut = (minimum, 250.)
        gapIn = (2., 498.)
        gapOut = (2., 498.)
        bounds += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return bounds


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), np.array(params))
    parray.Write('params')
    f.Close()
    print 'Geofile constructed at ' + geofile
    return geofile


def check_worker_file(id_, local):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename, local, strict=False):
        print worker_filename, 'exists.'
    else:
        return id_


f, tree = None, None


def init_filemaker():
    global f, tree
    f = r.TFile.Open(args.input)
    tree = f.Get('pythia8-Geant4')


def filemaker(id_, local):
    # requires init_worker_files to initialise worker process
    assert id_
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename, local):
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


def compute_FCN(params, lofi=False, backend='skygrid'):
    local = backend == 'local'
    params = [70., 170.] + params[:6] + [
        # MagnAbsorb1:
        40.,
        40.,
        150.,
        150.,
        2.,
        2.,
        # MagnAbsorb2:
        80.,
        80.,
        150.,
        150.,
        2.,
        2.,
    ] + params[6:] + [
        # Magn3:
        6.,
        33.,
        32.,
        13.,
        70.,
        11.,
        # Magn4:
        5.,
        16.,
        112.,
        5.,
        4.,
        2.,
        # Magn5:
        15.,
        34.,
        235.,
        32.,
        5.,
        8.,
        # Magn6:
        31.,
        90.,
        186.,
        310.,
        2.,
        55.,
    ]

    # Add constant parameters
    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, compute_FCN.counter), params)
    geoFileLocal = generate_geo('{}/input_files/geo_{}.root'.format(
        '.', compute_FCN.counter), params) if not local else geoFile
    pool = Pool(processes=min(args.njobs,
                              cpu_count() - 1 if local else 2 * cpu_count() - 2))
    geo_result = pool.apply_async(get_geo, [geoFileLocal])
    if not local:
        expected_time = 2400  # seconds
        time.sleep(expected_time / 4)
    partial_worker = partial(worker, geoFile=geoFile, lofi=lofi)
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
    assert check_path('{}/worker_files'.format(args.workDir), args.local)
    ids = range(1, args.njobs + 1)
    missing_files = pool.imap_unordered(
        partial(check_worker_file, local=args.local),
        ids
    )
    pool.close()
    pool.join()
    pool = Pool(
        processes=min(args.njobs, cpu_count()), initializer=init_filemaker)
    missing_ids = ifilter(None, missing_files)
    pool.imap_unordered(
        partial(filemaker, local=args.local),
        missing_ids
    )
    pool.close()
    pool.join()
    del pool
    bounds = get_bounds()
    start = [
        # Units all in cm
        # Lengths:
        (200. + 5.) / 2.,
        (200. + 5.) / 2.,
        (275. + 5.) / 2.,
        (240. + 5.) / 2.,
        (300. + 5.) / 2.,
        (235. + 5.) / 2.,
        # Magn1:
        87.,
        65.,
        35.,
        121,
        11.,
        2.,
        # Magn2:
        65.,
        43.,
        121.,
        207.,
        11.,
        2.,
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
    main()
