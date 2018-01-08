#!/usr/bin/env python3
import time
import json
import base64
import copy
import argparse
from disneylandClient import (
    new_client,
    Job,
    RequestWithId,
)
import config
from config import RUN
import disney_common as common

STATUS_IN_PROCESS = set([
    Job.PENDING,
    Job.PULLED,
    Job.RUNNING,
])
STATUS_FINAL = set([
    Job.COMPLETED,
    Job.FAILED,
])


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
            raise
    return [], []


def ExtractParams(metadata):
    params = json.loads(metadata)['user']['params']
    return common.ParseParams(params)


def get_result(jobs):
    results = []
    for job in jobs:
        if job.status != Job.COMPLETED:
            raise Exception(
                "Incomplete job while calculating result: %d",
                job.id
            )

        var = [o for o in json.loads(job.output)
               if o.startswith("variable")][0]
        result = json.loads(var.split("=", 1)[1])
        if result['error']:
            raise Exception(result['error'])
        results.append(result)

    # Only one job per machine calculates the weight and the length
    # -> take first we find
    weight = float([r['weight'] for r in results if r['weight']][0])
    length = float([r['length'] for r in results if r['length']][0])
    if weight < 3e6:
        muons = sum(int(result['muons']) for result in results)
        muons_w = sum(float(result['muons_w']) for result in results)
    else:
        muons, muons_w = None, 0
    return weight, length, muons, muons_w


def CreateMetaData(point, tag, sampling, seed):
    metadata = copy.deepcopy(config.METADATA_TEMPLATE)
    metadata['user'].update([
        ('tag', tag),
        ('params', str(point)),
        ('seed', seed),
        ('sampling', sampling),
    ])
    return json.dumps(metadata)


def CreateJobInput(point, number, sampling, seed):
    job = copy.deepcopy(config.JOB_TEMPLATE)
    job['container']['cmd'] = \
        job['container']['cmd'].format(
            params=base64.b64encode(str(point).encode('utf8')).decode('utf8'),
            sampling=sampling,
            seed=seed,
            job_id=number+1
        )

    return json.dumps(job)


def WaitForCompleteness(jobs, verbose=False):
    uncompleted_jobs = jobs

    while True:
        time.sleep(3)
        uncompleted_jobs = [
            stub.GetJob(RequestWithId(id=job.id))
            for job in uncompleted_jobs
        ]
        if verbose:
            print("[{}] Job :\n {}\n".format(time.time(), uncompleted_jobs[0]))
        else:
            print("[{}] Waiting...".format(time.time()))

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
    return jobs


def CalculatePoint(point, seed, sampling, tag, verbose=False):
    jobs = [
        stub.CreateJob(Job(
            input=CreateJobInput(point, i, sampling=sampling, seed=seed),
            kind='docker',
            metadata=CreateMetaData(point, tag, sampling=sampling, seed=seed)
        ))
        for i in range(16)
    ]

    if verbose:
        print("Job", jobs[0])

    return ProcessPoint(WaitForCompleteness(jobs, verbose=verbose), tag)


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-p', '--point', default=None)
    parser.add_argument(
        '--seed',
        help='Random seed of simulation',
        default=1
    )
    parser.add_argument(
        '--sampling',
        help='Muon sample to use.',
        default=37
    )
    args = parser.parse_args()
    tag = f'{RUN}_oneshot'
    if args.point:
        point = common.ParseParams(args.point)
    else:
        space = common.CreateDiscreteSpace()
        point = common.AddFixedParams(space.rvs()[0])

    print("result:", CalculatePoint(point, seed=args.seed, sampling=args.sampling, tag=tag, verbose=True))


if __name__ == '__main__':
    stub = new_client()
    main()
