#!/usr/bin/env python2
import os
import argparse
import ROOT as r
import shipunit as u
import geomGeant4
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
from analyse import analyse


def generate(inputFile, geoFile, nEvents, outFile, lofi=False, seed=1):
    """Generate muon background and transport it through the geometry.

    Parameters
    ----------
    inputFile : str
        File with muon ntuple
    geoFile : str
        File with the muon shield parameters (not with the geometry config!)
    nEvents : int
        Number of events to read from inputFile
    outFile : str
        File in which `cbmsim` tree is saved
    lofi : bool, optional
        Determine fidelity. If True all non-essential Geant4
        processes will be deactivated
    seed : int
        Determines the seed passed on to the MuonBackGenerator instance

    """
    firstEvent = 0
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    sameSeed = seed
    theSeed = 1

    # provisionally for making studies of various muon background sources
    inactivateMuonProcesses = lofi
    phiRandom = False  # only relevant for muon background generator
    followMuon = True  # only transport muons for a fast muon only background

    print 'FairShip setup to produce', nEvents, 'events'
    r.gRandom.SetSeed(theSeed)
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=vessel_design,
        muShieldDesign=shield_design,
        muShieldGeo=geoFile)

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
    nEvents = min(nEvents, MuonBackgen.GetNevents())
    print 'Process ', nEvents, ' from input file, with Phi random=', phiRandom
    if followMuon:
        modules['Veto'].SetFastMuon()
    run.SetGenerator(primGen)
    run.SetStoreTraj(r.kFALSE)
    run.Init()
    geomGeant4.setMagnetField()
    if inactivateMuonProcesses:
        mygMC = r.TGeant4.GetMC()
        mygMC.ProcessGeantCommand('/process/inactivate muPairProd')
        mygMC.ProcessGeantCommand('/process/inactivate muBrems')
        mygMC.ProcessGeantCommand('/process/inactivate muIoni')
        mygMC.ProcessGeantCommand('/process/inactivate msc')
        mygMC.ProcessGeantCommand('/process/inactivate Decay')
        mygMC.ProcessGeantCommand('/process/inactivate CoulombScat')
        mygMC.ProcessGeantCommand('/process/inactivate muonNuclear')
        mygMC.ProcessGeantCommand('/process/inactivate StepLimiter')
        mygMC.ProcessGeantCommand('/process/inactivate specialCutForMuon')
    run.Run(nEvents)
    print 'Macro finished succesfully.'


def main():
    n = args.nEvents
    # TODO read total number from muon file directly OR
    # TODO always pass from steering process?

    outFile = "/output/ship.conical.MuonBack-TGeant4.root"
    try:
        generate(args.input, args.geofile, n, outFile, args.lofi, args.seed)
    except:
        with open(args.results, 'w') as f:
            f.write("{}\n".format('-1'))
        return

    try:
        chain = r.TChain('cbmsim')
        chain.Add(outFile)
        xs = analyse(chain, args.hists)
        with open(args.results, 'w') as f:
            f.write("{}\n".format(sum(xs)))
    except:
        with open(args.results, 'w') as f:
            f.write("{}\n".format('-2'))

    os.remove(outFile)


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
    parser.add_argument('--results', default='test.csv')
    parser.add_argument('--hists', default='hists.root')
    parser.add_argument('--geofile', required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('-n', '--nEvents', type=int, default=10000000)
    parser.add_argument('--lofi', action='store_true')
    args = parser.parse_args()
    main()
