#!/usr/bin/env python2
import numexpr as ne
import argparse
import numpy as np
import rootpy.ROOT as r
from rootpy.io import root_open
from rootpy.io.pickler import Unpickler
from rootpy.vector import Vector3
import shipunit as u


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
    -> 10 cm shorter than result of magnetLength2

    Also note: TGeoShapeAssembly::GetDZ() returns a half-length

    """
    length = 2 * muonShield.GetShape().GetDZ()
    return length


def magnetLength2(fgeo):
    """Read magnet length [cm] from ShipGeo."""
    ShipGeo = Unpickler(fgeo).load('ShipGeo')
    length = ShipGeo.muShield.length - ShipGeo.muShield.LE
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


def main():
    with root_open(args.geofile, 'read') as fgeo:
        sGeo = fgeo.FAIRGeom
        muonShield = sGeo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
    ch = r.TChain('cbmsim')
    for input_file in args.input:
        ch.Add(input_file)
    # TODO same for all slaves; calculate in steering process? Only retrieve
    # hits from slave?
    xs = []
    mom = Vector3()
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
    print 'Event loop done'
    fcn = FCN(W, np.array(xs), L)
    print fcn
    return fcn


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        nargs='*',
        default=['ship.conical.MuonBack-TGeant4.root'])
    parser.add_argument(
        '-g',
        '--geofile',
        default='geofile_full.conical.MuonBack-TGeant4.root')
    args = parser.parse_args()
    main()
