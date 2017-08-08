import numpy as np


def FCN(W, Sxi2, L):
    print W, L, Sxi2
    W_star = 1915820.
    return (1 + np.exp(10. * (W - W_star) / W_star)) * (1. + Sxi2)
