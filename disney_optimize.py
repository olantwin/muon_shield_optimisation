import numpy as np
import time
import argparse

import disney_common as common

from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import GaussianProcessRegressor, RandomForestRegressor, GradientBoostingQuantileRegressor
from skopt.space.space import Integer, Space

import grpc
import disneylandClient.disneyland_pb2
from disneylandClient.disneyland_pb2 import Job, RequestWithId, ListOfJobs, ListJobsRequest, DisneylandStub

SLEEP_TIME = 5  # seconds
POINTS_IN_BATCH = 100
FIXED_PARAMS = [
    70.0, 170.0, 40.0, 40.0, 150.0, 150.0, 2.0,
    2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0
]


def WaitCompleteness(jobs):
    while True:
        time.sleep(SLEEP_TIME)
        jobs_completed = [stub.GetJob(RequestWithId(
            id=x.id)).status in STATUS_FINAL for x in jobs]
        if all(jobs_completed):
            break


def ProcessJobs(jobs, space, tag):
    X = []
    y = []

    for job in jobs:
        if job.kind == tag and job.status == disneylandClient.disneyland_pb2.Job.COMPLETED:
            params = common.StripFixedParams(ParseParams(job.input))
            if space.__contains__(params):
                X.append(params)
                y.append(float(job.output))
    return X, y


STATUS_IN_PROGRESS = set([
    disneylandClient.disneyland_pb2.Job.PENDING,
    disneylandClient.disneyland_pb2.Job.PULLED,
    disneylandClient.disneyland_pb2.Job.RUNNING,
])
STATUS_FINAL = set([
    disneylandClient.disneyland_pb2.Job.COMPLETED,
    disneylandClient.disneyland_pb2.Job.FAILED,
])

config_dict = disneylandClient.initClientConfig(
    "/Users/sashab1/.disney/config.yml")
creds = disneylandClient.getCredentials()
channel = grpc.secure_channel(config_dict.get("connect_to"), creds)
stub = DisneylandStub(channel)


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-opt', help='Write an optimizer.')
    clf_type = parser.parse_args().opt
    tag = "discrete2_{opt}".format(opt=clf_type)

    space = common.CreateDiscreteSpace()
    if clf_type == 'rf':
        clf = Optimizer(
            space,
            RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1)
        )

    all_jobs = stub.ListJobs(ListJobsRequest())
    X, y = ProcessJobs(all_jobs, space, tag)
    clf.tell(X, y)

    while True:
        points = clf.ask(
            n_points=POINTS_IN_BATCH,
            strategy='cl_mean')

        points = [common.AddFixedParams(p) for p in points]

        docker_jobs = []
        for point in points:
            docker_jobs.append(stub.CreateJob(
                Job(input=str(point), kind='docker-job', metadata=tag)))

        WaitCompleteness(docker_jobs)

        shield_jobs = []
        for job in docker_jobs:
            if job.status == disneylandClient.disneyland_pb2.Job.COMPLETED:
                # not sure about that line
                shield_jobs.append(stub.CreateJob(Job(input=job.output,
                                                      kind='shield-configuration',
                                                      metadata=tag)))

        WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)
        clf.tell(X_new, y_new)


if __name__ == '__main__':
    main()
