#!/usr/bin/env python3
import argparse
import pickle

from .disney_common import (AddFixedParams, CreateDiscreteSpace, StripFixedParams)
from importance_sampling_config import POINTS_IN_BATCH

from utils import (WaitCompleteness, ProcessJobs, ConvertToPoints, CollectResults, SubmitDockerJobs)

import disneylandClient
from disneylandClient import (
    ListJobsRequest
)

from optimization import CreateOptimizer

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
    tag = "important_sampling_{args.opt}_{args.tag}".format(**args)
    print(tag)

    space = CreateDiscreteSpace()
    clf = CreateOptimizer(
        args.opt,
        space,
        random_state=args.state
    )

    all_jobs_list = stub.ListJobs(ListJobsRequest(kind='point', how_many=0))
    X, y = ConvertToPoints(all_jobs_list.jobs, tag)

    if len(X) > 0:
        print('Received previous points ', X, y)
        X = [StripFixedParams(point) for point in X]
        clf.tell(X, y)

    while True:
        points = clf.ask(
            n_points=POINTS_IN_BATCH,
            strategy='cl_mean')

        points = [AddFixedParams(p) for p in points]

        shield_jobs = []
        for j in range(len(points)):
            SubmitDockerJobs(points[j], tag, sampling='IS', seed=1, point_id=j, share=0.05, tag="impsampl")

        shield_jobs = WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)

        print('Received new points ', X_new, y_new)
        X_new = [StripFixedParams(point) for point in X_new]
        result = clf.tell(X_new, y_new)
        CollectResults("impsampl")

        with open('optimiser.pkl', 'wb') as f:
            pickle.dump(clf, f)

        with open('result.pkl', 'wb') as f:
            pickle.dump(result, f)


if __name__ == '__main__':
    main()
