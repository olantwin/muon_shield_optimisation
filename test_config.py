import config
import disney_common


def test_sane_parameters():
    assert len(config.FIXED_PARAMS) == sum(
        [high-low for low, high in config.FIXED_RANGES]
    )


def test_parameter_number():
    space = disney_common.CreateDiscreteSpace()
    params = disney_common.AddFixedParams(space.rvs()[0])
    assert len(params) == 56
