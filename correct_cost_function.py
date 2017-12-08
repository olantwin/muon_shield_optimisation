#!/usr/bin/env python2
import json
import os
import argparse
from array import array
import ROOT as r
from get_geo import magnetMass, magnetLength
from disney_common import FCN


# TODO use version from reconstruct_vector.py
def extract_vector(geofile):
    vector = reconstruct_vector(geofile)
    params = r.TVectorD(len(vector), array('d', vector))
    f = r.TFile.Open(geofile, 'update')
    f.cd()
    params.Write('params')
    f.Close()
    print vector


# TODO use version from reconstruct_vector.py
def reconstruct_vector(geo):
    vector = [70., 170.]
    muonshield = geo.GetVolume('MuonShieldArea')
    magnets = {
        m.GetName(): m
        for m in muonshield.GetNodes() if 'Magn' in m.GetName()
    }
    lengths = [
        magnets['Magn{}_MiddleMagL_1'.format(i)].GetVolume().GetShape().GetDz()
        + 5. for i in range(1, 7)
    ]
    vector += lengths
    anti_overlap = 0.1
    for magnetname in ['MagnAbsorb{}'.format(i) for i in (1, 2)] + ['Magn{}'.format(i) for i in range(1, 7)]:
        magnet = magnets[magnetname + '_MiddleMagL_1']
        vertices = r.TVectorD(16, magnet.GetVolume().GetShape().GetVertices())
        dXIn = vertices[4]
        dXOut = vertices[12]
        dYIn = vertices[5] + anti_overlap
        dYOut = vertices[13] + anti_overlap
        magnet = magnets[magnetname + '_MagRetL_1']
        vertices = r.TVectorD(16, magnet.GetVolume().GetShape().GetVertices())
        gapIn = vertices[0] - dXIn
        gapOut = vertices[8] - dXOut
        vector += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return vector


def check_simulation_result(filename):
    with open(filename, 'r') as f:
        jobs = json.load(f)
    for job in jobs:
        if not [x for x in job['output'] if x.startswith('variable')]:
            return False
    return True


def read_simulation_result(filename):
    with open(filename, 'r') as f:
        jobs = json.load(f)
    try:
        return sum(
            float([x for x in job['output']
                   if x.startswith('variable')][0].split('=')[1])
            for job in jobs)
    except IndexError:
        print jobs


def read_parameters(filename):
    with open(filename, 'r') as f:
        params = json.load(f)
    return params


def to_geofile(logfile):
    return '_'.join(logfile.split('_')[:-1])


def to_paramfile(logfile):
    return '{}.json'.format(logfile.split('_')[1].split('.')[0])


def main():
    fcns = {}
    reconstructed = 0
    unreadable_log = 0
    unreadable_logs = []
    readable_logs = []
    unreadable_geo = 0
    unreadable_params = 0
    logfiles = [
        logfile for logfile in os.listdir(args.logdir)
        if check_simulation_result(os.path.join(args.logdir, logfile))
    ]
    print len(logfiles)
    geo_matches = {
        logfile: to_geofile(logfile)
        for logfile in logfiles
        if os.path.isfile(os.path.join(args.geodir, to_geofile(logfile)))
    }
    found = set(geo_matches.keys())
    print len(found), len(geo_matches)
    param_matches = {
        logfile: to_paramfile(logfile)
        for logfile in
        [logfile for logfile in logfiles if logfile not in found]
        if os.path.isfile(os.path.join(args.paramdir, to_paramfile(logfile)))
    }
    assert not len(
        param_matches), 'Missing geometries indicate invalid geometry.'

    found |= set(param_matches.keys())
    print len(found), len(param_matches)
    print [
        to_paramfile(logfile) for logfile in logfiles if logfile not in found
    ]

    assert not [logfile for logfile in logfiles
                if logfile not in found], 'Not all logfiles could be matched.'

    matches = [(logfile, geofile, to_paramfile(logfile) if os.path.isfile(
        os.path.join(args.paramdir, to_paramfile(logfile))
        ) else None) for logfile, geofile in geo_matches.iteritems()]
    print len(matches)

    for logfile, geofile, paramfile in matches:
        fcn_id = geofile.split('_')[1].split('.')[0]
        geofile = os.path.join(args.geodir, geofile)
        logfile = os.path.join(args.logdir, logfile)
        paramfile = os.path.join(args.paramdir,
                                 paramfile) if paramfile else None

        g = r.TFile.Open(geofile, 'read')
        geo = g.FAIRGeom
        muonShield = geo.GetVolume('MuonShieldArea')
        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
        try:
            params = [x for x in g.params]
        except (AttributeError, ReferenceError):
            # Old files or invalid geometries
            if paramfile:
                params = read_parameters(paramfile)
            else:
                params = reconstruct_vector(geo)
            pararray = r.TVectorD(len(params), array('d', params))
            f = r.TFile.Open(geofile, 'update')
            f.cd()
            pararray.Write('params')
            f.Close()
        g.Close()

        Sxi2 = read_simulation_result(logfile)
        if not Sxi2:
            Sxi2 = 0.

        with open(
            os.path.join(args.geodir, 'geo_{}.lw.csv'.format(fcn_id)),
            'w'
        ) as f:
            f.write('{},{}\n'.format(L, W))

        fcn = FCN(W, Sxi2, L)
        fcns[fcn_id] = (params, fcn)
        reconstructed += 1
    with open(args.output, 'w') as f:
        json.dump(fcns, f)

    print 10 * '*'
    print 'Reconstructed:', reconstructed
    print 'Unreadable geometries:', unreadable_geo
    print 'Unreadable logs:', unreadable_log
    print 'Unreadable parameters:', unreadable_params
    print unreadable_logs
    print readable_logs


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g', '--geodir', default='/shield/input_files/fcns/geo/')
    parser.add_argument(
        '-l', '--logdir', default='/shield/input_files/fcns/logs/')
    parser.add_argument(
        '-o', '--output', default='/shield/input_files/fcns/fcns.json')
    parser.add_argument(
        '-p', '--paramdir', default='/shield/input_files/fcns/params/')
    args = parser.parse_args()
    main()
