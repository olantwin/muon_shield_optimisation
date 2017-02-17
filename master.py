#!/usr/bin/env python2
import os
import tempfile
import numexpr as ne
from multiprocessing import Pool, cpu_count, current_process, Process, Pipe
import argparse
import numpy as np
import ROOT as r
import shipunit as u
import geomGeant4
import shipRoot_conf
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def generate(pid, inputFile, nEvents):
    mcEngine = 'TGeant4'
    simEngine = 'MuonBack'
    nEvents = 100
    firstEvent = 0

    outputDir = '.'
    sameSeed = 1
    theSeed = 1
    dy = 10.
    dv = 5
    ds = 7

    # provisionally for making studies of various muon background sources
    inactivateMuonProcesses = True
    phiRandom = False  # only relevant for muon background generator
    followMuon = False  # only transport muons for a fast muon only background

    print 'FairShip setup for', simEngine, 'to produce', nEvents, 'events'
    r.gRandom.SetSeed(theSeed)
    shipRoot_conf.configure()
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=dv,
        muShieldDesign=ds)

    # Output file name, add dy to be able to setup geometry with ambiguities.
    tag = simEngine + '-' + mcEngine
    if dv == 5:
        tag = 'conical.' + tag
    elif dy:
        tag = str(dy) + '.' + tag
    if not os.path.exists(outputDir):
        os.makedirs(outputDir)
    outFile = '{}/{}.ship.{}.root'.format(outputDir, pid, tag)

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

    print 'Output file is ', outFile
    return outFile


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


def worker(id_):
    ego = current_process()
    worker_filename = "{}_{}.root".format(id_, args.njobs)
    n = (ntotal / args.njobs)
    firstEvent = n*(id_-1)
    n += (ntotal % args.njobs if id_ == args.njobs else 0)
    print id_, ego.pid, 'Produce', n, 'events starting with event', firstEvent
    n = 100
    if os.path.isfile(worker_filename):
        print worker_filename, "exists."
        pass
    else:
        f = r.TFile.Open("root://eoslhcb.cern.ch/"+args.input)
        tree = f.Get("pythia8-Geant4")
        worker_file = r.TFile.Open(worker_filename,"recreate")
        worker_data = tree.CopyTree("","",n,firstEvent)
        worker_data.Write()
        worker_file.Close()
    outFile = generate(ego.pid, worker_filename, n)
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
    return xs


def get_geo(out):
    dy = 10.
    dv = 5
    ds = 7
    shipRoot_conf.configure()
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=dy,
        tankDesign=dv,
        muShieldDesign=ds)

    with tempfile.NamedTemporaryFile() as t:
        run = r.FairRunSim()
        run.SetName('TGeant4')  # Transport engine
        run.SetOutputFile(t.name)  # Output file
        run.SetUserConfig('g4Config.C')
        modules = shipDet_conf.configure(run, ship_geo)
        run.Init()
        run.Run(0)
        sGeo = r.gGeoManager
        muonShield = sGeo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
    out.send([L, W])


def main():
    out_, in_ = Pipe(duplex=False)
    geo_process = Process(target=get_geo, args=[in_])
    geo_process.start()
    pool = Pool(processes=args.njobs)
    xss = pool.map(worker, range(1, args.njobs + 1))
    xs = [x for xs_ in xss for x in xs_]
    L, W = out_.recv()
    fcn = FCN(W, np.array(xs), L)
    print fcn
    return fcn


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='/eos/ship/data/Mbias/pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '-n',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    args = parser.parse_args()
    ntotal = 17786274
    main()
