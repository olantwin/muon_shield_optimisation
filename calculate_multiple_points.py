#!/usr/bin/env python2
import filelock
import os
import argparse
import numpy as np
import ROOT as r
from sh import docker
from skysteer import calculate_geofile
from telegram_notify import notify as tlgrm_notify
import json
import md5
from multiprocessing import Queue, Process

with open("points.json") as f:
    POINTS = json.load(f)


def FCN(W, Sxi2, L):
    print W, L, Sxi2
    return 0.01*(W/1000)*(1.+Sxi2)/(1.-L/10000.)

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
    for _ in range(8):
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

def dump_params(path, params_json_str):
    with open(path, "w") as f:
        f.write(params_json_str)

def create_geofile(params):
    params_json = json.dumps(params)
    h = md5.new()
    h.update(params_json)
    fcn_id = h.hexdigest()

    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, fcn_id), params)

    try:
        print "Running docker: " + params_json
        docker.run(
            "--rm",
            "-v", "{}:/shield".format(args.workDir),
            "olantwin/ship-shield:20170420",
            '/bin/bash',
            '-l',
            '-c',
            "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{}.root".format(fcn_id)
        )
        print "Docker finished!"
    except Exception, e:
        print "Docker finished with error, hope it is fine!"

def geofile_worker(task_queue):
    while True:
        params = task_queue.get()
        if not params:
            break
        create_geofile(params)


def compute_FCN(params):
    params_json = json.dumps(params)
    h = md5.new()
    h.update(params_json)
    fcn_id = h.hexdigest()

    print "="*5, "compute_FCN:{}".format(fcn_id), "="*5

    dump_params(
        '{}/params/{}.json'.format(args.workDir, fcn_id),
        params_json
    )

    geoFile = '{}/input_files/geo_{}.root'.format(args.workDir, fcn_id)
    if not os.path.isfile(geoFile):
        print "Geofile does not exist, exiting!"
        return

    chi2s = 0
    try:
        chi2s = calculate_geofile(geoFile)
    except Exception, e:
        tlgrm_notify("Error calculating: [{}]  {}".format(params_json, e))
        return
    with open(os.path.join(args.workDir, 'input_files/lw.csv')) as lw_f:
        L, W = map(float, lw_f.read().strip().split(","))

    print 'Processing results...'
    fcn = FCN(W, chi2s, L)
    tlgrm_notify("[{}]  metric={:1.3e}".format(params_json, fcn))

    assert np.isclose(
        L / 2.,
        sum(params[:8]) + 5), 'Analytical and ROOT lengths are not the same.'

    print "="*5, "/compute_FCN", "="*5


def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


# def create_geofiles(params_batch):
#     task_queue = Queue()
#     n_workers = 15

#     for params in params_batch:
#         task_queue.put(params)

#     processes = []
#     for _ in xrange(n_workers):
#         task_queue.put(None)

#         p = Process(target=geofile_worker, args=(task_queue,))
#         p.start()
#         processes.append(p)

#     for p in processes:
#         p.join()

def fcn_worker(task_queue, lockfile):
    latest_parameters = None
    while True:
        try:
            params = task_queue.get()
            if not params:
                break

            latest_parameters = params

            lock = filelock.FileLock(lockfile)
            with lock:
                create_geofile(params)

            compute_FCN(params)
        except BaseException, e:
            tlgrm_notify("Exception occured for paramters: [{}]  {}".format(latest_parameters, e))



def main():
    task_queue = Queue()
    n_workers = 100

    for params in POINTS:
        task_queue.put(params)

    processes = []
    for worker_id in xrange(n_workers):
        task_queue.put(None)

        lockfile = "/tmp/shield-{}.lock".format((worker_id + 1) % 15)
        p = Process(target=fcn_worker, args=(task_queue, lockfile))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


    # for params_batch in batch(POINTS, 50):
    #     create_geofiles(params_batch)

    #     processes = []
    #     for params in params_batch:
    #         p = Process(target=compute_FCN, args=(params,))
    #         p.start()
    #         processes.append(p)

    #     for p in processes:
    #         p.join()

if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
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
    parser.add_argument('--only_geo', action='store_true')
    args = parser.parse_args()
    ntotal = 17786274
    main()
