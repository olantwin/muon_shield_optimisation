#!/usr/bin/env python2
import os
import argparse
from array import array
import ROOT as r
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
        if 'Mag' in volume.GetName():
            m += volume.Weight(0.01, 'a')
    return m


def magnetLength(muonShield):
    """Ask TGeoShapeAssembly for magnet length [cm]

    Note: Ignores one of the gaps before or after the magnet

    Also note: TGeoShapeAssembly::GetDZ() returns a half-length

    """
    length = 2 * muonShield.GetShape().GetDZ()
    return length


def get_geo(geoFile, workDir='/shield/geofiles', outfile=None):
    if workDir[-1] != '/':
        workDir = workDir + '/'
    if not outfile:
        outfile = workDir + os.path.basename(geoFile)
    else:
        outfile = workDir + outfile
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
    run.CreateGeometryFile(outfile)
    sGeo = r.gGeoManager
    muonShield = sGeo.GetVolume('MuonShieldArea')
    L = magnetLength(muonShield)
    W = magnetMass(muonShield)
    g = r.TFile.Open(geoFile, 'read')
    params = g.Get("params")
    f = r.TFile.Open(outfile, 'update')
    f.cd()
    length = r.TVectorD(1, array('d', [L]))
    length.Write('length')
    weight = r.TVectorD(1, array('d', [W]))
    weight.Write('weight')
    params.Write("params")
    return L, W


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g',
        '--geofile',
        required=True)
    parser.add_argument(
        '-o',
        '--output',
        required=True)
    args = parser.parse_args()
    l, w = get_geo(args.geofile)
    with open(args.output, 'w') as f:
        f.write("{},{}\n".format(l, w))
