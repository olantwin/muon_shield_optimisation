import numexpr as ne


def FCN(W, Sxi2, L):
    """Calculate penalty function.

    W = weight [kg]
    x = array of positions of muon hits in bending plane [cm]
    L = shield length [cm]

    """
    print W, L, Sxi2
    return float(ne.evaluate('0.01*(W/1000)*(1.+Sxi2/(1.-L/10000.))'))
