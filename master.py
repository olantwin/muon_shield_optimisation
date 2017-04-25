#!/usr/bin/env python2
import argparse
import numpy as np
from skopt import forest_minimize, dump
import ROOT as r
from sh import docker
from common import FCN
from skysteer import calculate_geofile
from sh import docker

def get_bounds():
    dZgap = 10.
    zGap = 0.5 * dZgap  # halflengh of gap
    dZ3 = (20. + zGap, 300. + zGap)
    dZ4 = (20. + zGap, 300. + zGap)
    dZ5 = (20. + zGap, 300. + zGap)
    dZ6 = (20. + zGap, 300. + zGap)
    dZ7 = (20. + zGap, 300. + zGap)
    dZ8 = (20. + zGap, 300. + zGap)
    bounds = [dZ3, dZ4, dZ5, dZ6, dZ7, dZ8]
    for _ in range(8):
        minimum = 10.
        dXIn = (minimum, 250.)
        dXOut = (minimum, 250.)
        dYIn = (minimum, 250.)
        dYOut = (minimum, 250.)
        gapIn = (2., 498.)
        gapOut = (2., 498.)
        bounds += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return bounds


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), np.array(params))
    parray.Write('params')
    f.Close()
    print 'Geofile constructed at ' + geofile
    return geofile


def compute_FCN(params):
    params = [70., 170.] + params  # Add constant parameters
    geoFile = generate_geo('{}/input_files/geo_{}.root'.format(
        args.workDir, compute_FCN.counter), params)

    docker.run(
        "--rm",
        "-v", "{}:/shield".format(args.workDir),
        "olantwin/ship-shield:20170420",
        '/bin/bash', '-l', '-c', "source /opt/FairShipRun/config.sh; python2 /shield/code/get_geo.py -g /shield/input_files/geo_{}.root".format(compute_FCN.counter)
    )
    chi2s, L, W = calculate_geofile(geoFile)

    print 'Processing results...'
    fcn = FCN(W, chi2s, L)
    assert np.isclose(
        L / 2.,
        sum(params[:8]) + 5), 'Analytical and ROOT lengths are not the same.'
    compute_FCN.counter += 1
    return fcn



compute_FCN.counter = 36

def main():
    bounds = get_bounds()
    start = [
        # Units all in cm
        # Lengths:
        200. + 5.,
        200. + 5.,
        275. + 5.,
        240. + 5.,
        300. + 5.,
        235. + 5.,
        # MagnAbsorb1:
        40.,
        40.,
        150.,
        150.,
        2.,
        2.,
        # MagnAbsorb2:
        80.,
        80.,
        150.,
        150.,
        2.,
        2.,
        # Magn1:
        87.,
        65.,
        35.,
        121,
        11.,
        2.,
        # Magn2:
        65.,
        43.,
        121.,
        207.,
        11.,
        2.,
        # Magn3:
        6.,
        33.,
        32.,
        13.,
        70.,
        11.,
        # Magn4:
        5.,
        16.,
        112.,
        5.,
        4.,
        2.,
        # Magn5:
        15.,
        34.,
        235.,
        32.,
        5.,
        8.,
        # Magn6:
        31.,
        90.,
        186.,
        310.,
        2.,
        55.,
    ]
    if args.only_geo:
        params = [70., 170.] + start  # Add constant parameters
        geoFile = generate_geo('geo_start.root', params)
        print 'geofile written to {}'.format(geoFile)
        return 0
    res = forest_minimize(compute_FCN, bounds, x0=start, n_calls=100)
    print res
    compute_FCN(res.x)
    dump(res, 'minimisation_result')


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/data/Mbias/'
        'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument(
        '--workDir',
        default='root://eoslhcb.cern.ch/'
        '/eos/ship/user/olantwin/skygrid')
    parser.add_argument('-j', '--njobs', type=int, required=True)
    parser.add_argument('--only_geo', action='store_true')
    args = parser.parse_args()
    ntotal = 17786274
    main()
