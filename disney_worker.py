#!/usr/bin/env python2
import os
import time
import json
from multiprocessing import Queue, Process
import logging
import filelock
from skysteer import calculate_geofile
import grpc
from fcn import FCN
import disneylandClient.disneyland_pb2
from disneylandClient.disneyland_pb2 import Job, RequestWithId, ListOfJobs, ListJobsRequest, DisneylandStub
import disney_common as common
from common import generate_geo
import config

SLEEP_TIME = 5 * 60  # seconds
WORK_DIR = 'root://eoslhcb.cern.ch/'
'/eos/ship/user/olantwin/skygrid'
CONFIG_PATH = "/Users/sashab1/.disney/config.yml"

config_dict = disneylandClient.initClientConfig(CONFIG_PATH)
creds = disneylandClient.getCredentials()
channel = grpc.secure_channel(config_dict.get("connect_to"), creds)
stub = DisneylandStub(channel)


def dump_params(path, params_json_str):
    with open(path, "w") as f:
        f.write(params_json_str)


def compute_FCN(job):
    log = logging.getLogger('compute_fcn')
    log.info("=" * 5 + "compute_FCN:{}".format(job.id) + "=" * 5)

    dump_params(
        '{}/params/{}.json'.format(WORK_DIR, job.id),
        job.input
    )

    geoFile = '{}/input_files/geo_{}.root'.format(WORK_DIR, job.id)
    if not os.path.isfile(geoFile):
        log.error("Geofile does not exist, exiting!")
        job.status = disneylandClient.disneyland_pb2.Job.FAILED
        stub.ModifyJob(job)
        return

    with open(os.path.join(WORK_DIR, 'input_files/geo_{}.lw.csv'.format(job.id))) as lw_f:
        length, weight = map(float, lw_f.read().strip().split(","))

    result = {'weight': weight, 'length': length, 'metric': 1e+8, 'chi2s': -1}

    if weight < 3e+6:
        try:
            chi2s = calculate_geofile(geoFile, sampling=37, seed=1)
        except Exception, e:
            log.exception(e)
            job.status = disneylandClient.disneyland_pb2.Job.FAILED
            stub.ModifyJob(job)
            return

        metric = FCN(weight, chi2s, length)
        result['metric'] = metric
        result['chi2s'] = chi2s

    job.output = json.dumps(result)
    job.status = disneylandClient.disneyland_pb2.Job.COMPLETED
    stub.ModifyJob(job)

    log.info("Job completed: %s", job.id)


def fcn_worker(task_queue, lockfile):
    while True:
        job = task_queue.get()
        if not job:
            break

        lock = filelock.FileLock(lockfile)
        with lock:
            create_geofile(job)

        compute_FCN(job)


def create_geofile(job):
    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        WORK_DIR, job.id), common.ParseParams(job.input))

    log = logging.getLogger('create_geofile')
    try:
        log.info("Running docker: " + job.input)
        docker.run(
            "--rm",
            "-v", "{}:/shield".format(WORK_DIR),
            "{}:{}".format(config.IMAGE, config.IMAGE_TAG),
            '/bin/bash',
            '-l',
            '-c',
            "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{0}.root -o /shield/input_files/geo_{0}.lw.csv".format(
                job.id)
        )
        log.info("Docker finished!")
        return True
    except Exception, e:
        log.exception(
            'Docker finished with error, hope it is fine! %s',
            e
        )
        return False


def main():
    logging.basicConfig(
        filename='./logs/runtime.log',
        level=logging.INFO,
        format="%(asctime)s %(process)s %(thread)s: %(message)s"
    )
    n_workers = 98
    processes = []

    while True:
        pulled_jobs = stub.PullPendingJobs(ListJobsRequest(
            how_many=100, kind='shield-configuration'))

        task_queue = Queue()
        for job in pulled_jobs.jobs:
            task_queue.put(job)

        for worker_id in xrange(n_workers):
            task_queue.put(None)
            lockfile = "/tmp/shield-{}.lock".format((worker_id + 1) % 15)
            p = Process(target=fcn_worker, args=(task_queue, lockfile))
            p.start()
            processes.append(p)

        time.sleep(SLEEP_TIME)


if __name__ == '__main__':
    main()
