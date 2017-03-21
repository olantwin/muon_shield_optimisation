#!/usr/bin/env python2
import argparse
import rootpy.ROOT as r
from root_numpy import root2array, array2root


def main():
    array = root2array(
        args.input, treename='pythia8-Geant4',
        selection='sqrt(pz**2 + py**2 + px**2) >= 100'
    )
    array2root(array, args.output, treename='pythia8-Geant4', mode='recreate')


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='ship.conical.MuonBack-TGeant4.root')
    parser.add_argument('-o', '--output', default='test.root')
    args = parser.parse_args()
    main()
