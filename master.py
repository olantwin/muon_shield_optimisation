#!/usr/bin/env python2
import numexpr as ne
from multiprocessing import Pool, cpu_count, current_process
import argparse
import numpy as np
import rootpy.ROOT as r
from rootpy.io import root_open


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
    n = (ntotal / args.njobs) + \
        (ntotal % args.njobs if id_ == args.njobs else 0)
    print id_, ego.pid, n


def main():
    with root_open(args.geofile, 'read') as fgeo:
        sGeo = fgeo.FAIRGeom
        muonShield = sGeo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
    pool = Pool(processes=args.njobs)
    pool.map(worker, range(1, args.njobs + 1))
    xs = []  # Retrieve from slaves
    fcn = FCN(W, np.array(xs), L)
    print fcn
    return fcn


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g',
        '--geofile',
        default='geofile_full.conical.MuonBack-TGeant4.root')
    parser.add_argument(
        '-n',
        '--njobs',
        type=int,
        default=min(8, cpu_count()), )
    args = parser.parse_args()
    ntotal = 17786274
    main()
