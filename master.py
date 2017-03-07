#!/usr/bin/env python2
import os
import random
import tempfile
import numexpr as ne
from multiprocessing import Pipe
from multiprocessing import Process
from multiprocessing import cpu_count
from multiprocessing import current_process
import argparse
import numpy as np
import ROOT as r
import shipunit as u
import geomGeant4
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def generate(inputFile, geoFile, nEvents, outFile):
    nEvents = 100
    firstEvent = 0

    # provisionally for making studies of various muon background sources
    inactivateMuonProcesses = True
    phiRandom = False  # only relevant for muon background generator
    followMuon = False  # only transport muons for a fast muon only background

    print 'FairShip setup for', simEngine, 'to produce', nEvents, 'events'
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
    return ne.evaluate('0.01*(W/1000)*(1.+Sxi2/(1.-L/10000.))')


def worker(master):
    id_ = master.recv()
    ego = current_process()
    worker_filename = '{}_{}.root'.format(id_, args.njobs)
    n = (ntotal / args.njobs)
    firstEvent = n * (id_ - 1)
    n += (ntotal % args.njobs if id_ == args.njobs else 0)
    print id_, ego.pid, 'Produce', n, 'events starting with event', firstEvent
    n = 100
    if os.path.isfile(worker_filename):
        print worker_filename, 'exists.'
    else:
        f = r.TFile.Open('root://eoslhcb.cern.ch/' + args.input)
        tree = f.Get('pythia8-Geant4')
        worker_file = r.TFile.Open(worker_filename, 'recreate')
        worker_data = tree.CopyTree('', '', n, firstEvent)
        worker_data.Write()
        worker_file.Close()
    # Output file name, add dy to be able to setup geometry with ambiguities.
    tag = simEngine + '-' + mcEngine
    tag = 'conical.' + tag
    if not os.path.exists(outputDir):
        os.makedirs(outputDir)

    outFile = '{}/{}.ship.{}.root'.format(outputDir, ego.pid, tag)
    # TODO read geometry from queue after each iteration
    while True:
        geoFile = master.recv()
        if not geoFile:
            break
        p = Process(target=generate, args=(worker_filename, geoFile, n, outFile))
        p.start()
        p.join()
        ch = r.TChain('cbmsim')
        ch.Add(outFile)
        xs = []
        mom = r.TVector3()
        for event in ch:
            weight = event.MCTrack[1].GetWeight()
            if weight == 0:
                weight = 1.
            for hit in event.strawtubesPoint:
                if hit:
                    if not hit.GetEnergyLoss() > 0:
                        continue
                    if hit.GetDetectorID() / 10000000 == 4 and abs(hit.PdgCode(
                    )) == 13:
                        hit.Momentum(mom)
                        P = mom.Mag() / u.GeV
                        if P > 1:
                            y = hit.GetY()
                            if abs(y) < 5 * u.m:
                                x = hit.GetX()
                                if x < 2.6 * u.m and x > -3 * u.m:
                                    xs.append(x)
        master.send(xs)
        os.remove(outFile)
    print 'Worker process {} done.'.format(id_)


def get_geo(geoFile):
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=vessel_design,
        muShieldDesign=shield_design,
        muShieldGeo=geoFile)

    with tempfile.NamedTemporaryFile() as t:
        run = r.FairRunSim()
        run.SetName('TGeant4')  # Transport engine
        run.SetOutputFile(t.name)  # Output file
        run.SetUserConfig('g4Config.C')
        modules = shipDet_conf.configure(run, ship_geo)
        run.Init()
        run.Run(0)
        sGeo = r.gGeoManager
        # sGeo.Export('test.gdml')
        # sGeo = r.TGeoManager.Import('test.gdml')
        iron = sGeo.GetMedium('iron')
        old = sGeo.GetVolume("Magn7_MagBotRight")
        new = sGeo.MakeArb8('test', iron, 5. * u.m, np.array([-80.,-310.,-0.,-390.,-215.,-390.,-135.,-310.,-80.,-310.,-0.,-390.,-215.,-390.,-135.,-310.]))
        assert old
        assert new
        print sGeo.ReplaceVolume(old, new)
        # TODO Remove old volume?
        sGeo.RefreshPhysicalNodes()
        sGeo.Export('test2.gdml')
        # sGeo = r.TGeoManager.Import('test.gdml')
        muonShield = sGeo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
    return L, W


def geo_guessr():
    dZgap = 0.1*u.m
    zGap = 0.5 * dZgap  # halflengh of gap
    dZ1 = 0.7*u.m
    dZ2 = 1.7*u.m
    dZ3 = 2.0*u.m + zGap
    dZ4 = 2.0*u.m + zGap
    dZ5 = 2.75*u.m + zGap
    dZ6 = 2.4*u.m + zGap
    dZ7 = 3.0*u.m + zGap
    dZ8 = 2.35*u.m + zGap
    params = [dZ1, dZ2, dZ3, dZ4, dZ5, dZ6, dZ7, dZ8]
    for i in range(9):
        # TODO take care of exceptions
        minimum = 1.*u.m
        dXIn = minimum + random.random()*u.m
        dXOut = minimum + random.random()*u.m
        dYIn = minimum + random.random()*u.m
        dYOut = minimum + random.random()*u.m
        gapIn = 20.
        gapOut = 20.
        params += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return params


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), np.array(params))
    parray.Write("params")
    f.Close()
    return geofile


def main():
    pipes = [Pipe(duplex=True) for _ in range(args.njobs)]
    ps = [(w, Process(target=worker, args=[m])) for m, w in pipes]
    for i, p in enumerate(ps):
        p[1].start()
        p[0].send(i + 1)

    for _ in range(2):
        # TODO generate geofilename automatically
        params = geo_guessr()
        geoFile = generate_geo("placeholder_{}.root".format(_), params)
        L, W = get_geo(geoFile)
        for w, _ in ps:
            w.send(geoFile)
        xss = [w.recv() for w, _ in ps]
        xs = [x for xs_ in xss for x in xs_]
        fcn = FCN(W, np.array(xs), L)
        print fcn
    for w, _ in ps:
        w.send(False)


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load("libpythia8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='/eos/ship/data/Mbias/pythia8_Geant4-withCharm_onlyMuons_4magTarget.root'
    )
    parser.add_argument(
        '-n',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    args = parser.parse_args()
    ntotal = 17786274
    dy = 10.
    vessel_design = 5
    shield_design = 8
    mcEngine = 'TGeant4'
    simEngine = 'MuonBack'
    outputDir = '.'
    sameSeed = 1
    theSeed = 1
    main()
