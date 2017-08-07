import numpy as np


def FCN(W, Sxi2, L):
    print W, L, Sxi2
    return np.exp(W / 1000) * (1. + Sxi2) / (1. - L / 10000.)
