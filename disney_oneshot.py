#!/usr/bin/env python3
import time
import json
import base64
import copy
import config
import disney_common as common
from disney_common import get_result

from disneylandClient import (
    new_client,
    Job,
    RequestWithId,
)

STATUS_IN_PROCESS = set([
    Job.PENDING,
    Job.PULLED,
    Job.RUNNING,
])
STATUS_FINAL = set([
    Job.COMPLETED,
    Job.FAILED,
])


def CreateMetaData(point, tag, sampling, seed):
    metadata = copy.deepcopy(config.METADATA_TEMPLATE)
    metadata['user'].update([
        ('tag', tag),
        ('params', str(point)),
        ('seed', seed),
        ('sampling', sampling),
    ])
    return json.dumps(metadata)


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


def main():
    space = common.CreateDiscreteSpace()
    point = common.AddFixedParams(space.rvs()[0])

    jobs = [
        stub.CreateJob(Job(
            input=CreateJobInput(point, i),
            kind='docker',
            metadata=CreateMetaData(point, 'test_oneshot', sampling=37, seed=1)
        ))
        for i in range(16)
    ]
    uncompleted_jobs = jobs

    print("Job", jobs[0])

    while True:
        time.sleep(3)
        uncompleted_jobs = [
            stub.GetJob(RequestWithId(id=job.id))
            for job in uncompleted_jobs
        ]
        print("[{}] Job :\n {}\n".format(time.time(), uncompleted_jobs[0]))

        uncompleted_jobs = [
            job for job in uncompleted_jobs
            if job.status not in STATUS_FINAL
        ]

        if not uncompleted_jobs:
            break

    jobs = [stub.GetJob(RequestWithId(id=job.id)) for job in jobs]

    if any(job.status == Job.FAILED for job in jobs):
        print("Job failed!")
        print(list(job for job in jobs if job.status == Job.FAILED))
        raise SystemExit(1)

    print("result:", get_result(jobs))


if __name__ == '__main__':
    stub = new_client()
    main()
