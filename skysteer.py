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
            "name" : "olantwin/ship-shield:20170420",
            "volumes": ["/home/sashab1/ship-shield:/shield"],
            "cpu_needed" : 1,
            "max_memoryMB" : 1024,
            "min_memoryMB" : 512,
            "cmd": "/bin/bash -l -c 'source /opt/FairShipRun/config.sh;  python2 /shield/code/slave.py --geofile /shield/geofiles/{geofile} --jobid {job_id} -f /shield/worker_files/muons_{job_id}_1600.root --results /output/result.csv'",
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
    jobs = []
    for i in xrange(1,1601):
        tmpl = copy.deepcopy(JOB_TEMPLATE)
        tmpl['descriptor']['container']['cmd'] = tmpl['descriptor']['container']['cmd'].format(geofile=geofile, job_id=i)
        # tmpl['descriptor']['input'] += [
        #     "local:" + os.path.join(GEO_DIR, geofile),
        #     "local:/home/sashab1/ship-shield/worker_files/muons_{}_1600.root".format(i),
        # ]

        for retry in xrange(5):
            try:
                job = queue.put(tmpl)
                print "Submitted job {} for worker {} and geofile {}".format(job.job_id, i, geofile)
                jobs.append(job)
                break
            except Exception, e:
                traceback.print_exc()
                print "Got exception ", e

    print time(), "Pushed geofile ", geofile
    return jobs


def wait_jobs(jobs):
    completed = 0
    while True:
        sleep(60)
        print time(), " Checking jobs for completeness...",

        for job in jobs:
            if job.status == "completed":
                continue

            job.load_from_api()
            if job.status == "completed":
                completed += 1
            elif job.status == "failed":
                print "\t Resubmitting ", job.job_id
                job.update_status("pending")

        print "  [{}/{}]".format(completed, len(jobs))
        if completed == 1600:
            print time(), "All jobs completed!"
            break

def get_result(jobs):
    sum_result = 0.
    for job in jobs:
        if job.status != "completed":
            print "Incomplete job while calculating result:", job.job_id
            continue

        var = filter(lambda o: o.startswith("variable"), job.output)[0]
        result = float(var.split(":", 1)[1].split("=", 1)[1])
        sum_result += result

    print "Sum: ", sum_result
    return sum_result


def distribute_geofile(geofile):
    pscp("-r", "-h", "/home/sashab1/shield-control/hosts.txt", geofile, "/home/sashab1/ship-shield/geofiles/")


def calculate_geofile(geofile):
    distribute_geofile(geofile)
    jobs = push_jobs_for_geofile(geofile.split("/")[-1])
    wait_jobs(jobs)
    return get_result(jobs)


def main():
    print "The result for geo_36 is:", calculate_geofile("geo_36.root")

if __name__ == '__main__':
    main()