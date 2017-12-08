#!/usr/bin/env python2
from array import array
import click
from rootpy.io import root_open
import rootpy.ROOT as r


def reconstruct_vector(geofile):
    vector = [70., 170.]
    with root_open(geofile, 'read') as f:
        geo = f.FAIRGeom
        muonshield = geo.GetVolume('MuonShieldArea')
        magnets = {
            m.GetName(): m
            for m in muonshield.GetNodes()
            if 'Magn' in m.GetName()
        }
        lengths = [
            magnets[
                'Magn{}_MiddleMagL_1'.format(i)
            ].GetVolume().GetShape().GetDz() + 5.
            for i in range(1, 7)
        ]
        vector += lengths
        anti_overlap = 0.1
        for magnetname in [
                'MagnAbsorb{}'.format(i) for i in (1, 2)
        ] + [
            'Magn{}'.format(i) for i in range(1, 7)
        ]:
            magnet = magnets[magnetname + '_MiddleMagL_1']
            vertices = r.TVectorD(
                16,
                magnet.GetVolume().GetShape().GetVertices()
            )
            dXIn = vertices[4]
            dXOut = vertices[12]
            dYIn = vertices[5] + anti_overlap
            dYOut = vertices[13] + anti_overlap
            magnet = magnets[magnetname + '_MagRetL_1']
            vertices = r.TVectorD(
                16,
                magnet.GetVolume().GetShape().GetVertices()
            )
            gapIn = vertices[0] - dXIn
            gapOut = vertices[8] - dXOut
            vector += [dXIn, dXOut, dYIn, dYOut, gapIn, gapOut]
    return vector


@click.command()
@click.argument('geofile')
def extract_vector(geofile):
    vector = reconstruct_vector(geofile)
    params = r.TVectorD(len(vector), array('d', vector))
    with root_open(geofile, 'update'):
        params.Write("params")
    print vector


if __name__ == '__main__':
    extract_vector()
