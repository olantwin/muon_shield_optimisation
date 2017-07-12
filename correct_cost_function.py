#!/bin/env python2
import json
import os
import argparse
import ROOT as r
from get_geo import magnetMass, magnetLength
from analyse import FCN


def read_simulation_result(filename):
    with open(filename, 'r') as f:
        jobs = json.load(f)
    return sum(
        float([x for x in job['output']
               if x.startswith('variable')][0].split('=')[1]) for job in jobs)


def read_parameters(filename):
    with open(filename, 'r') as f:
        params = json.load(f)
    return params


def main():
    fcns = {}
    for filename in os.listdir(args.geodir):
        fcn_id = filename.split('_')[1].split('.')[0]
        geoFile = filename
        logFile = os.path.join(args.logdir, "{}.json".format(fcn_id))

        # TODO match parameters with those from json as cross-check
        g = r.TFile.Open(geoFile, 'read')
        # params = g.params
        geo = g.FAIRGeom
        muonShield = geo.GetVolume('MuonShieldArea')

        Sxi2 = read_simulation_result(logFile)

        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
        with open(os.path.join(args.geodir, 'geo_{}.lw.csv'.format(fcn_id)),
                  'w') as f:
            f.write('{},{}\n'.format(L, W))

        #   calculate cost function value
        fcn = FCN(W, Sxi2, L)
        fcns[fcn_id] = fcn
        # export list
    with open(args.output, 'w') as f:
        json.dump(fcns, f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g', '--geodir', default='/shield/input_files/fcns/geo/')
    parser.add_argument(
        '-l', '--logdir', default='/shield/input_files/fcns/logs/')
    parser.add_argument(
        '-o', '--output', default='/shield/input_files/fcns/fcns.json')
    args = parser.parse_args()
    main()
