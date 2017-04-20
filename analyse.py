#!/usr/bin/env python2
import argparse
import numpy as np
import ROOT as r
import shipunit as u
import rootUtils as ut
from common import get_geo, FCN


def main():
    h = {}
    ut.bookHist(h, 'mu_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'anti-mu_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'mu_w_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'anti-mu_w_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000, 100, -800, 1000)
    ut.bookHist(h, 'mu_p', '#mu+-;p[GeV];', 100, 0, 350)
    xs = r.std.vector('double')()
    f = r.TFile.Open(args.input, 'read')
    tree = f.cbmsim
    i, n = 0, tree.GetEntries()
    print '0/{}\r'.format(n),
    mom = r.TVector3()
    for event in tree:
        i += 1
        if i % 1000 == 0:
            print '{}/{}\r'.format(i, n),
        for hit in event.vetoPoint:
            if hit:
                if not hit.GetEnergyLoss() > 0:
                    continue
                pid = hit.PdgCode()
                if hit.GetZ() > 2597 and hit.GetZ() < 2599 and abs(pid) == 13:
                    hit.Momentum(mom)
                    P = mom.Mag() / u.GeV
                    y = hit.GetY()
                    x = hit.GetX()
                    if pid == 13:
                        h['mu_pos'].Fill(x, y)
                    else:
                        h['anti-mu_pos'].Fill(x, y)
                    x *= pid / 13.
                    if (P > 1 and abs(y) < 5 * u.m and
                            (x < 2.6 * u.m and x > -3 * u.m)):
                        xs.push_back(x)
                        w = np.sqrt((560.-(x+300.))/560.)
                        h['mu_p'].Fill(P)
                        if pid == 13:
                            h['mu_w_pos'].Fill(x, y, w)
                        else:
                            h['anti-mu_w_pos'].Fill(-x, y, w)
    ut.writeHists(h, args.output)
    L, W = get_geo(args.geofile)
    fcn = FCN(W, np.array(xs), L)
    print fcn, len(xs)


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input', required=True)
    parser.add_argument('-g', '--geofile', required=True)
    parser.add_argument('-o', '--output', default='test.root')
    args = parser.parse_args()
    main()
