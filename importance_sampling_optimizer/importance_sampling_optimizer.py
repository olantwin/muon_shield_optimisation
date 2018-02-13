#!/usr/bin/env python3
import argparse
import pickle

import .disney_common as common
from importance_sampling_config import POINTS_IN_BATCH

import disneylandClient
from disneylandClient import (
    Job,
    RequestWithId,
    ListJobsRequest
)

from result_collector.config import JOB_TEMPLATE as JOB_COLLECTOR_TEMPLATE
stub = disneylandClient.new_client()

def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('--opt', help='Write an optimizer.', default='rf')
    parser.add_argument('--tag', help='Additional suffix for tag', default='')
    parser.add_argument(
        '--state',
        help='Random state of Optimizer',
        type=int
    )
    args = parser.parse_args()
    tag = f'important_sampling_{args.opt}' + f'_{args.tag}' if args.tag else ''
    print(tag)

    space = common.CreateDiscreteSpace()
    clf = CreateOptimizer(
        args.opt,
        space,
        random_state=args.state
    )


    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point', how_many=0))
    X, y = ConvertToPoints(all_jobs_list.jobs, tag)

    if len(X) > 0:
        print('Received previous points ', X, y)
        X = [common.StripFixedParams(point) for point in X]
        clf.tell(X, y)

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
        result = clf.tell(X_new, y_new)
        CollectResults()

        with open('optimiser.pkl', 'wb') as f:
            pickle.dump(clf, f)

        with open('result.pkl', 'wb') as f:
            pickle.dump(result, f)


if __name__ == '__main__':
    main()
