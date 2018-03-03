#!/usr/bin/env python3
import base64
import json
import copy
import time

from muon_shield_optimisation.disney_oneshot import (
    get_result,
    CreateMetaData,
    ExtractParams,
    STATUS_IN_PROCESS,
    STATUS_FINAL
)

from disneylandClient import (Job, RequestWithId, ListJobsRequest)

from config import JOB_TEMPLATE_IMP_SAMPLING, IMAGE_TAG, SLEEP_TIME
from muon_shield_optimisation.weighter.config import JOB_TEMPLATE as JOB_COLLECTOR_TEMPLATE
from muon_shield_optimisation.disney_common import (FCN)

def CreateSimulationJobInput(point, sampling, seed, point_id, share, tag):
    job = copy.deepcopy(JOB_TEMPLATE_IMP_SAMPLING)
    job['container']['cmd'] = \
        job['container']['cmd'].format(
            params=base64.b64encode(str(point).encode('utf8')).decode('utf8'),
            sampling=sampling,
            seed=seed,
            job_id=0,
            IMAGE_TAG=IMAGE_TAG,
            point_id=point_id,
            share=share,
            tag=tag
        )

    return json.dumps(job)


def CreateCollectorJobInput(tag, number_of_points):
    job = copy.deepcopy(JOB_COLLECTOR_TEMPLATE)
    main_path = 'eos:/eos/experiment/ship/skygrid/importance_sampling'

    job['input'].append(main_path + "/cumloss.npy")
    job['input'].append(main_path + "/cumindeces.npy")
    job['container']['cmd'] = \
        job['container']['cmd'].format(
            tag=tag
        )

    return json.dumps(job)


def SubmitDockerJobs(stub, point, user_tag, sampling, seed, point_id, share, tag):
    return [
        stub.CreateJob(Job(
            input=CreateSimulationJobInput(point, sampling, seed, point_id, share, tag),
            kind='docker',
            metadata=CreateMetaData(point, user_tag, sampling=sampling, seed=seed)
        ))
        ]


def ProcessJob(stub, job, space, tag):
    if json.loads(job[0].metadata)['user']['tag'] == tag:
        try:
            weight, length, _, muons_w = get_result(job)
            y = FCN(weight, muons_w, length)
            X = ExtractParams(job[0].metadata)

            stub.CreateJob(Job(
                input='',
                output=str(y),
                kind='point',
                metadata=job[0].metadata
            ))

            print(X, y)
            return X, y
        except Exception as e:
            print(e)


def ProcessJobs(stub, jobs, space, tag):
    print("[{}] Processing jobs...".format(time.time()))
    results = [
        ProcessJob(stub, job, space, tag)
        for job in jobs
    ]
    print(f"Got results {results}")
    results = [result for result in results if result]
    if results:
        return zip(*results)
    else:
        return [], []


def WaitCompleteness(stub, jobs):
    work_time = 0
    while True:
        time.sleep(SLEEP_TIME)

        ids = [[job.id for job in point] for point in jobs]
        jobs = [
            [
                stub.GetJob(RequestWithId(id=id))
                for id in point
            ]
            for point in ids
        ]
        jobs_completed = [job.status
                          in STATUS_FINAL
                          for point in jobs
                          for job in point]

        if all(jobs_completed):
            return jobs

        print("[{}] Waiting...".format(time.time()))
        work_time += 60

        if work_time > 60 * 60 * 3:
            completed_jobs = []
            for point in jobs:
                if all([job.status in STATUS_FINAL for job in point]):
                    completed_jobs.append(point)

            return completed_jobs


def CollectResults(stub, tag, number_of_points):
    job_input = CreateCollectorJobInput(tag, number_of_points)
    job = stub.CreateJob(Job(
        input=job_input,
        kind='docker'
    ))
    WaitCompleteness(stub, [[job]])


def ConvertToPoints(disney_points, tag):
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
