IMAGE = 'olantwin/ship-shield'
IMAGE_TAG = 20180216.1

JOB_TEMPLATE = {
    'input': ['eos:/eos/experiment/ship/skygrid/importance_sampling/previous_results'],
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
        '''/bin/bash -l -c 'source /opt/FairShipRun/config.sh;'''
        '''python2 /code/weighter/aggregate_results.py '''
        '''--tag {tag}' ''',
    },
    'required_outputs': {
        'output_uri': 'eos:/eos/experiment/ship/skygrid/importance_sampling',
    }
}
