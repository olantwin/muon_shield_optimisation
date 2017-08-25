#!/bin/env python2
import os
from time import sleep
import click
from rootpy.io import root_open
import rootpy.ROOT as r


@click.command()
@click.argument('geofile')
def render_geofile(geofile):
    with root_open(geofile, 'read') as f:
        geo = f.FAIRGeom
        muonshield = geo.GetVolume('MuonShieldArea')
        muonshield.Draw('ogl')
        viewer = r.gPad.GetViewer3D()
        viewer.GetFrame().Resize(1200, 800)
        sleep(1)
        filename = os.path.splitext(geofile)[0] + '.png'
        print filename
        viewer.SavePicture(str(filename))
        print 2 * muonshield.GetShape().GetDZ()


if __name__ == '__main__':
    render_geofile()
