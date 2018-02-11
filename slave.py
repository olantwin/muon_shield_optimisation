#!/usr/bin/env python2
import os
from time import sleep
import numpy as np
import copy
import json
import argparse
import shutil
import subprocess
import filelock
import ROOT as r
import config
import shipunit as u
import geomGeant4
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
from analyse import analyse
from disney_common import create_id, ParseParams
from common import generate_geo


def generate(
        inputFile,
        paramFile,
        outFile,
        seed=1,
        nEvents=None
):
    """Generate muon background and transport it through the geometry.

    Parameters
    ----------
    inputFile : str
        File with muon ntuple
    paramFile : str
        File with the muon shield parameters
    outFile : str
        File in which `cbmsim` tree is saved
    seed : int
        Determines the seed passed on to the MuonBackGenerator instance
    nEvents : int
        Number of events to be read from inputFile

        If falsy, generate will run over the entire file.

    """
    firstEvent = 0
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    sameSeed = seed
    theSeed = 1

    phiRandom = False  # only relevant for muon background generator
    followMuon = True  # only transport muons for a fast muon only background

    print 'FairShip setup to produce', nEvents, 'events'
    r.gRandom.SetSeed(theSeed)
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=vessel_design,
        muShieldDesign=shield_design,
        muShieldGeo=paramFile)

    run = r.FairRunSim()
    run.SetName(mcEngine)  # Transport engine
    run.SetOutputFile(outFile)  # Output file
    # user configuration file default g4Config.C
    run.SetUserConfig('g4Config.C')
    modules = shipDet_conf.configure(run, ship_geo)
    primGen = r.FairPrimaryGenerator()
    primGen.SetTarget(ship_geo.target.z0 + 50 * u.m, 0.)
    MuonBackgen = r.MuonBackGenerator()
    MuonBackgen.Init(inputFile, firstEvent, phiRandom)
    MuonBackgen.SetSmearBeam(3 * u.cm)  # beam size mimicking spiral
    if sameSeed:
        MuonBackgen.SetSameSeed(sameSeed)
    primGen.AddGenerator(MuonBackgen)
    if not nEvents:
        nEvents = MuonBackgen.GetNevents()
    else:
        nEvents = min(nEvents, MuonBackgen.GetNevents())
    print 'Process ', nEvents, ' from input file, with Phi random=', phiRandom
    if followMuon:
        modules['Veto'].SetFastMuon()
    run.SetGenerator(primGen)
    run.SetStoreTraj(r.kFALSE)
    run.Init()
    print 'Initialised run.'
    geomGeant4.setMagnetField()
    print 'Start run of {} events.'.format(nEvents)
    run.Run(nEvents)
    print 'Finished simulation of {} events.'.format(nEvents)


def main():

    tmpl = copy.deepcopy(config.RESULTS_TEMPLATE)
    tmpl['args'] = vars(args)
    with open(args.results, 'w') as f:
        json.dump(tmpl, f)

    tmpl['status'] = 'Parsing parameters...'
    try:
        params = ParseParams(args.params.decode('base64'))
    except Exception as e:
        tmpl['error'] = e.__repr__()
        with open(args.results, 'w') as f:
            json.dump(tmpl, f)
        raise
    tmpl['status'] = 'Parsed parameters.'
    paramFile = '/shared/params_{}.root'.format(
        create_id(params)
    )
    geoinfoFile = paramFile.replace('params', 'geoinfo')
    heavy = '/shared/heavy_{}'.format(create_id(params))
    lockfile = paramFile + '.lock'

    if os.path.exists(geoinfoFile):
        geolockfile = geoinfoFile + '.lock'
        lock = filelock.FileLock(geolockfile)
        if not lock.is_locked:
            with lock:
                with open(geoinfoFile, 'r') as f:
                    length, weight = map(float, f.read().strip().split(','))

                tmpl['weight'] = weight
                tmpl['length'] = length

    while not os.path.exists(paramFile) and not os.path.exists(heavy):
        lock = filelock.FileLock(lockfile)
        if not lock.is_locked:
            with lock:
                tmpl['status'] = 'Aquired lock.'
                tmp_paramFile = generate_geo(
                    paramFile.replace('.', '.tmp.'),
                    params
                )
                subprocess.call(
                    [
                        'python2',
                        '/code/get_geo.py',
                        '-g', tmp_paramFile,
                        '-o', geoinfoFile
                        ])
                shutil.move(
                    '/shield/geofiles/' + os.path.basename(tmp_paramFile),
                    paramFile.replace(
                        'shared', 'output'
                    ).replace(
                        'params', 'geo'
                    )
                )
                with open(geoinfoFile, 'r') as f:
                    length, weight = map(float, f.read().strip().split(','))

                tmpl['weight'] = weight
                tmpl['length'] = length
                if weight < 3e6:
                    shutil.move(tmp_paramFile, paramFile)
                else:
                    open(heavy, 'a').close()
                    with open(args.results, 'w') as f:
                        json.dump(tmpl, f)
                tmpl['status'] = 'Created geometry.'
        else:
            sleep(60)

    if os.path.exists(heavy):
        tmpl['status'] = 'Too heavy.'
        tmpl['error'] = None
        with open(args.results, 'w') as f:
            json.dump(tmpl, f)
        return

    outFile = "/output/ship.conical.MuonBack-TGeant4.root"
    try:
        try:
            tmpl['status'] = 'Simulating...'
            generate(
                inputFile=args.input,
                paramFile=paramFile,
                outFile=outFile,
                seed=args.seed,
                nEvents=args.nEvents
            )
        except Exception as e:
            raise RuntimeError(
                "Simulation failed with exception: %s",
                e
            )
        try:
            tmpl['status'] = 'Analysing...'
            chain = r.TChain('cbmsim')
            chain.Add(outFile)
            xs = analyse(chain, args.hists)
            np.save(args.xs_path, np.array(xs))
            tmpl['muons'] = len(xs)
            tmpl['muons_w'] = sum(xs)
        except Exception as e:
            raise RuntimeError(
                "Analysis failed with exception: %s",
                e
            )
        tmpl['error'] = None
        tmpl['status'] = 'Done.'
    except RuntimeError, e:
        tmpl['error'] = e.__repr__()
    finally:
        with open(args.results, 'w') as f:
            json.dump(tmpl, f)
        if os.path.exists(outFile):
            os.remove(outFile)


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
    parser.add_argument('--results', default='results.json')
    parser.add_argument('--hists', default='hists.root')
    parser.add_argument('--params', required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--xs_path', default='xs.npz')
    parser.add_argument('-n', '--nEvents', type=int)

    args = parser.parse_args()
    main()
