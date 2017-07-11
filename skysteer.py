import json
import os
from sh import xrdfs, kinit
from libscheduler import Metascheduler
from time import sleep, time
import copy
import traceback
from sh import pscp


METASCHEDULER_URL = "http://metascheduler.cern.tst.yandex.net/"
ms = Metascheduler(METASCHEDULER_URL)
queue = ms.queue("docker_queue")


JOB_TEMPLATE = {
    "descriptor": {
        "input": [
            # "local:/home/sashab1/ship-shield/code/worker.sh",
            # "local:/home/sashab1/ship-shield/code/slave.py",
        ],

        "container" : {
            "workdir" : "",
            "name" : "olantwin/ship-shield:20170531",
            "volumes": ["/home/sashab1/ship-shield:/shield"],
            "cpu_needed" : 1,
            "max_memoryMB" : 1024,
            "min_memoryMB" : 512,
            "run_id": "alexey_run2",
            "cmd": "/bin/bash -l -c 'source /opt/FairShipRun/config.sh;  python2 /shield/code/slave.py --geofile /shield/geofiles/{geofile} -f /shield/worker_files/muons_{job_id}_16.root --results /output/result.csv --hists /output/hists.root'",
        },

        "required_outputs": {
            "output_uri": "host:/srv/local/skygrid-local-storage/$JOB_ID",
            "file_contents": [
                {"file": "result.csv", "to_variable": "result"}
            ]
        }
    }
}


def push_jobs_for_geofile(geofile):
    print "Submitting job for geofile ", geofile
    jobs = []
    for i in xrange(1, 16+1):
        tmpl = copy.deepcopy(JOB_TEMPLATE)
        tmpl['descriptor']['container']['cmd'] = tmpl['descriptor']['container']['cmd'].format(geofile=geofile, job_id=i)

        for retry in xrange(5):
            try:
                job = queue.put(tmpl)
                jobs.append(job)
                break
            except Exception, e:
                traceback.print_exc()
                print "Got exception ", e

    print time(), "Pushed geofile ", geofile
    return jobs


def wait_jobs(jobs):
    wait_started = time()
    job_submitted = {job.job_id: wait_started for job in jobs}
    completed = 0
    while True:
        sleep(60)
        print time(), " Checking jobs for completeness...",

        for job in jobs:
            if job.status == "completed":
                continue
            try:
                job.load_from_api()
            except:
                pass

            if job.status == "completed":
                completed += 1
            elif job.status == "failed" or (job.status == "running" and (time() - job_submitted[job.job_id]) > 10 * 60 * 60.):
                print "\t Resubmitting ", job.job_id
                try:
                    job.update_status("pending")
                    job_submitted[job.job_id] = time()
                except: pass

            if completed == 0 and time() - wait_started > 10 * 60 * 60.:
                print "More than 5hours passed and no jobs completed. Stopping this geofile."
                return

        print "  [{}/{}]".format(completed, len(jobs))
        if completed == len(jobs):
            print time(), "All jobs completed!"
            break

def get_result(jobs):
    sum_result = 0.
    for job in jobs:
        if job.status != "completed":
            raise Exception("Incomplete job while calculating result:" +job.job_id)
            continue

        var = filter(lambda o: o.startswith("variable"), job.output)[0]
        result = float(var.split(":", 1)[1].split("=", 1)[1])
        sum_result += result

    print "Sum: ", sum_result
    return sum_result


def distribute_geofile(geofile):
    print "Running pscp for geofile ", geofile
    if not os.path.isfile(geofile):
        raise Exception("Geofile does not exist")

    for retry in xrange(1):
        try:
            pscp("-r", "-h", "/home/sashab1/shield-control/hosts.txt", geofile, "/home/sashab1/ship-shield/geofiles/")
            break
        except Exception, e:
            print "error in pscp:", e.stderr


def dump_jobs(jobs, geo_filename):
    with open("logs/"+geo_filename+"_jobs.json", "w") as f:
        json.dump([{"job_id": j.job_id, "output": j.output} for j in jobs], f)


def calculate_geofile(geofile):
    distribute_geofile(geofile)
    geo_filename = geofile.split("/")[-1]
    jobs = push_jobs_for_geofile(geo_filename)
    wait_jobs(jobs)
    dump_jobs(jobs, geo_filename)
    return get_result(jobs)


def main():
    print "The result for geo_1 is:", calculate_geofile("geo_1.root")

if __name__ == '__main__':
    main()
