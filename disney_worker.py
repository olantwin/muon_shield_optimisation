#!/usr/bin/env python2
import time
import json
from multiprocessing import Queue, Process
import logging
from skysteer import calculate_point
import grpc
import disneylandClient.disneyland_pb2
from disneylandClient.disneyland_pb2 import ListJobsRequest, DisneylandStub
from disney_common import FCN

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

    try:
        weight, length, muons, muons_w = calculate_point(
            params=job.input,
            sampling=37,
            seed=1
        )
    except Exception, e:
        log.exception(e)
        job.status = disneylandClient.disneyland_pb2.Job.FAILED
        stub.ModifyJob(job)
        return

    metric = FCN(weight, muons_w, length) if weight < 3e6 else 1e8

    result = {
        'weight': weight,
        'length': length,
        'metric': metric,
        'chi2s': muons_w,
        'muons': muons
    }

    job.output = json.dumps(result)
    job.status = disneylandClient.disneyland_pb2.Job.COMPLETED
    stub.ModifyJob(job)

    log.info("Job completed: %s", job.id)


def fcn_worker(task_queue, lockfile):
    while True:
        job = task_queue.get()
        if not job:
            break

        compute_FCN(job)


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
