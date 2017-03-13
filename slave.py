#!/usr/bin/env python2
import os
import tempfile
import argparse
import ROOT as r
import shipunit as u
import geomGeant4
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def generate(inputFile, geoFile, nEvents, outFile, lofi=True):
    # nEvents = 100
    firstEvent = 0
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    sameSeed = 1
    theSeed = 1

    # provisionally for making studies of various muon background sources
    inactivateMuonProcesses = lofi
    phiRandom = False  # only relevant for muon background generator
    followMuon = False  # only transport muons for a fast muon only background

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
    if hasattr(ship_geo, 'muShieldDesign'):
        if ship_geo.muShieldDesign != 1:
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
    id_ = args.jobid
    outputDir = '.'
    worker_filename = '{}_{}.root'.format(id_, args.njobs)
    n = (ntotal / args.njobs)
    firstEvent = n * (id_ - 1)
    n += (ntotal % args.njobs if id_ == args.njobs else 0)
    print id_, 'Produce', n, 'events starting with event', firstEvent
    # TODO split in steering process
    if os.path.isfile(worker_filename):
        print worker_filename, 'exists.'
    else:
        f = r.TFile.Open(args.input)
        tree = f.Get('pythia8-Geant4')
        worker_file = r.TFile.Open(worker_filename, 'recreate')
        worker_data = tree.CopyTree('', '', n, firstEvent)
        worker_data.Write()
        worker_file.Close()
    if not os.path.exists(outputDir):
        os.makedirs(outputDir)

    with tempfile.NamedTemporaryFile() as t:
        generate(worker_filename, args.geofile, n, t.name, args.lofi)
        ch = r.TChain('cbmsim')
        ch.Add(t.name)
        xs = []
        mom = r.TVector3()
        for event in ch:
            for hit in event.strawtubesPoint:
                if hit:
                    if not hit.GetEnergyLoss() > 0:
                        continue
                    if hit.GetDetectorID() / 10000000 == 4 and abs(hit.PdgCode(
                    )) == 13:
                        hit.Momentum(mom)
                        P = mom.Mag() / u.GeV
                        y = hit.GetY()
                        x = hit.GetX()
                        if (
                                P > 1 and abs(y) < 5 * u.m and
                                (x < 2.6 * u.m and x > -3 * u.m)
                        ):
                            xs.append(x)
    # TODO write results
    print 'Worker process {} done.'.format(id_)


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='root:/eoslhcb.cern.ch/'
        '/eos/ship/data/Mbias/'
        'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '--results',
        default='test.pkl'  # TODO EOS
    )
    parser.add_argument('--geofile')
    parser.add_argument('--jobid', type=int)
    parser.add_argument('--lofi', action='store_true')
    args = parser.parse_args()
    ntotal = 86229
    # TODO read total number from muon file directly
    main()
