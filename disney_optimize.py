#!/usr/bin/env python3
import time
import argparse
import copy
import json
import base64

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

SLEEP_TIME = 60  # seconds
POINTS_IN_BATCH = 1


def WaitCompleteness(jobs):
    while True:
        time.sleep(SLEEP_TIME)

        ids = [job.id for point in jobs for job in point]
        all_jobs_list = stub.ListJobs(ListJobsRequest())
        submitted_jobs = [job for job in all_jobs_list.jobs if job.id in ids]
        jobs_completed = [job.status
                          in STATUS_FINAL
                          for job in submitted_jobs]
        # jobs_completed = [stub.GetJob(RequestWithId(id=job.id)).status
        #                   in STATUS_FINAL
        #                   for point in jobs
        #                   for job in point]

        if all(jobs_completed):
            break

        print("[{}] Waiting...".format(time.time()))


def ExtractParams(metadata):
    params = json.loads(metadata)['user']['params']
    return common.ParseParams(params)


def ProcessPoint(jobs, space, tag):
    if json.loads(jobs[0].metadata)['user']['tag'] == tag:
        try:
            weight, length, _, muons_w = get_result(jobs)
            y = common.FCN(weight, muons_w, length)
            X = ExtractParams(jobs[0].metadata)

            stub.CreateJob(Job(
                input='',
                output=str(y),
                kind='point',
                metadata=jobs[0].metadata
            ))
            print(X, y)
            return X, y
        except Exception as e:
            print(e)


def ProcessJobs(jobs, space, tag):
    print("[{}] Processing jobs...".format(time.time()))
    results = [
        ProcessPoint(point, space, tag)
        for point in jobs
    ]
    print(f"Got results {results}")
    results = [result for result in results if result]
    if results:
        return zip(*results)
    else:
        return [], []


def CreateJobInput(point, number):
    job = copy.deepcopy(config.JOB_TEMPLATE)
    job['descriptor']['container']['cmd'] = \
        job['descriptor']['container']['cmd'].format(
            params=base64.b64encode(str(point).encode('utf8')).decode('utf8'),
            sampling=37,
            seed=1,
            job_id=number+1
        )

    return json.dumps(job)


def get_result(jobs):
    results = []
    for job in jobs:
        if job.status != Job.COMPLETED:
            raise Exception(
                "Incomplete job while calculating result: %d",
                job.id
            )

        var = [o for o in job.output if o.startswith("variable")][0]
        result = json.load(var.split(":", 1)[1].split("=", 1)[1])
        if result.error:
            raise Exception(results.error)
        results.append(result)

    weight = float([r['weight'] for r in results if r['weight']][0])
    length = float([r['length'] for r in results if r['length']][0])
    if weight < 3e6:
        muons = sum(int(result['muons']) for result in results)
        muons_w = sum(float(result['muons_w']) for result in results)
    else:
        muons, muons_w = None, 0
    return weight, length, muons, muons_w


def CreateMetaData(point, tag, sampling, seed):
    metadata = copy.deepcopy(config.METADATA_TEMPLATE)
    metadata['user'].update([
        ('tag', tag),
        ('params', str(point)),
        ('seed', seed),
        ('sampling', sampling),
    ])
    return json.dumps(metadata)


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


def SubmitDockerJobs(point, tag, sampling, seed):
    return [
        stub.CreateJob(Job(
            input=CreateJobInput(point, i),
            kind='docker',
            metadata=CreateMetaData(point, tag, sampling=sampling, seed=seed)
        ))
        for i in range(16)
    ]


def ProcessPoints(disney_points, tag):
    X = []
    y = []

    for point in disney_points:
        if json.loads(point.metadata)['user']['tag'] == tag:
            try:
                X.append(ExtractParams(point.metadata))
                y.append(float(point.output))
            except Exception as e:
                print(e)

    return X, y


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-opt', help='Write an optimizer.', default='rf')
    clf_type = parser.parse_args().opt
    tag = f'discrete3_{clf_type}'

    space = common.CreateDiscreteSpace()
    clf = Optimizer(
        space,
        RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1)
    ) if clf_type == 'rf' else None

    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point'))
    X, y = ProcessPoints(all_jobs_list.jobs, tag)
    if X and y:
        print('Received previous points ', X, y)
        clf.tell(X, y)
    if not X or (X and len(X) < POINTS_IN_BATCH):
        points = space.rvs(n_samples=POINTS_IN_BATCH)
        points = [common.AddFixedParams(p) for p in points]

        shield_jobs = [
            SubmitPoint(point, tag, sampling=37, seed=1)
            for point in points
        ]

        WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)
        print('Received new points ', X_new, y_new)
        if X_new and y_new:
            clf.tell(X_new, y_new)

    while True:
        points = clf.ask(
            n_points=POINTS_IN_BATCH,
            strategy='cl_mean')

        points = [common.AddFixedParams(p) for p in points]

        shield_jobs = [
            SubmitDockerJobs(point, tag, sampling=37, seed=1)
            for point in points
        ]

        WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)

        print('Received new points ', X_new, y_new)
        clf.tell(X_new, y_new)


if __name__ == '__main__':
    main()
