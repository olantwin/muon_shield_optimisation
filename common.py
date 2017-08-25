from random import uniform
from array import array
import json
import md5
import logging
import ROOT as r


def get_random_vector():
    vector = [uniform(*bound) for bound in get_bounds()]
    return vector


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), array('d', params))
    parray.Write('params')
    f.Close()
    logging.info('Geofile constructed at ' + geofile)
    return geofile


def get_bounds():
    dZgap = 10.
    zGap = 0.5 * dZgap  # halflengh of gap
    minimum = 10.
    dXIn = (minimum, 250.)
    dXOut = (minimum, 250.)
    dYIn = (minimum, 250.)
    dYOut = (minimum, 250.)
    gapIn = (2., 100.)
    gapOut = (2., 100.)
    bounds = 6 * [(20. + zGap, 300. + zGap)
                  ] + 8 * [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return bounds


def in_bounds(vector):
    for element, bound in zip(vector, get_bounds()):
        assert bound[0] <= element <= bound[
            1], '{} is not in bounds [{},{}]'.format(element, *bound)


def create_id(params):
    params_json = json.dumps(params)
    h = md5.new()
    h.update(params_json)
    return h.hexdigest()
