#!/usr/bin/env python2
import argparse
import tempfile
import numpy as np
import ROOT as r
import shipunit as u
import geomGeant4
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
import rootUtils as ut


def generate(inputFile, geoFile, nEvents, outFile, lofi=False):
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
    h = {}
    id_ = args.jobid
    n = args.nEvents if args.nEvents else 100000
    # TODO read total number from muon file directly OR
    # TODO always pass from steering process?

    ut.bookHist(h, 'mu_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'anti-mu_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'mu_w_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'anti-mu_w_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'mu_p', '#mu+-;p[GeV];', 100, 0, 350)
    xs = r.std.vector('double')()
    with tempfile.NamedTemporaryFile() as t:
        outFile = t.name
        generate(args.input, args.geofile, n, outFile, args.lofi)
        ch = r.TChain('cbmsim')
        ch.Add(outFile)
        mom = r.TVector3()
        for event in ch:
            for hit in event.vetoPoint:
                if hit:
                    if (not hit.GetEnergyLoss() > 0) and (not args.lofi):
                        continue
                    pid = hit.PdgCode()
                    if hit.GetZ() > 2597 and hit.GetZ() < 2599 and abs(pid) == 13:
                        hit.Momentum(mom)
                        P = mom.Mag() / u.GeV
                        y = hit.GetY()
                        x = hit.GetX()
                        if pid == 13:
                            h['mu_pos'].Fill(x, y)
                        else:
                            h['anti-mu_pos'].Fill(x, y)
                        x *= pid / 13.
                        if (P > 1 and abs(y) < 5 * u.m and
                                (x < 2.6 * u.m and x > -3 * u.m)):
                            w = np.sqrt(500.-(x+300.)/560.)
                            xs.push_back(w)
                            h['mu_p'].Fill(P)
                            if pid == 13:
                                h['mu_w_pos'].Fill(x, y, w)
                            else:
                                h['anti-mu_w_pos'].Fill(-x, y, w)
    ut.writeHists(h, "test.root")
    with open(args.results, 'w') as f:
        f.write("{}\n".format(sum(xs)))
    print 'Slave: Worker process {} done.'.format(id_)


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
        '--results',
        default='test.csv')
    parser.add_argument('--geofile', required=True)
    parser.add_argument('--jobid', type=int, required=True)
    parser.add_argument('-n', '--nEvents', type=int, default=None)
    parser.add_argument('--lofi', action='store_true')
    args = parser.parse_args()
    main()
