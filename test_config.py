import config


def test_sane_parameters():
    assert len(config.FIXED_PARAMS) == sum([high-low for low, high in config.FIXED_RANGES])
