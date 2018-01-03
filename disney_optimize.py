#!/usr/bin/env python3
import time
import argparse
import json
import pickle

import disneylandClient
from disneylandClient import (
    Job,
    RequestWithId,
    ListJobsRequest
)

from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import (
    GaussianProcessRegressor,
    RandomForestRegressor,
    GradientBoostingQuantileRegressor
)

import disney_common as common
from disney_oneshot import (
    get_result,
    CreateJobInput,
    CreateMetaData,
    ExtractParams,
    WaitForCompleteness,
    STATUS_FINAL
)
import config
from config import RUN, POINTS_IN_BATCH, RANDOM_STARTS

SLEEP_TIME = 60  # seconds


def ProcessPoint(jobs, tag):
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
            # TODO modify original jobs to mark them as processed,
            # job_id of point
            print(X, y)
            return X, y
        except Exception as e:
            print(e)


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
        clf = Optimizer(
            space,
            base_estimator='dummy',
            random_state=random_state
        )

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

        print('[{}] Waiting...'.format(time.time()))
        work_time += 60

        if work_time > 60 * 60 * 3:
            completed_jobs = []
            for point in uncompleted_jobs:
                if all([job.status in STATUS_FINAL for job in point]):
                    completed_jobs.append(point)

            return completed_jobs


def ProcessJobs(jobs, tag):
    print('[{}] Processing jobs...'.format(time.time()))
    results = [
        ProcessPoint(point, tag)
        for point in jobs
    ]
    print(f'Got results {results}')
    results = [result for result in results if result]
    return zip(*results) if results else ([], [])


stub = disneylandClient.new_client()


def SubmitDockerJobs(point, tag, sampling, seed):
    return [
        stub.CreateJob(Job(
            input=CreateJobInput(point, i, sampling=sampling, seed=seed),
            kind='docker',
            metadata=CreateMetaData(point, tag, sampling=sampling, seed=seed)
        ))
        for i in range(16)
    ]


def ProcessPoints(points):
    X = []
    y = []

    for point in points:
        try:
            X.append(ExtractParams(point.metadata))
            y.append(float(point.output))
        except Exception as e:
            print(e)

    return X, y


def FilterPoints(points, seed, sampling,
                 image_tag=config.IMAGE_TAG, tag='all'):
    filtered = []
    for point in points:
        metadata = json.loads(point.metadata)['user']
        if (
                (tag == 'all' or metadata['tag'] == tag)
                and metadata['image_tag'] == image_tag
                and (metadata['seed'] == seed or seed == 'all')
                and (metadata['sampling'] == sampling or sampling == 'all')
        ):
            filtered.append(point)
    return filtered


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('--opt', help='Write an optimizer.', default='rf')
    parser.add_argument('--tag', help='Additional suffix for tag', default='')
    parser.add_argument(
        '--state',
        help='Random state of Optimizer',
        default=None
    )
    parser.add_argument(
        '--seed',
        help='Random seed of simulation',
        default=1
    )
    parser.add_argument(
        '--sampling',
        default=37
    )
    args = parser.parse_args()
    tag = f'{RUN}_{args.opt}' + f'_{args.tag}' if args.tag else ''

    MIN = [70.0, 170.0, 275.0, 300.0, 226.0, 204.0, 235.0, 239.0, 40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0, 77.0, 58.0, 104.0, 60.0, 57.0, 22.0, 33.0, 10.0, 35.0, 99.0, 15.0, 69.0, 60.0, 27.0, 179.0, 38.0, 30.0, 61.0, 13.0, 14.0, 135.0, 158.0, 57.0, 60.0, 12.0, 49.0, 22.0, 72.0, 24.0, 16.0, 47.0, 67.0, 68.0, 154.0, 6.0, 53.0]

    space = common.CreateReducedSpace(MIN, 0.1)

    clf = CreateOptimizer(
        args.opt,
        space,
        random_state=int(args.state) if args.state else None
    )

    # TODO use random points for init, don't tag them with optimiser

    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point', how_many=0))
    # TODO request multiple tags
    X, y = ProcessPoints(
        FilterPoints(
            all_jobs_list.jobs, tag=tag, seed=args.seed, sampling=args.sampling))

    if X and y:
        print('Received previous points ', X, y)
        X = [common.StripFixedParams(point) for point in X]
        clf.tell(*zip(*[x, loss for x, loss in zip(X, y) if space.__contains__(x)])
    while not (X and len(X) > RANDOM_STARTS):
        points = space.rvs(n_samples=POINTS_IN_BATCH)
        points = [common.AddFixedParams(p) for p in points]

        shield_jobs = [
            SubmitDockerJobs(
                point,
                tag,
                sampling=args.sampling,
                seed=args.seed)
            # TODO change tag
            for point in points
        ]

        shield_jobs = WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, tag)
        print('Received new points ', X_new, y_new)
        if X_new and y_new:
            X_new = [common.StripFixedParams(point) for point in X_new]
            clf.tell(*zip(*[x, loss for x, loss in zip(X_new, y_new) if space.__contains__(x)])

    while True:
        points = clf.ask(
            n_points=POINTS_IN_BATCH,
            strategy='cl_mean')

        result = []

        shield_jobs = [
            SubmitDockerJobs(
                point,
                tag,
                sampling=args.sampling,
                seed=args.seed)
            for point in points
        ]

        shield_jobs = WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, tag)

        print('Received new points ', X_new, y_new)

        X_new = [common.StripFixedParams(point) for point in X_new]

        result = clf.tell(*zip(*[x, loss for x, loss in zip(X_new, y_new) if space.__contains__(x)])

        with open('optimiser.pkl', 'wb') as f:
            pickle.dump(clf, f)

        with open('result.pkl', 'wb') as f:
            pickle.dump(result, f)


if __name__ == '__main__':
    main()
