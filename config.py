# Configuration file for the optimisation. Only static global variables.
#
# For testing whether the config is sane, please add tests to `test_config.py`

FIXED_PARAMS = [
    70.0, 170.0, 40.0, 40.0, 150.0, 150.0, 2.0,
    2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0
]
FIXED_RANGES = [(0, 2), (8, 20)]
IMAGE = 'olantwin/ship-shield'
IMAGE_TAG = '20170531'  # '20170818' for T4
