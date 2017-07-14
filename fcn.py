
def FCN(W, Sxi2, L):
    print W, L, Sxi2
    return 0.01 * (W / 1000) * (1. + Sxi2) / (1. - L / 10000.)
