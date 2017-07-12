#!/bin/env python2
import json
import os
import argparse
import md5
import ROOT as r
from get_geo import magnetMass, magnetLength
from analyse import FCN
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def read_simulation_result(filename):
    with open(filename, 'r') as f:
        jobs = json.load(f)
    try:
        return sum(
            float([x for x in job['output']
                   if x.startswith('variable')][0].split('=')[1]) for job in jobs)
    except IndexError:
        print jobs


def read_parameters(filename):
    with open(filename, 'r') as f:
        params = json.load(f)
    return params


def main():
    fcns = {}
    reconstructed = 0
    unreadable_log = 0
    unreadable_logs = []
    unreadable_geo = 0
    unreadable_params = 0
    for filename in os.listdir(args.geodir):
        if os.path.splitext(filename)[1] != '.root':
            continue
        fcn_id = filename.split('_')[1].split('.')[0]
        geoFile = os.path.join(args.geodir, filename)
        logFile = os.path.join(args.logdir, "{}_jobs.json".format(filename))

        # TODO match parameters with those from json as cross-check
        g = r.TFile.Open(geoFile, 'read')
        try:
            params = [x for x in g.params]
        except (AttributeError, ReferenceError):
            # Old files or invalid geometries
            try:
                params = read_parameters(os.path.join('/shield/input_files/fncs/params/', '{}.json'.format(fcn_id)))
            except IOError:
                params_json = json.dumps(params)
                h = md5.new()
                h.update(params_json)
                fcn_id = h.hexdigest()
                try:
                    params = read_parameters(os.path.join('/shield/input_files/fncs/params/', '{}.json'.format(fcn_id)))
                except IOError:
                    unreadable_params +=1
                    continue
        filename = 'geo_{}.root'.format(fcn_id)
        logFile = os.path.join(args.logdir, "{}_jobs.json".format(filename))
        try:
            Sxi2 = read_simulation_result(logFile)
        except IOError:
            # TODO try other log name
            params_json = json.dumps(params)
            h = md5.new()
            h.update(params_json)
            fcn_id = h.hexdigest()
            filename = 'geo_{}.root'.format(fcn_id)
            logFile = os.path.join(args.logdir, "{}_jobs.json".format(filename))
            try:
                Sxi2 = read_simulation_result(logFile)
            except IOError:
                unreadable_logs.append(logFile)
                unreadable_log += 1
                continue

        if not Sxi2:
            Sxi2 = 0.
        # params_json = json.dumps(params)
        # h = md5.new()
        # h.update(params_json)
        # fcn_id_alt = h.hexdigest()
        # print fcn_id, fcn_id_alt
        try:
            geo = g.FAIRGeom
        except AttributeError:
            # No geometry exists, we need to construct it
            ship_geo = ConfigRegistry.loadpy(
                '$FAIRSHIP/geometry/geometry_config.py',
                Yheight=10,
                tankDesign=5,
                muShieldDesign=8,
                muShieldGeo=geoFile)

            outFile = r.TMemFile('output', 'create')
            run = r.FairRunSim()
            run.SetName('TGeant4')
            run.SetOutputFile(outFile)
            run.SetUserConfig('g4Config.C')
            shipDet_conf.configure(run, ship_geo)
            run.Init()
            geo = r.gGeoManager
        muonShield = geo.GetVolume('MuonShieldArea')

        L = magnetLength(muonShield)
        W = magnetMass(muonShield)
        with open(os.path.join(args.geodir, 'geo_{}.lw.csv'.format(fcn_id)),
                  'w') as f:
            f.write('{},{}\n'.format(L, W))

        #   calculate cost function value
        fcn = FCN(W, Sxi2, L)
        fcns[fcn_id] = (params, fcn)
        reconstructed += 1
        # export list
    with open(args.output, 'w') as f:
        json.dump(fcns, f)

    print 10*"*"
    print "Reconstructed:", reconstructed
    print "Unreadable geometries:", unreadable_geo
    print "Unreadable logs:", unreadable_log
    print "Unreadable parameters:", unreadable_params
    print unreadable_logs
    print "Number of geofiles:", len(os.listdir(args.geodir))


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
