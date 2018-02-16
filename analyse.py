#!/usr/bin/env python2
"""Functions to analyse and visualise simulation results."""
import argparse
from array import array
import numpy as np
import ROOT as r
import shipunit as u
import rootUtils as ut
from get_geo import get_geo
from disney_common import FCN

Z_T4 = 3538
Z_T1 = Z_T4 - 940
Z_Sensitive_Plane = Z_T1


def graph_tracks(event):
    """Create graphs of tracks in event by interpolating between vetoPoints."""
    hits = []
    fPos = r.TVector3()
    for n, track in enumerate(event.MCTrack):
        track.GetStartVertex(fPos)
        hitlist = {}
        hitlist[fPos.Z()] = [
            fPos.X(), fPos.Y(), fPos.Px(), fPos.Py(), fPos.Pz()
        ]
        # loop over all sensitive volumes to find hits
        for hit in event.vetoPoint:
            if hit.GetTrackID() == (n - 1):
                lp = hit.LastPoint()
                lm = hit.LastMom()
                assert not (lp.x() == lp.y() and lp.x() == lp.z() and
                            lp.x() == 0)
                # must be old data, don't expect hit at 0,0,0
                # first point:
                # Entry point as p in centre of volume, halfway between
                # entry and exit
                hitlist[2. * hit.GetZ() - lp.z()] = [
                    2. * hit.GetX() - lp.x(), 2. * hit.GetY() - lp.y(), 0.0,
                    0.0, 0.0
                ]
                # last point:
                hitlist[lp.z()] = [lp.x(), lp.y(), lm.Px(), lm.Py(), lm.Pz()]
        if len(hitlist) == 1:
            if track.GetMotherId() < 0:
                continue

        zs = hitlist.keys()
        for z in zs:
            hits.append([hitlist[z][0], hitlist[z][1], z])
    # sort in z
    hits.sort(key=lambda x: x[2])
    xs, ys, zs = zip(*hits)
    return r.TGraph(len(hits), array('f', zs), array('f', xs)), r.TGraph(
        len(hits), array('f', zs), array('f', ys))


def analyse(tree, outputfile):
    """Analyse tree to find hit positions and create histograms.

    Parameters
    ----------
    tree
        Tree or Chain of trees with the usual `cbmsim` format
    outputfile : str
        Filename for the file in which the histograms are saved,
        will be overwritten

    Returns
    -------
    std::vector<double>
        Vector of hit x-positions [cm]

    """
    r.gROOT.SetBatch(True)
    maxpt = 6.5
    maxp = 360.
    f = r.TFile.Open(outputfile, 'recreate')
    f.cd()
    h = {}
    ut.bookHist(h, 'mu_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100,
                -800, 1000)
    ut.bookHist(h, 'anti-mu_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000,
                100, -800, 1000)
    ut.bookHist(h, 'mu_w_pos', '#mu- hits;x[cm];y[cm]', 100, -1000, +1000, 100,
                -800, 1000)
    ut.bookHist(h, 'anti-mu_w_pos', '#mu+ hits;x[cm];y[cm]', 100, -1000, +1000,
                100, -800, 1000)
    ut.bookHist(h, 'mu_p', '#mu+-;p[GeV];', 100, 0, maxp)
    ut.bookHist(h, 'mu_p_original', '#mu+-;p[GeV];', 100, 0, maxp)
    ut.bookHist(h, 'mu_pt_original', '#mu+-;p_t[GeV];', 100, 0, maxpt)
    ut.bookHist(h, 'mu_ppt_original', '#mu+-;p[GeV];p_t[GeV];', 100, 0, maxp,
                100, 0, maxpt)
    ut.bookHist(h, 'smear', '#mu+- initial vertex;x[cm];y[cm]', 100, -10, +10,
                100, -10, 10)
    xs = r.std.vector('double')()
    i, n = 0, tree.GetEntries()
    print '0/{}\r'.format(n),
    mom = r.TVector3()
    for event in tree:
        i += 1
        if i % 1000 == 0:
            print '{}/{}\r'.format(i, n),
        original_muon = event.MCTrack[1]
        h['smear'].Fill(original_muon.GetStartX(), original_muon.GetStartY())
        draw = False
        for hit in event.vetoPoint:
            if hit:
                if not hit.GetEnergyLoss() > 0:
                    xs.push_back(0.)
                    continue
                pid = hit.PdgCode()
                if (
                        hit.GetZ() > (Z_Sensitive_Plane - 1) and
                        hit.GetZ() < (Z_Sensitive_Plane + 1) and
                        abs(pid) == 13
                ):
                    hit.Momentum(mom)
                    P = mom.Mag() / u.GeV
                    y = hit.GetY()
                    x = hit.GetX()
                    if pid == 13:
                        h['mu_pos'].Fill(x, y)
                    else:
                        h['anti-mu_pos'].Fill(x, y)
                    x *= pid / 13.
                    if (
                            P > 1 and
                            abs(y) < 5 * u.m and
                            (x < 2.6 * u.m and x > -3 * u.m)
                    ):
                        w = np.sqrt((560. - (x + 300.)) / 560.)
                        xs.push_back(w)
                        h['mu_p'].Fill(P)
                        original_muon = event.MCTrack[1]
                        h['mu_p_original'].Fill(original_muon.GetP())
                        h['mu_pt_original'].Fill(original_muon.GetPt())
                        h['mu_ppt_original'].Fill(original_muon.GetP(),
                                                  original_muon.GetPt())
                        if pid == 13:
                            h['mu_w_pos'].Fill(x, y, w)
                            draw = 4
                        else:
                            h['anti-mu_w_pos'].Fill(-x, y, w)
                            draw = 6
                    else:
                        xs.push_back(0.)
        if draw:
            graph_x, graph_y = graph_tracks(event)
            graph_x.SetLineColor(draw)
            graph_y.SetLineColor(draw)
            name = 'c{}'.format(i)
            c = r.TCanvas(name, name, 1600, 900)
            multigraph = r.TMultiGraph(
                'tracks_{}'.format(i),
                'Tracks in acceptance and side;z [cm];x/y [cm]')
            graph_x.SetLineStyle(1)
            graph_x.SetMarkerStyle(20)
            graph_x.SetTitle('x-projection')
            graph_x.SetFillStyle(0)
            graph_y.SetTitle('y-projection')
            graph_y.SetLineStyle(2)
            graph_y.SetMarkerStyle(20)
            graph_y.SetFillStyle(0)
            multigraph.Add(graph_x, 'lp')
            multigraph.Add(graph_y, 'lp')
            multigraph.Draw('Alp')
            c.BuildLegend()
            c.Write()
    print 'Loop done'
    for key in h:
        classname = h[key].Class().GetName()
        if 'TH' in classname or 'TP' in classname:
            h[key].Write()
    f.Close()
    return xs


def main():
    """Run standalone analysis and print FCN."""
    f = r.TFile.Open(args.input, 'read')
    tree = f.cbmsim
    xs = analyse(tree, args.output)
    L, W = get_geo(args.geofile)
    fcn = FCN(W, np.array(xs), L)
    print fcn, len(xs)


if __name__ == '__main__':
    r.gErrorIgnoreLevel = r.kWarning
    r.gSystem.Load('libpythia8')
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--input', required=True)
    parser.add_argument('-g', '--geofile', required=True)
    parser.add_argument('-o', '--output', default='test.root')
    args = parser.parse_args()
    main()
