#!/usr/bin/env python2
import os
import time
from urlparse import urlparse
import tempfile
import numexpr as ne
import subprocess
from multiprocessing import Pipe
from multiprocessing import Process
from multiprocessing import Pool
from multiprocessing import cpu_count
from functools import partial
import argparse
import numpy as np
from skopt import gp_minimize, dump
import ROOT as r
import shipunit as u
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def magnetMass(muonShield):
    """Calculate magnet weight [kg]

    Assumes magnets contained in `MuonShieldArea` TGeoVolumeAssembly and
    contain `Magn` in their name. Calculation is done analytically by
    the TGeoVolume class.

    """
    nodes = muonShield.GetNodes()
    m = 0.
    for node in nodes:
        volume = node.GetVolume()
        if 'Magn' in volume.GetName():
            m += volume.Weight(0.01, 'a')
    return m


def magnetLength(muonShield):
    """Ask TGeoShapeAssembly for magnet length [cm]

    Note: Ignores one of the gaps before or after the magnet

    Also note: TGeoShapeAssembly::GetDZ() returns a half-length

    """
    length = 2 * muonShield.GetShape().GetDZ()
    return length


def FCN(W, x, L):
    """Calculate penalty function.

    W = weight [kg]
    x = array of positions of muon hits in bending plane [cm]
    L = shield length [cm]

    """
    Sxi2 = ne.evaluate('sum(sqrt(560-(x+300.)/560))') if x else 0.
    print W, x, L, Sxi2
    return float(ne.evaluate('0.01*(W/1000)*(1.+Sxi2/(1.-L/10000.))'))


def load_results(fileName):
    f = r.TFile.Open(fileName)
    xs = r.TVectorD()
    # TODO handle key error explicitly instead of using fact that it's not
    # fatal implicitly
    xs.Read('results')
    f.Close()
    return xs


def retrieve_result(outFile):
    print 'Retrieving results from {}.'.format(outFile)
    if args.local:
        pass
    else:
        while True:
            if not check_file(outFile):
                time.sleep(60)  # Wait for job to finish
            else:
                break
    return load_results(outFile)


def check_file(fileName):
    if args.local:
        return os.path.isfile(fileName)
    else:
        parser_ = urlparse(fileName)
        return not bool(
            subprocess.call(
                ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]]))
        # TODO Handle return code more strictly instead of casting to bool?


def check_path(path):
    if args.local:
        return os.path.isdir(path)
    else:
        parser_ = urlparse(path)
        return not bool(
            subprocess.call(
                ['xrdfs', parser_.netloc, 'stat', parser_.path[1:]]))
        # TODO Handle return code more strictly instead of casting to bool?


def worker(id_, geoFile):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    n = (ntotal / args.njobs) + (ntotal % args.njobs
                                 if id_ == args.njobs else 0)
    outFile = '{}/output_files/iteration_{}/{}/result.root'.format(
        args.workDir, os.path.basename(geoFile), id_)
    if args.local:
        path = os.path.dirname(outFile)
        if not os.path.isdir(path):
            os.makedirs(path)
        subprocess.call(
            [
                './slave.py', '--geofile', geoFile, '--jobid', str(id_), '-f',
                worker_filename, '-n', str(n), '--results', outFile, '--lofi'
            ],
            shell=False)
    print 'Master: Worker process {} done.'.format(id_)
    return retrieve_result(outFile)


def get_geo(geoFile, out):
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=vessel_design,
        muShieldDesign=shield_design,
        muShieldGeo=geoFile)

    print 'Config created with ' + geoFile

    with tempfile.NamedTemporaryFile() as t:
        run = r.FairRunSim()
        run.SetName('TGeant4')  # Transport engine
        run.SetOutputFile(t.name)  # Output file
        run.SetUserConfig('g4Config.C')
        shipDet_conf.configure(run, ship_geo)
        run.Init()
        run.CreateGeometryFile('./geo/' + os.path.basename(geoFile))
        sGeo = r.gGeoManager
        muonShield = sGeo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
    out.send((L, W))


def get_bounds():
    dZgap = 0.1 * u.m
    zGap = 0.5 * dZgap  # halflengh of gap
    dZ3 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ4 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ5 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ6 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ7 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    dZ8 = (0.2 * u.m + zGap, 3 * u.m + zGap)
    bounds = [dZ3, dZ4, dZ5, dZ6, dZ7, dZ8]
    for _ in range(8):
        minimum = 0.1 * u.m
        dXIn = (minimum, 2.5 * u.m)
        dXOut = (minimum, 2.5 * u.m)
        dYIn = (minimum, 2.5 * u.m)
        dYOut = (minimum, 2.5 * u.m)
        gapIn = (2., 4.98 * u.m)
        gapOut = (2., 4.98 * u.m)
        bounds += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return bounds


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), np.array(params))
    parray.Write('params')
    f.Close()
    print 'Geofile constructed at ' + geofile
    return geofile


def make_worker_file(id_):
    worker_filename = ('{}/worker_files/muons_{}_{}.root').format(
        args.workDir, id_, args.njobs)
    if check_file(worker_filename):
        print worker_filename, 'exists.'
    else:
        print 'Creating workerfile: ', worker_filename
        f = r.TFile.Open(args.input)
        tree = f.Get('pythia8-Geant4')
        assert check_path(os.path.dirname(worker_filename))
        worker_file = r.TFile.Open(worker_filename, 'recreate')
        n = (ntotal / args.njobs)
        firstEvent = n * (id_ - 1)
        n += (ntotal % args.njobs if id_ == args.njobs else 0)
        worker_data = tree.CopyTree('', '', n, firstEvent)
        worker_data.Write()
        worker_file.Close()


def main():
    pool = Pool(processes=min(args.njobs, cpu_count()))
    pool.map(make_worker_file, range(1, args.njobs + 1))

    def compute_FCN(params):
        params = [0.7 * u.m, 1.7 * u.m] + params  # Add constant parameters
        geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
            args.workDir, compute_FCN.counter), params)
        geoFileLocal = generate_geo('{}/input_files/geo_{}.root'.format(
            '.', compute_FCN.counter), params) if not args.local else geoFile
        out_, in_ = Pipe(duplex=False)
        ids = range(1, args.njobs + 1)
        geo_process = Process(target=get_geo, args=[geoFileLocal, in_])
        geo_process.start()
        partial_worker = partial(worker, geoFile=geoFile)
        results = pool.map(partial_worker, ids, 1)
        L, W = out_.recv()
        print 'Processing results...'
        fcn = FCN(W, np.array(results), L)
        assert np.isclose(L / 2., sum(params[:8]) +
                          5), 'Analytical and ROOT lengths are not the same.'
        compute_FCN.counter += 1
        print fcn
        return fcn

    compute_FCN.counter = 57
    bounds = get_bounds()
    res = gp_minimize(compute_FCN, bounds, n_calls=100)
    print res
    compute_FCN(res.x)
    pool.close()
    pool.join()
    dump(res, 'minimisation_result')


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/data/Mbias/'
        'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '--workDir',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/user/olantwin/skygrid')
    parser.add_argument(
        '-j',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    assert args.local ^ ('root://' in args.workDir), (
        'Please specify a local workDir if not working on EOS.\n')
    ntotal = 17786274  # full sample
    # ntotal = 86229  # fast muons
    # TODO read total number from muon file directly
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    simEngine = 'MuonBack'
    sameSeed = 1
    theSeed = 1
    main()
