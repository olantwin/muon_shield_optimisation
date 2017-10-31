#!/usr/bin/env python3
import time
import argparse
import copy
import json

import disney_common as common
import config


from skopt import Optimizer
from skopt.learning import RandomForestRegressor

import disneylandClient
from disneylandClient import (
    Job,
    RequestWithId,
    ListJobsRequest
)

SLEEP_TIME = 5  # seconds
POINTS_IN_BATCH = 100


def WaitCompleteness(jobs):
    while True:
        time.sleep(SLEEP_TIME)

        jobs_completed = [stub.GetJob(RequestWithId(id=x.id)).status
                          in STATUS_FINAL
                          for docker_jobs in jobs
                          for x in docker_jobs]

        if all(jobs_completed):
            break


def ExtractParams(docker_cmd):
    cmd_string = json.loads(docker_cmd)['descriptor']['container']['cmd']
    params = cmd_string[
        cmd_string.find('--params ')
        + len('--params '):
        cmd_string.find(' -f')
    ]
    return json.loads(params)


def ProcessJobs(jobs, space, tag):
    X = []
    y = []

    for docker_jobs in jobs:
        if docker_jobs[0].metadata == tag:
            try:
                weight, length, _, muons_w = common.get_result(docker_jobs)
                y.append(common.FCN(weight, muons_w, length))
                X.append(ExtractParams(docker_jobs[0].input))
            except:
                pass
    return X, y


def CreateJobInput(point, number):
    job = copy.deepcopy(config.JOB_TEMPLATE)
    job['descriptor']['container']['cmd'] = \
        job['descriptor']['container']['cmd'].format(
            params=str(point),
            sampling=37,
            seed=1,
            job_id=number
        )

    return job


STATUS_IN_PROGRESS = set([
    Job.PENDING,
    Job.PULLED,
    Job.RUNNING,
])
STATUS_FINAL = set([
    Job.COMPLETED,
    Job.FAILED,
])

stub = disneylandClient.new_client()


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-opt', help='Write an optimizer.', default='rf')
    clf_type = parser.parse_args().opt
    tag = 'discrete2_{opt}'.format(opt=clf_type)

    space = common.CreateDiscreteSpace()
    clf = Optimizer(
        space,
        RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1)
    ) if clf_type == 'rf' else None

    all_jobs_list = stub.ListJobs(ListJobsRequest())
    X, y = ProcessJobs(all_jobs_list.jobs, space, tag)
    if X and y:
        clf.tell(X, y)

    while True:
        points = clf.ask(
            n_points=POINTS_IN_BATCH,
            strategy='cl_mean')

        points = [common.AddFixedParams(p) for p in points]

        shield_jobs = [
            [
                stub.CreateJob(Job(
                    input=CreateJobInput(point, i),
                    kind='docker',
                    metadata=tag
                ))
                for i in range(16)
            ]
            for point in points
        ]

        WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)
        clf.tell(X_new, y_new)


if __name__ == '__main__':
    main()
