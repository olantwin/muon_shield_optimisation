#!/bin/env python2
import os
import argparse
import ROOT as r
from ShipGeoConfig import ConfigRegistry
import shipDet_conf
from common import magnetMass, magnetLength


def get_geo(geoFile):
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=10,
        tankDesign=5,
        muShieldDesign=8,
        muShieldGeo=geoFile)

    print 'Config created with ' + geoFile

    outFile = r.TMemFile('output', 'create')
    run = r.FairRunSim()
    run.SetName('TGeant4')
    run.SetOutputFile(outFile)
    run.SetUserConfig('g4Config.C')
    shipDet_conf.configure(run, ship_geo)
    run.Init()
    run.CreateGeometryFile('./geo/' + os.path.basename(geoFile))
    sGeo = r.gGeoManager
    muonShield = sGeo.GetVolume('MuonShieldArea')
    L = magnetLength(muonShield)
    W = magnetMass(muonShield)
    return L, W


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g',
        '--geofile',
        required=True)
    args = parser.parse_args()
    l, w = get_geo(args.geofile)
    with open('lw.csv') as f:
        f.write("{},{}\n".format(l, w))
