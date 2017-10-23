from disney_common import StripFixedParams, AddFixedParams
from config import FIXED_PARAMS


def _StripFixedParams(point):
    return point[2:8] + point[20:]


def _AddFixedParams(point):
    return FIXED_PARAMS[:2] + point[:6] + FIXED_PARAMS[2:] + point[6:]


test_stripped_point = [
    # Units all in cm Lengths:
    200. + 5., 200. + 5., 275. + 5., 240. + 5., 300. + 5., 235. + 5.,
    # Magn1:
    87., 65., 35., 121, 11., 2.,
    # Magn2:
    65., 43., 121., 207., 11., 2.,
    # Magn3:
    6., 33., 32., 13., 70., 11.,
    # Magn4:
    5., 16., 112., 5., 4., 2.,
    # Magn5:
    15., 34., 235., 32., 5., 8.,
    # Magn6:
    31., 90., 186., 310., 2., 55., ]

test_point = AddFixedParams(test_stripped_point)


def test_parameter_adding():
    assert _AddFixedParams(test_stripped_point) == AddFixedParams(test_stripped_point)


def test_parameter_stripping():
    assert _StripFixedParams(test_point) == StripFixedParams(test_point)


def test_parameter_closure():
    assert _AddFixedParams(test_stripped_point) == test_point
