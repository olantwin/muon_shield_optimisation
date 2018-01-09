# Configuration file for the optimisation. Only static global variables.
#
# For testing whether the config is sane, please add tests to `test_config.py`


def StripFreeParams(point):
    fixed_params = []
    for low, high in FIXED_RANGES:
        fixed_params += point[low:high]
    return fixed_params


DEFAULT_POINT = [
    70.0,
    170.0,
    205.,
    205.,
    280.,
    245.,
    305.,
    240.,
    40.0,
    40.0,
    150.0,
    150.0,
    2.0,
    2.0,
    80.0,
    80.0,
    150.0,
    150.0,
    2.0,
    2.0,
    87.,
    65.,
    35.,
    121,
    11.,
    2.,
    65.,
    43.,
    121.,
    207.,
    11.,
    2.,
    6.,
    33.,
    32.,
    13.,
    70.,
    11.,
    5.,
    16.,
    112.,
    5.,
    4.,
    2.,
    15.,
    34.,
    235.,
    32.,
    5.,
    8.,
    31.,
    90.,
    186.,
    310.,
    2.,
    55.,
]
FIXED_RANGES = [(0, 2), (8, 20)]
FIXED_PARAMS = StripFreeParams(DEFAULT_POINT)
IMAGE = 'olantwin/ship-shield'
IMAGE_TAG = '20171222_T1'
COMPATIBLE_TAGS = {
    '20171207_T1': [
        '20171222_T1'
        ],
    '20171222_T1': [
        '20171207_T1',
        ],
    '20180108_T1': [],
}
RESULTS_TEMPLATE = {
    'error': 'Some',
    'weight': None,
    'length': None,
    'muons': None,
    'muons_w': None,
    'args': None,
    'status': None,
}
JOB_TEMPLATE = {
    'input': [],
    'container': {
        'workdir':
        '',
        'name':
        '{}:{}'.format(IMAGE, IMAGE_TAG),
        'volumes': [
            '/home/sashab1/ship-shield:/shield',
            '/home/sashab1/ship/shared:/shared'
        ],
        'cpu_needed':
        1,
        'max_memoryMB':
        1024,
        'min_memoryMB':
        512,
        'run_id':
        'near_run3',
        'cmd':
        '''/bin/bash -l -c 'source /opt/FairShipRun/config.sh; '''
        '''python2 /code/slave.py '''
        '''--params {params} '''
        '''-f /shield/worker_files/sampling_{sampling}/'''
        '''muons_{job_id}_16.root '''
        '''--results /output/result.json '''
        '''--hists /output/hists.root --seed {seed}' ''',
    },
    'required_outputs': {
        'output_uri': 'host:/srv/local/skygrid-local-storage/$JOB_ID',
        'file_contents': [{
            'file': 'result.json',
            'to_variable': 'result'
        }]
    }
}
METADATA_TEMPLATE = {
    'user': {
        'tag': '',
        'sampling': 37,
        'seed': 1,
        'image_tag': IMAGE_TAG,
        'params': []
    },
    'disney': {}
}

RUN = "discrete4"
POINTS_IN_BATCH = 20
RANDOM_STARTS = 100

MIN = [
    70.0, 170.0, 275.0, 300.0, 226.0, 204.0, 235.0, 239.0, 40.0, 40.0,
    150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0, 77.0, 58.0,
    104.0, 60.0, 57.0, 22.0, 33.0, 10.0, 35.0, 99.0, 15.0, 69.0, 60.0,
    27.0, 179.0, 38.0, 30.0, 61.0, 13.0, 14.0, 135.0, 158.0, 57.0, 60.0,
    12.0, 49.0, 22.0, 72.0, 24.0, 16.0, 47.0, 67.0, 68.0, 154.0, 6.0, 53.0
]
