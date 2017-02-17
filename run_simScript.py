#!/usr/bin/env python2
import os
import sys
import getopt
import ROOT as r
import geomGeant4
import shipunit as u
import shipRoot_conf
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
import saveBasicParameters


def main():
    mcEngine = 'TGeant4'
    simEngine = 'MuonBack'
    nEvents = 100
    firstEvent = 0

    inputFile = '/eos/ship/data/Mbias/pythia8_Geant4-withCharm_onlyMuons_4magTarget.root'

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
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'D:FHPu:n:i:f:c:hqv:s:l:A:Y:i:m:co:', [
                'PG', 'Pythia6', 'Pythia8', 'Genie', 'MuDIS', 'Ntuple', 'Nuage',
                'MuonBack', 'FollowMuon', 'Cosmics=', 'nEvents=', 'display',
                'seed=', 'firstEvent=', 'phiRandom', 'mass=', 'couplings=',
                'coupling=', 'epsilon=', 'output=', 'tankDesign=',
                'muShieldDesign=', 'NuRadio', 'RpvSusy', 'SusyBench=', 'sameSeed=',
                'charm='
            ])

    except getopt.GetoptError:
        sys.exit()
    for o, a in opts:
        if o in ('--FollowMuon', ):
            followMuon = True
        if o in ('--phiRandom', ):
            phiRandom = True
        if o in ('-n', '--nEvents'):
            nEvents = int(a)
        if o in ('-i', '--firstEvent'):
            firstEvent = int(a)
        if o in ('-f', ):
            if a.lower() == 'none':
                inputFile = None
            else:
                inputFile = a
        if o in ('-o', '--output'):
            outputDir = a
        if o in ('-Y', ):
            dy = float(a)
        if o in ('--tankDesign', ):
            dv = int(a)
        if o in ('--muShieldDesign', ):
            ds = int(a)

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
    outFile = '%s/ship.%s.root' % (outputDir, tag)

    # rm older files !!!
    for x in os.listdir(outputDir):
        if not x.find(tag) < 0:
            os.system('rm %s/%s' % (outputDir, x))
    # Parameter file name
    parFile = '%s/ship.params.%s.root' % (outputDir, tag)

    timer = r.TStopwatch()
    timer.Start()
    run = r.FairRunSim()
    run.SetName(mcEngine)  # Transport engine
    run.SetOutputFile(outFile)  # Output file
    run.SetUserConfig('g4Config.C')  # user configuration file default g4Config.C
    rtdb = run.GetRuntimeDb()
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
    gMC = r.TVirtualMC.GetMC()
    fStack = gMC.GetStack()
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
    kParameterMerged = r.kTRUE
    parOut = r.FairParRootFileIo(kParameterMerged)
    parOut.open(parFile)
    rtdb.setOutput(parOut)
    rtdb.saveOutput()
    rtdb.printParamContexts()
    getattr(rtdb, 'print')()
    run.CreateGeometryFile('%s/geofile_full.%s.root' % (outputDir, tag))
    saveBasicParameters.execute('%s/geofile_full.%s.root' % (outputDir, tag),
                                ship_geo)
    timer.Stop()
    rtime = timer.RealTime()
    ctime = timer.CpuTime()
    print ' '
    print 'Macro finished succesfully.'

    print 'Output file is ', outFile
    print 'Parameter file is ', parFile
    print 'Real time ', rtime, ' s, CPU time ', ctime, 's'


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    main()
