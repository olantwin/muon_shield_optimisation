#!/usr/bin/env python2
import filelock
import os
import argparse
import numpy as np
import ROOT as r
from sh import docker
from skysteer import calculate_geofile
from telegram_notify import notify as tlgrm_notify
#from telegram_notify import notify_image as tlgrm_image
import json
import md5
from multiprocessing import Queue, Process
from common import generate_geo, get_bounds
from fcn import FCN
import MySQLdb
import exceptions
import logging
import time
from downloader import create_merged_file
import random
from models import Point, Base
import sqlalchemy
from sqlalchemy.orm import sessionmaker


engine = sqlalchemy.create_engine('mysql://root:P@ssw0rd@[2a03:b0c0:1:d0::2c4f:1001]/points_prod')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

with open("points.json") as f:
    POINTS = json.load(f)
    f.close()

def parse_params(params_string):
    return [float(x) for x in params_string.strip('[]').split(',')]

def dump_params(path, params_json_str):
    with open(path, "w") as f:
        f.write(params_json_str)

def create_geofile(point):

    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, point.id), parse_params(point.params))

    log = logging.getLogger('create_geofile')
    try:
        log.info("Running docker: " + point.params)
        docker.run(
            "--rm",
            "-v", "{}:/shield".format(args.workDir),
            "olantwin/ship-shield:20170420",
            '/bin/bash',
            '-l',
            '-c',
            "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{0}.root -o /shield/input_files/geo_{0}.lw.csv".format(point.id)
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

def insert_hist(point):
    try:
        create_merged_file('logs/geo_{}.root_jobs.json'.format(point.id))
    except:
        return

    with open('./hists/geo_{}.root'.format(point.id)) as file:
        point.hist = file.read()
        session.commit()
        file.close()


def insert_geofile(point):
    with open('./files/geo/geo_{}.root'.format(point.id)) as file:
        point.geofile = file.read()
        session.commit()
        file.close()



def compute_FCN(point):
    log = logging.getLogger('compute_fcn')
    log.info("="*5 + "compute_FCN:{}".format(point.id) + "="*5)

    dump_params(
        '{}/params/{}.json'.format(args.workDir, point.id),
        point.params
    )

    point.status = 'running'
    session.commit()

    sampling = point.resampled

    if point.seed is None:
        seed = 1
    else:
        seed = point.seed


    geoFile = '{}/input_files/geo_{}.root'.format(args.workDir, point.id)
    if not os.path.isfile(geoFile):
        log.error("Geofile does not exist, exiting!")

        point.geofile_exception = True
        session.commit()
        return

    chi2s = 0
    
    try:
        chi2s = calculate_geofile(geoFile, sampling, seed)
    except Exception, e:
        log.exception(e)
        point.geofile_exception = True
        session.commit()
        tlgrm_notify("Error calculating: [{}]  {}".format(point.params, e))
        return

    with open(os.path.join(args.workDir, 'input_files/geo_{}.lw.csv'.format(point.id))) as lw_f:
        L, W = map(float, lw_f.read().strip().split(","))

    insert_hist(point)
    insert_geofile(point)


    log.info('Processing results...')
    fcn = FCN(W, chi2s, L)
    #render_geofile(geoFile)
    tlgrm_notify("[{}]\nresampled={}\nid={}\ngeo_id={}\nweight={}\nchi2={}\nmetric={:1.3e}".format(point.params, sampling, point.id, point.geo_id, W, chi2s, fcn))
    #tlgrm_image(os.path.splitext(geoFile)[0] + '.png')
    point.weight = W
    point.metric_1 = fcn
    point.chi2 = chi2s
    point.status = 'completed'
    point.tag_image = '20170531'
    point.seed = seed
    session.commit()

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
            the_id = task_queue.get()
            if not the_id:
                break

            latest_id = the_id

            lock = filelock.FileLock(lockfile)

            point = session.query(Point).filter(Point.id == the_id).first()
            with lock:
                result = create_geofile(point)

            compute_FCN(point)

        except BaseException, e:
            log = logging.getLogger('fcn_worker')
            log.exception(e)


            point.params_exception = True
            session.commit()

            tlgrm_notify("Exception occured for paramters: [{}]  {}".format(latest_parameters, e))


def main():
    logging.basicConfig(filename = './logs/runtime.log', level = logging.INFO, format = "%(asctime)s %(process)s %(thread)s: %(message)s")

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
            for ids in POINTS:
                task_queue.put(ids)

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

