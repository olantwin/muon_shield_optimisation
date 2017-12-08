#!/usr/bin/env python2
import os
from time import sleep
import click
import ROOT as r


@click.command()
@click.argument('geofile')
def render_geofile(geofile):
    f = r.TFile.Open(geofile, 'read')
    geo = f.FAIRGeom
    muonshield = geo.GetVolume('MuonShieldArea')
    muonshield.Draw('ogl')
    viewer = r.gPad.GetViewer3D()
    camera = viewer.CurrentCamera()
    viewer.GetFrame().Resize(1200, 800)
    sleep(1)
    filename = os.path.splitext(geofile)[0] + '_zy.png'
    print filename
    viewer.SavePictureWidth(str(filename), 4800)
    camera.RotateRad(-r.TMath.Pi()/2., 0)
    viewer.DoDraw()
    filename = os.path.splitext(geofile)[0] + '_zx.png'
    print filename
    viewer.SavePictureWidth(str(filename), 4800)
    print 2 * muonshield.GetShape().GetDZ()
    f.Close()


if __name__ == '__main__':
    render_geofile()
