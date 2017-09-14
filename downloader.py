import json
import os
from sh import scp, hadd, rm
import glob
from multiprocessing import Queue, Pool, Process, Manager
import errno


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def download_single_file(output, i, tmp_dir):
    for retry in xrange(5):
        try:
            scp(output.split(":",1)[1], tmp_dir+"/{}.root".format(i))
            break
        except Exception, e:
            print "[{}] Error occured {}".format(retry, str(e))


def create_merged_file(logfile):
    print "Processing ", logfile
    if not logfile.endswith(".root_jobs.json"):
        print "Odd filename, skipping!"
        return

    hist_basename = logfile.replace("logs/", "").replace(".root_jobs.json", "")
    hist_fname = "hists/" + hist_basename + ".root"
    tmp_dir = "tmp/" + hist_basename
    mkdir_p(tmp_dir)

    if os.path.exists(hist_fname):
        print "Histogram already exists, skipping!"
        return

    with open(logfile) as f:
        jobs = json.load(f)

    for i, job in enumerate(jobs):
        for output in job['output']:
            if output.endswith(".root") and 'cern-mc40h.ydf.yandex.net' not in output:
                download_single_file(output, i, tmp_dir)
                print "Copied", output

    tmpfiles = glob.glob(tmp_dir + "/*.root")

    hadd(hist_fname, tmpfiles)
    rm("-rf", tmp_dir)


def worker(task_queue):
    while not task_queue.empty():
        try:
            path = task_queue.get(True, 3)
        except:
            continue

        create_merged_file(path)


def main():
    manager = Manager()
    task_queue = manager.Queue()

    # files = os.listdir("logs")
    # for f in files:
    #     task_queue.put("logs/"+f)
    #task_queue.put("logs/geo_b93fdcb746647b91eb9436c0f5b6480f.root_jobs.json")
    task_queue.put("logs/geo_d920d0ab360af1663ee766a992e710dc.root_jobs.json")
    #task_queue.put("logs/geo_1.root_jobs.json")

    p = Pool(10)

    pool = Pool(10, worker, (task_queue,))
    pool.close()
    pool.join()



if __name__ == '__main__':
    main()
