import json
from time import sleep, time
import logging
import copy
import traceback
from libscheduler import Metascheduler
import config
from disney_common import create_id


METASCHEDULER_URL = "http://metascheduler.cern.tst.yandex.net/"
ms = Metascheduler(METASCHEDULER_URL)
queue = ms.queue("docker_queue")


def push_jobs_for_params(params, sampling, seed):
    point_id = create_id(params)
    logging.info("Submitting job for id %s", point_id)
    jobs = []
    for i in xrange(1, 16+1):
        tmpl = copy.deepcopy(config.JOB_TEMPLATE)
        tmpl['descriptor']['container']['cmd'] = tmpl['descriptor']['container']['cmd'].format(params=params, job_id=i, sampling=sampling, seed=seed)

        for _ in xrange(5):
            try:
                job = queue.put(tmpl)
                jobs.append(job)
                break
            except Exception, e:
                traceback.print_exc()
                logging.exception("Got exception %r", e.stderr)

    logging.info("%r Pushed point: %s", time(), point_id)
    return jobs


def is_failed_due_to_docker(job):
    for _ in xrange(5):
        try:
            debug = job.get_debug() or {}
            return "devmapper" in debug.get('exception', "")
        except Exception, e:
            traceback.print_exc()
            logging.exception("Got exception %r", e.stderr)
    return False


def wait_jobs(jobs):
    log = logging.getLogger('wait jobs')
    wait_started = time()
    job_metadata = {
        job.job_id: {
            "resubmits": 0,
            "last_update": wait_started
        }
        for job in jobs
    }
    completed = 0
    while completed < len(jobs):
        sleep(60)
        log.info("%s Checking jobs for completeness...", time())

        for job in jobs:
            if job.status == "completed":
                continue
            try:
                job.load_from_api()
            except:
                pass

            if job.status == "completed":
                completed += 1
            elif job.status == "failed" or (
                    job.status == "running"
                    and (
                        time() - job_metadata[job.job_id]['last_update']
                    ) > 10 * 60 * 60.):
                log.info("\t Resubmitting %s %s", job.job_id, job.status)
                try:
                    job.update_status("pending")
                    job_metadata[job.job_id]['last_update'] = time()

                    if not is_failed_due_to_docker(job):
                        job_metadata[job.job_id]['resubmits'] += 1
                except:
                    pass

            timeout_passed = time() - wait_started > 10 * 60 * 60.
            too_many_resubmits = all(
                v['resubmits'] > 5
                for _, v in job_metadata.items()
            )
            if completed == 0 and (timeout_passed or too_many_resubmits):
                raise Exception(
                    "More than 2 hours passed and no jobs completed."
                    if timeout_passed else
                    "Too many resubmits, canceling execution"
                )

        log.info("  [%d/%d]", completed, len(jobs))
    log.info("%r All jobs completed!", time())


def get_result(jobs):
    results = []
    for job in jobs:
        if job.status != "completed":
            raise Exception(
                "Incomplete job while calculating result: %d",
                job.job_id
            )

        var = [o for o in job.output if o.startswith("variable")][0]
        result = json.load(var.split(":", 1)[1].split("=", 1)[1])
        if result.error:
            logging.error(results.error)
        results.append(result)

    # TODO sanity check: check that weights/lengths agree
    weight = float(results[0]['weight'])
    length = float(results[0]['length'])
    muons = sum(int(result['muons']) for result in results)
    muons_w = sum(float(result['muons_w']) for result in results)
    return weight, length, muons, muons_w


def dump_jobs(jobs, geo_filename):
    with open("logs/"+geo_filename+"_jobs.json", "w") as f:
        json.dump(({"job_id": j.job_id, "output": j.output} for j in jobs), f)


def calculate_params(params, sampling, seed):
    jobs = push_jobs_for_params(params, sampling, seed)
    dump_jobs(jobs, params)
    wait_jobs(jobs)
    dump_jobs(jobs, params)
    return get_result(jobs)
