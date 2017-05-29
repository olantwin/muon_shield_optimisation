from random import uniform
import ROOT as r
from array import array


def get_random_vector():
    vector = [uniform(*bound) for bound in get_bounds()]
    return vector


def generate_geo(geofile, params):
    f = r.TFile.Open(geofile, 'recreate')
    parray = r.TVectorD(len(params), array('d', params))
    parray.Write('params')
    f.Close()
    print 'Geofile constructed at ' + geofile
    return geofile


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
