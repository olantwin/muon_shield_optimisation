import time
import argparse

import disney_common as common

from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import GaussianProcessRegressor, RandomForestRegressor, GradientBoostingQuantileRegressor

import grpc
from disneylandClient import new_client, Worker, Job, RequestWithId
from disneylandClient import Job, RequestWithId, ListOfJobs, ListJobsRequest, DisneylandStub

SLEEP_TIME = 5  # seconds
POINTS_IN_BATCH = 100


def WaitCompleteness(jobs):
    while True:
        time.sleep(SLEEP_TIME)

        jobs_completed = [stub.GetJob(RequestWithId(id=x.id)).status in STATUS_FINAL
                          for x in docker_jobs
                          for docker_jobs in jobs]

        if all(jobs_completed):
            break


def ParseJobOutput(job_output):
    return 0, 0, 0


def ProcessJobs(jobs, space, tag):
    X = []
    y = []

    for dokcer_jobs in jobs:
        chi2s = 0
        failed = 0
        for docker_job in docker_jobs:
            if docker_job.metadata == tag and docker_job.status == Job.COMPLETED:
                chi2, weight, length = ParseJobOutput(docker_job.output)
                chi2s += chi2

            elif docker_job.status == Job.FAILED:
                failed = 1
                break

        if failed == 0:
            params = common.ParseParams(docker_job[0].input['params'])
            if params in space:
                X.append(params)
                y.append(common.FCN(weight, chi2s, length))
    return X, y


def CreateJobInput(point, number):
    return JOB_TEMPLATE


STATUS_IN_PROGRESS = set([
    Job.PENDING,
    Job.PULLED,
    Job.RUNNING,
])
STATUS_FINAL = set([
    Job.COMPLETED,
    Job.FAILED,
])

JOB_TEMPLATE = {}

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

        shield_jobs = []
        for point in points:
            docker_jobs = []
            for i in xrange(16):
                docker_jobs.append(stub.CreateJob(Job(input=CreateJobInput(point, i),
                                                      kind='shield-configuration',
                                                      metadata=tag)))
            shield_jobs.append(docker_jobs)

        WaitCompleteness(shield_jobs)
        X_new, y_new = ProcessJobs(shield_jobs, space, tag)
        clf.tell(X_new, y_new)


if __name__ == '__main__':
    main()
