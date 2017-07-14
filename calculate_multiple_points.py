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
from common import generate_geo, get_bounds
from fcn import FCN

with open("points.json") as f:
    POINTS = json.load(f)


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
            "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{0}.root -o /shield/input_files/geo_{0}.lw.csv".format(fcn_id)
        )
        print "Docker finished!"
        return True
    except Exception, e:
        print "Docker finished with error, hope it is fine!"
        return False

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
    with open(os.path.join(args.workDir, 'input_files/geo_{}.lw.csv'.format(fcn_id))) as lw_f:
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
                OK = create_geofile(params)
                if not OK:
                    continue

            compute_FCN(params)
        except BaseException, e:
            tlgrm_notify("Exception occured for paramters: [{}]  {}".format(latest_parameters, e))


def main():
    task_queue = Queue()
    n_workers = 98

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
