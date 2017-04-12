import numexpr as ne
import ROOT as r


def FCN(W, x, L):
    """Calculate penalty function.

    W = weight [kg]
    x = array of positions of muon hits in bending plane [cm]
    L = shield length [cm]

    """
    Sxi2 = ne.evaluate('sum(sqrt(560-(x+300.)/560))') if x.size else 0.
    print W, x, L, Sxi2
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
