
IMAGE = 'olantwin/ship-shield'
IMAGE_TAG = 20180216.1
SLEEP_TIME = 60
POINTS_IN_BATCH = 1
RUN = 'imp_sampling_test'

JOB_TEMPLATE_IMP_SAMPLING = {
    'input': ['eos:/eos/experiment/ship/skygrid/importance_sampling/cumloss.npy',
              'eos:/eos/experiment/ship/skygrid/importance_sampling/cumindeces.npy',
              'eos:/eos/experiment/ship/data/Mbias/'
              'pythia8_Geant4-withCharm_onlyMuons_4magTarget.root'],

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
        '''mkdir -p /output/previous_results;'''
        '''python2 /code/weighter/weighter.py '''
        '''--params {params} '''
        '''--results /output/result.json '''
        '''--hists /output/hists_{IMAGE_TAG}_'''
        '''{params}_{job_id}_{sampling}_{seed}.root --seed {seed} '''
        '''--share_muons {share} --tag {tag} --point_id {point_id}' ''',
    },
    'required_outputs': {
        'output_uri': 'eos:/eos/experiment/ship/skygrid/importance_sampling',
        'file_contents': [{
            'file': 'result.json',
            'to_variable': 'result'
        }]
    }
}


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

RESULTS_TEMPLATE = {
    'error': 'Some',
    'weight': None,
    'length': None,
    'muons': None,
    'muons_w': None,
    'args': None,
    'status': None,
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
