from numpy import isclose
from common import generate_geo
from get_geo import get_geo
from reconstruct_vector import reconstruct_vector
from rootpy.io import root_open
from disney_common import AddFixedParams, CreateDiscreteSpace


space = CreateDiscreteSpace()


def geo_closure(tmpdir, params):
    # create geometry
    parameter_file = generate_geo(tmpdir.dirname + '/params.root', params)
    try:
        _ = get_geo(parameter_file, tmpdir.dirname, 'geo.root')
    except SystemError:
        pass

    # compare vector stored in geometry with starting vector
    with root_open(tmpdir.dirname + '/geo.root', 'read') as f:
        saved_params = f.Get('params')
    assert len(saved_params) == len(params)
    for a, b in zip(params, saved_params):
        assert isclose(a, b)

    # reconstruct vector from geometry
    reconstructed_params = reconstruct_vector(tmpdir.dirname + '/geo.root')
    # compare with original vector
    assert len(reconstructed_params) == len(params)
    for a, b in zip(params, reconstructed_params):
        assert isclose(a, b)
    # compare with vector saved in geofile
    assert len(reconstructed_params) == len(saved_params)
    for a, b in zip(saved_params, reconstructed_params):
        assert isclose(a, b)


def test_geo_closure(tmpdir):
    # create vector (use hans's config)
    start = [
        # Units all in cm
        # Lengths:
        200. + 5.,
        200. + 5.,
        275. + 5.,
        240. + 5.,
        300. + 5.,
        235. + 5.,
        # Magn1:
        87.,
        65.,
        35.,
        121,
        11.,
        2.,
        # Magn2:
        65.,
        43.,
        121.,
        207.,
        11.,
        2.,
        # Magn3:
        6.,
        33.,
        32.,
        13.,
        70.,
        11.,
        # Magn4:
        5.,
        16.,
        112.,
        5.,
        4.,
        2.,
        # Magn5:
        15.,
        34.,
        235.,
        32.,
        5.,
        8.,
        # Magn6:
        31.,
        90.,
        186.,
        310.,
        2.,
        55.,
    ]
    params = AddFixedParams(start)
    geo_closure(tmpdir, params)


def test_random_geo_closure(tmpdir):
    # create vector (use random config)
    params = AddFixedParams(map(float, space.rvs()[0]))
    geo_closure(tmpdir, params)
