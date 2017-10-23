import json
import os
from time import sleep, time
import logging
import copy
import traceback
from libscheduler import Metascheduler
from sh import pscp
import config


METASCHEDULER_URL = "http://metascheduler.cern.tst.yandex.net/"
ms = Metascheduler(METASCHEDULER_URL)
queue = ms.queue("docker_queue")


JOB_TEMPLATE = {
    "descriptor": {
        "input": [],

        "container": {
            "workdir": "",
            "name": "{}:{}".format(config.IMAGE, config.IMAGE_TAG),
            "volumes": ["/home/sashab1/ship-shield:/shield"],
            "cpu_needed": 1,
            "max_memoryMB": 1024,
            "min_memoryMB": 512,
            "run_id": "near_run3",
            "cmd": "/bin/bash -l -c 'source /opt/FairShipRun/config.sh;  python2 /shield/code/slave.py --geofile /shield/geofiles/{geofile} -f /shield/worker_files/sampling_{sampling}/muons_{job_id}_16.root --results /output/result.csv --hists /output/hists.root --seed {seed}'",
        },

        "required_outputs": {
            "output_uri": "host:/srv/local/skygrid-local-storage/$JOB_ID",
            "file_contents": [
                {"file": "result.csv", "to_variable": "result"}
            ]
        }
    }
}


def push_jobs_for_geofile(geofile, sampling, seed):
    logging.info("Submitting job for geofile {}".format(geofile))
    jobs = []
    for i in xrange(1, 16+1):
        tmpl = copy.deepcopy(JOB_TEMPLATE)
        tmpl['descriptor']['container']['cmd'] = tmpl['descriptor']['container']['cmd'].format(geofile=geofile, job_id=i, sampling=sampling, seed=seed)

        for retry in xrange(5):
            try:
                job = queue.put(tmpl)
                jobs.append(job)
                break
            except Exception, e:
                traceback.print_exc()
                logging.exception("Got exception {}".format(e.stderr))

    logging.info("{} Pushed geofile: {}".format(time(), geofile))
    return jobs


def is_failed_due_to_docker(job):
    for retry in xrange(5):
        try:
            debug = job.get_debug() or {}
            return "devmapper" in debug.get('exception', "")
        except Exception, e:
            traceback.print_exc()
            logging.exception("Got exception {}".format(e.stderr))
    return False


def wait_jobs(jobs):
    log = logging.getLogger('wait jobs')
    wait_started = time()
    job_metadata = {job.job_id: {"resubmits": 0, "last_update": wait_started} for job in jobs}
    # job_submitted = {job.job_id: wait_started for job in jobs}
    completed = 0
    while True:
        sleep(60)
        log.info(str(time()) +  " Checking jobs for completeness...")

        for job in jobs:
            if job.status == "completed":
                continue
            try:
                job.load_from_api()
            except:
                pass

            if job.status == "completed":
                completed += 1
            elif job.status == "failed" or (job.status == "running" and (time() - job_metadata[job.job_id]['last_update']) > 10 * 60 * 60.):
                log.info("\t Resubmitting {} {}".format(job.job_id, job.status))
                try:
                    job.update_status("pending")
                    job_metadata[job.job_id]['last_update'] = time()

                    if not is_failed_due_to_docker(job):
                        job_metadata[job.job_id]['resubmits'] += 1
                except:
                    pass

            timeout_passed = time() - wait_started > 10 * 60 * 60.
            too_many_resubmits = all([v['resubmits'] > 5 for _, v in job_metadata.items()])
            if completed == 0 and (timeout_passed or too_many_resubmits):
                if timeout_passed:
                    raise Exception("More than 2 hours passed and no jobs completed.")
                else:
                    raise Exception("Too many resubmits, canceling execution")

        log.info("  [{}/{}]".format(completed, len(jobs)))
        if completed == len(jobs):
            log.info("{} All jobs completed!".format(time()))
            break

def get_result(jobs):
    sum_result = 0.
    for job in jobs:
        if job.status != "completed":
            raise Exception("Incomplete job while calculating result: {}".format(job.job_id))

        var = filter(lambda o: o.startswith("variable"), job.output)[0]
        result = float(var.split(":", 1)[1].split("=", 1)[1])
        sum_result += result

    logging.info("Sum: {}".format(sum_result))
    return sum_result


def distribute_geofile(geofile):
    log = logging.getLogger('distribute_geofile')
    log.info("Running pscp for geofile {}".format(geofile))
    if not os.path.isfile(geofile):
        raise Exception("Geofile does not exist")

    for retry in xrange(1):
        try:
            pscp("-r", "-h", "/home/sashab1/shield-control/hosts.txt", geofile, "/home/sashab1/ship-shield/geofiles/")
            break
        except Exception, e:
            log.exception("error in pscp: {}".format(e.stderr))


def dump_jobs(jobs, geo_filename):
    with open("logs/"+geo_filename+"_jobs.json", "w") as f:
        json.dump([{"job_id": j.job_id, "output": j.output} for j in jobs], f)


def calculate_geofile(geofile, sampling, seed):
    distribute_geofile(geofile)
    geo_filename = geofile.split("/")[-1]
    jobs = push_jobs_for_geofile(geo_filename, sampling, seed)
    dump_jobs(jobs, geo_filename)
    wait_jobs(jobs)
    dump_jobs(jobs, geo_filename)
    return get_result(jobs)


def main():
    logging.basicConfig(filename = './logs/runtime.log', level = logging.INFO, format="%(asctime)s %(process)s %(thread)s: %(message)s")
    logging.info("The result for geo_1 is: {}".format(calculate_geofile("geo_1.root")))


if __name__ == '__main__':
    main()
