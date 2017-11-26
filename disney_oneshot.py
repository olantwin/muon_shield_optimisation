#!/usr/bin/env python3
import time
import json
import base64
import copy
import config
import disney_common as common

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
    stub = new_client()

    space = common.CreateDiscreteSpace()
    point = common.AddFixedParams(space.rvs()[0])

    job = Job(
        input=CreateJobInput(point, 15),
        kind="docker",
        metadata=CreateMetaData(point, 'test', sampling=37, seed=1)
    )

    job = stub.CreateJob(job)
    print("Job", job)

    while True:
        time.sleep(3)
        job = stub.GetJob(RequestWithId(id=job.id))
        print("[{}] Job :\n {}\n".format(time.time(), job))

        if job.status in STATUS_FINAL:
            break

    if job.status == Job.FAILED:
        print("Job failed!")

    print("result:", json.loads(job.output))


if __name__ == '__main__':
    main()
