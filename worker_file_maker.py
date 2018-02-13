#!/usr/bin/env python2
import subprocess
from multiprocessing import Pool, cpu_count
import os
from urlparse import urlparse
from functools import partial
from itertools import ifilter
import argparse
import rootpy.ROOT as r


f, tree = None, None


def init_filemaker():
    global f, tree
    f = r.TFile.Open(args.input)
    tree = f.Get('pythia8-Geant4')


def filemaker(id_, local):
    # requires init_worker_files to initialise worker process
    assert id_
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename, local):
        print worker_filename, 'exists.'
    else:
        print 'Creating workerfile: ', worker_filename
        worker_file = r.TFile.Open(worker_filename, 'recreate')
        n = (ntotal / args.njobs)
        firstEvent = n * (id_ - 1)
        n += (ntotal % args.njobs if id_ == args.njobs else 0)
        worker_data = tree.CopyTree('', '', n, firstEvent)
        worker_data.Write()
        worker_file.Close()


def check_worker_file(id_, local):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename, local, strict=False):
        print worker_filename, 'exists.'
    else:
        return id_


def check_file(fileName, local, strict=True):
    if local:
        return os.path.isfile(fileName)
    else:
        parser_ = urlparse(fileName)
        try:
            command = ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]]
            if strict:
                command += ['-q', 'IsReadable']
            output = subprocess.check_output(command)
            for line in output.split('\n'):
                if 'Size' in line:
                    size = line.split(' ')[-1]
                    if int(size) != 0:
                        print output
                    return int(size) != 0
            print output
        except subprocess.CalledProcessError:
            return False


def check_path(path, local):
    if local:
        return os.path.isdir(path)
    else:
        parser_ = urlparse(path)
        try:
            subprocess.check_output(
                ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]])
            return True
        except subprocess.CalledProcessError as e:
            print e.returncode, e.output
            return False


def main():
    pool = Pool(
        processes=min(args.njobs, cpu_count()))
    assert check_path('{}/worker_files'.format(args.workDir), args.local)
    ids = range(1, args.njobs + 1)
    missing_files = pool.imap_unordered(
        partial(check_worker_file, local=args.local),
        ids
    )
    pool.close()
    pool.join()
    pool = Pool(
        processes=min(args.njobs, cpu_count()), initializer=init_filemaker)
    missing_ids = ifilter(None, missing_files)
    pool.imap_unordered(
        partial(filemaker, local=args.local),
        missing_ids
    )
    pool.close()
    pool.join()


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='root://eospublic.cern.ch/'
        '/eos/experiment/ship/data/Mbias/'
        'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '--workDir',
        default='root://eospublic.cern.ch/'
        '/eos/experiment/ship/user/olantwin/skygrid')
    parser.add_argument(
        '-j',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    assert args.local ^ ('root://' in args.workDir), (
        'Please specify a local workDir if not working on EOS.\n')
    ntotal = 17786274
    # TODO read total number from muon file directly
    main()
