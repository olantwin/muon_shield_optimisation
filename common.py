"""Functions shared between master, slave and the utility scripts."""
import os
import numexpr as ne
import ROOT as r
from ShipGeoConfig import ConfigRegistry
import shipDet_conf


def FCN(W, x, L):
    """Calculate penalty function.

    Parameters
    ----------
    W : float
        weight [kg]
    x : float
        array of positions of muon hits in bending plane [cm]
    L : float
        shield length [cm]

    Returns
    -------
    float
        Loss function value
    """
    Sxi2 = ne.evaluate('sum(sqrt((560-(x+300.))/560))') if x.size else 0.
    print W, x, L, Sxi2
    return float(ne.evaluate('0.01*(W/1000)*(1.+Sxi2/(1.-L/10000.))'))


def magnetMass(muonShield):
    """Calculate magnet weight analytically [kg].

    Parameters
    ----------
    muonShield : TGeoVolumeAssembly
        Assembly that contains the muon shield magnets. Assumes it is named
        `MuonShieldArea` and that the magnet names contain `Magn`.

    Returns
    -------
    float
        Magnet mass in [kg].

    """
    nodes = muonShield.GetNodes()
    m = 0.
    for node in nodes:
        volume = node.GetVolume()
        if 'Magn' in volume.GetName():
            m += volume.Weight(0.01, 'a')
    return m


def magnetLength(muonShield):
    """Ask TGeoShapeAssembly for magnet length [cm].

    Note: Ignores one of the gaps before or after the magnet

    Also note: TGeoShapeAssembly::GetDZ() returns a half-length

    Parameters
    ----------
    muonShield : TGeoVolumeAssembly
        Assembly that contains the muon shield magnets.

    Returns
    -------
    float
        Magnet length in [cm].

    """
    length = 2 * muonShield.GetShape().GetDZ()
    return length


def load_results(fileName):
    """Load the polarity corrected x positions [cm] of hits from job.

    Parameters
    ----------
    fileName : str
        File in which results were saved. Assumes they were saved with the key
        "results".

    Returns
    -------
    std::vector<double>
        Vector of hit x-positions [cm]
    """
    f = r.TFile.Open(fileName)
    xs = r.std.vector('double')()
    f.GetObject("results", xs)
    f.Close()
    return xs


def get_geo(geoFile):
    """Generate the geometry and check its lenght and weight.

    Note: As FairRunSim is a C++ singleton it misbehaves if run
    more than once in a process.

    Parameters
    ----------
    geoFile : str
        File with the muon shield parameters (not with the geometry config!)

    Returns
    -------
    L : float
        Magnet length in [cm].
    W : float
        Magnet mass in [kg].

    """
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
