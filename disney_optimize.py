#!/usr/bin/env python3
import time
import argparse
import copy
import json
import base64

import disney_common as common
from disney_oneshot import get_result, CreateJobInput, CreateMetaData
import config

import disneylandClient
from disneylandClient import (
    Job,
    RequestWithId,
    ListJobsRequest
)

from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import GaussianProcessRegressor
from skopt.learning import RandomForestRegressor
from skopt.learning import GradientBoostingQuantileRegressor

SLEEP_TIME = 60  # seconds
POINTS_IN_BATCH = 1

class RandomSearchOptimizer:
    def __init__(self, space):
        self.space_ = space
    
    def tell(self, X, y):
        pass
    
    def ask(self, n_points=1, strategy=None):
        return self.space_.rvs(n_points)


def CreateOptimizer(clf_type, space):
    if clf_type == 'rf':
        clf = Optimizer(
            space,
            RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1)
        )
    elif clf_type == 'gb':
        clf = Optimizer(
            space,
            GradientBoostingQuantileRegressor(
                base_estimator=GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=4,
                    loss='quantile'
                )
            )
        )
    elif clf_type == 'gp':
        clf = Optimizer(
            space,
            GaussianProcessRegressor(
                alpha=1e-7,
                normalize_y=True,
                noise='gaussian'
            )
        )
    else:
        clf = RandomSearchOptimizer(space)
    
    return clf


def WaitCompleteness(jobs):

    work_time = 0
    while True:
        time.sleep(SLEEP_TIME)

        ids = [[job.id for job in point] for point in jobs]
        uncompleted_jobs = [
            [
                stub.GetJob(RequestWithId(id=id))
                for id in point
            ]
            for point in ids
        ]
        jobs_completed = [job.status
                          in STATUS_FINAL
                          for point in uncompleted_jobs
                          for job in point]

        if all(jobs_completed):
            return uncompleted_jobs

        print("[{}] Waiting...".format(time.time()))
        work_time += 60

        if work_time > 60 * 60 * 3:
            completed_jobs = []
            for point in uncompleted_jobs:
                if all([job.status in STATUS_FINAL for job in point]):
                    completed_jobs.append(point)

            return completed_jobs
    


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
        if tag == 'all' or json.loads(point.metadata)['user']['tag'] == tag:
            try:
                X.append(ExtractParams(point.metadata))
                y.append(float(point.output))
            except Exception as e:
                print(e)

    return X, y


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-opt', help='Write an optimizer.', default='rf')
    parser.add_argument('-tag', help='Write tag', default='')
    clf_type = parser.parse_args().opt
    additional_tag = parser.parse_args().tag
    tag = f'mitesh_1d_{clf_type}_{additional_tag}'

    space = common.CreateDiscreteSpace()

    clf = CreateOptimizer(clf_type, space)


    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point', how_many=100000))
    X, y = ProcessPoints(all_jobs_list.jobs, tag)

    if X and y:
        print('Received previous points ', X, y)
        X = [common.StripFixedParams(point) for point in X]
        clf.tell(X, y)
    if not X or (X and len(X) < POINTS_IN_BATCH):
        points = space.rvs(n_samples=POINTS_IN_BATCH)
        points = [common.AddFixedParams(p) for p in points]

        shield_jobs = [
            SubmitDockerJobs(point, tag, sampling=37, seed=1)
            for point in points
        ]

        shield_jobs = WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)
        print('Received new points ', X_new, y_new)
        if X_new and y_new:
            X_new = [common.StripFixedParams(point) for point in X_new]
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

        shield_jobs = WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)

        print('Received new points ', X_new, y_new)

        X_new = [common.StripFixedParams(point) for point in X_new]

        clf.tell(X_new, y_new)


if __name__ == '__main__':
    main()
