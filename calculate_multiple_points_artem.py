#!/usr/bin/env python2
import os
import argparse
import json
from multiprocessing import Queue, Process
import exceptions
import logging
import time
import numpy as np
import ROOT as r
import filelock
from sh import docker
from skysteer import calculate_geofile
from telegram_notify import notify as tlgrm_notify
from common import generate_geo, create_id
from fcn import FCN
import MySQLdb
from downloader import create_merged_file

DB_CONF = dict(
    host='2a03:b0c0:1:d0::2c4f:1001',
    user='root',
    passwd='P@ssw0rd',
    db='points_prod'
)


with open("points.json") as f:
    POINTS = json.load(f)
    f.close()


def dump_params(path, params_json_str):
    with open(path, "w") as f:
        f.write(params_json_str)

def create_geofile(params):
    fcn_id = create_id(params)

    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, fcn_id), params)

    log = logging.getLogger('create_geofile')
    try:
        log.info("Running docker: " + params_json)
        docker.run(
            "--rm",
            "-v", "{}:/shield".format(args.workDir),
            "olantwin/ship-shield:20170420",
            '/bin/bash',
            '-l',
            '-c',
            "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{0}.root -o /shield/input_files/geo_{0}.lw.csv".format(fcn_id)
        )
        log.info("Docker finished!")
        return True
    except Exception, e:
        log.exception('Docker finished with error, hope it is fine! {}'.format(e))
        return False

def geofile_worker(task_queue):
    while True:
        params = task_queue.get()
        if not params:
            break
        create_geofile(params)

def insert_hist(fcn_id, id):
    db = MySQLdb.connect(**DB_CONF)
    cur = db.cursor()

    try:
        create_merged_file('logs/geo_{}.root_jobs.json'.format(fcn_id))
    except:
        return

    with open('./hists/geo_{}.root'.format(fcn_id)) as file:
        cur.execute('UPDATE points_results SET hist = %s WHERE id = %s', (file.read(), id))
        db.commit()
        file.close()

    return


def compute_FCN(params, fcn_id):
    id = params[-1]

    db = MySQLdb.connect(**DB_CONF)
    cur = db.cursor()

    log = logging.getLogger('compute_fcn')
    log.info("="*5 + "compute_FCN:{}".format(fcn_id) + "="*5)

    dump_params(
        '{}/params/{}.json'.format(args.workDir, fcn_id),
        params_json
    )
    cur.execute('''UPDATE points_results SET status = 'running' WHERE id = '{}' '''.format(id))
    db.commit()

    cur.execute('SELECT resampled FROM points_results WHERE id = {}'.format(id))
    sampling = int(cur.fetchall()[0][0])

    geoFile = '{}/input_files/geo_{}.root'.format(args.workDir, fcn_id)
    if not os.path.isfile(geoFile):
        log.error("Geofile does not exist, exiting!")
        cur.execute('UPDATE points_results SET geofile_exception = %s WHERE id = %s', (True, id))
        db.commit()
        db.close()
        return

    chi2s = 0
    try:
        chi2s = calculate_geofile(geoFile, sampling)
    except Exception, e:
        log.exception(e)
        cur.execute('UPDATE points_results SET geofile_exception = %s WHERE id = %s', (True, id))
        db.commit()
        db.close()
        tlgrm_notify("Error calculating: [{}]  {}".format(params_json, e))
        return

    with open(os.path.join(args.workDir, 'input_files/geo_{}.lw.csv'.format(fcn_id))) as lw_f:
        L, W = map(float, lw_f.read().strip().split(","))

    insert_hist(fcn_id, id)

    log.info('Processing results...')
    fcn = FCN(W, chi2s, L)
    tlgrm_notify("[{}]\nresampled={}\nid={}\nweight={}\nchi2={}\nmetric={:1.3e}".format(params_json, sampling, fcn_id, W, chi2s, fcn))

    cur.execute('UPDATE points_results SET weight = %s, metric_1 = %s, chi2 = %s, status = %s WHERE id = %s', (W, fcn, chi2s, 'completed', id))
    db.commit()
    db.close()

    assert np.isclose(
        L / 2.,
        sum(params[:8]) + 5), 'Analytical and ROOT lengths are not the same.'

    log.info("="*5 + "/compute_FCN" + "="*5)


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

            fcn_id = create_id(params[:-1])

            latest_parameters = params[:-1]

            lock = filelock.FileLock(lockfile)
            with lock:
                result = create_geofile(params[:-1])

            compute_FCN(params, fcn_id)

        except BaseException, e:
            log = logging.getLogger('fcn_worker')
            log.exception(e)

            db = MySQLdb.connect(**DB_CONF)
            cur = db.cursor()

            cur.execute('UPDATE points_results SET params_exception = %s WHERE id = %s', (True, params[-1]))
            db.commit()
            db.close()

            tlgrm_notify("Exception occured for paramters: [{}]  {}".format(latest_parameters, e))


def main():
    logging.basicConfig(filename = './logs/runtime.log', level = logging.INFO, format = "%(asctime)s %(process)s %(thread)s: %(message)s")

    '''
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
    '''
    n_workers = 98
    processes = []
    try:
        while True:
            POINTS = []
            while True:
                with open('points_to_run/run.json', 'r+') as f:
                    if len(f.read()) > 0:
                        f.seek(0)
                        POINTS += json.load(f)
                        f.seek(0)
                        f.truncate()
                    f.close()
                    
                if len(POINTS) > 0:
                    break
                else:        
                    time.sleep(10)

            task_queue = Queue()
            for params in POINTS:
                task_queue.put(params)

            for worker_id in xrange(n_workers):
                task_queue.put(None)
                lockfile = "/tmp/shield-{}.lock".format((worker_id + 1) % 15)
                p = Process(target=fcn_worker, args=(task_queue, lockfile))
                p.start()
                processes.append(p)
                
    except exceptions.KeyboardInterrupt:
        logging.info('Wait until tasks complete...')
        print 'Wait until tasks complete...'
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
