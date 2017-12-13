#!/usr/bin/env python3
import time
import argparse
import copy
import json
import base64

import disney_common as common
from disney_oneshot import (
    get_result,
    CreateJobInput,
    CreateMetaData,
    ExtractParams,
    ProcessPoint,
    STATUS_IN_PROCESS,
    STATUS_FINAL
)
import config
from config import RUN, POINTS_IN_BATCH, RANDOM_STARTS

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


class RandomSearchOptimizer:
    def __init__(self, space, random_state=None):
        self.space_ = space
        self.state_ = random_state

    def tell(self, X, y):
        pass

    def ask(self, n_points=1, strategy=None):
        return self.space_.rvs(n_points, random_state=self.state_)


def CreateOptimizer(clf_type, space, random_state=None):
    if clf_type == 'rf':
        clf = Optimizer(
            space,
            RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1),
            random_state=random_state
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
            ),
            random_state=random_state
        )
    elif clf_type == 'gp':
        clf = Optimizer(
            space,
            GaussianProcessRegressor(
                alpha=1e-7,
                normalize_y=True,
                noise='gaussian'
            ),
            random_state=random_state
        )
    else:
        clf = RandomSearchOptimizer(space, random_state=random_state)

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
    parser.add_argument('--opt', help='Write an optimizer.', default='rf')
    parser.add_argument('--tag', help='Additional suffix for tag', default='')
    parser.add_argument(
        '--state',
        help='Random state of Optimizer',
        default=None
    )
    args = parser.parse_args()
    tag = f'{RUN}_{args.opt}' + '_{args.tag}' if args.tag else ''

    space = common.CreateDiscreteSpace()

    clf = CreateOptimizer(args.opt, space, random_state=int(args.state))

    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point', how_many=0))
    X, y = ProcessPoints(all_jobs_list.jobs, tag)

    if X and y:
        print('Received previous points ', X, y)
        X = [common.StripFixedParams(point) for point in X]
        clf.tell(X, y)
    while not (X and len(X) > RANDOM_STARTS):
        points = space.rvs(
            n_samples=POINTS_IN_BATCH,
            random_state=int(args.state)
        )
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
