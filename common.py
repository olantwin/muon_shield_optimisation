import os
import numexpr as ne
import ROOT as r
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def FCN(W, Sxi2, L):
    """Calculate penalty function.

    W = weight [kg]
    x = array of positions of muon hits in bending plane [cm]
    L = shield length [cm]

    """
    print W, L, Sxi2
    return float(ne.evaluate('0.01*(W/1000)*(1.+Sxi2/(1.-L/10000.))'))


def magnetMass(muonShield):
    """Calculate magnet weight [kg]

    Assumes magnets contained in `MuonShieldArea` TGeoVolumeAssembly and
    contain `Magn` in their name. Calculation is done analytically by
    the TGeoVolume class.

    """
    nodes = muonShield.GetNodes()
    m = 0.
    for node in nodes:
        volume = node.GetVolume()
        if 'Magn' in volume.GetName():
            m += volume.Weight(0.01, 'a')
    return m


def magnetLength(muonShield):
    """Ask TGeoShapeAssembly for magnet length [cm]

    Note: Ignores one of the gaps before or after the magnet

    Also note: TGeoShapeAssembly::GetDZ() returns a half-length

    """
    length = 2 * muonShield.GetShape().GetDZ()
    return length


def load_results(fileName):
    """Loads the polarity corrected x positions [cm] of hits from job

    """
    f = r.TFile.Open(fileName)
    xs = r.std.vector('double')()
    f.GetObject("results", xs)
    f.Close()
    return xs


def get_geo(geoFile):
    ship_geo = ConfigRegistry.loadpy(
        '$FAIRSHIP/geometry/geometry_config.py',
        Yheight=10,
        tankDesign=5,
        muShieldDesign=8,
        muShieldGeo=geoFile)

    print 'Config created with ' + geoFile

    outFile = r.TMemFile('output', 'create')
    run = r.FairRunSim()
    run.SetName('TGeant4')
    run.SetOutputFile(outFile)
    run.SetUserConfig('g4Config.C')
    shipDet_conf.configure(run, ship_geo)
    run.Init()
    run.CreateGeometryFile('./geo/' + os.path.basename(geoFile))
    sGeo = r.gGeoManager
    muonShield = sGeo.GetVolume('MuonShieldArea')
    L = magnetLength(muonShield)
    W = magnetMass(muonShield)
    return L, W
