
IMAGE = 'olantwin/ship-shield'
IMAGE_TAG =
SLEEP_TIME = 60

JOB_TEMPLATE_IMP_SAMPLING = {
    'input': ['eos:/eos/experiment/ship/skygrid/importance_sampling',
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
        '''python2 /code/weighter.py '''
        '''--params {params} '''
        '''--results /output/result.json '''
        '''--hists /output/hists_{IMAGE_TAG}_'''
        '''{params}_{job_id}_{sampling}_{seed}.root --seed {seed}' '''
        '''--share_muons {share} --tag {tag} --point_id {point_id}''',
    },
    'required_outputs': {
        'output_uri': 'eos:/eos/experiment/ship/skygrid/importance_sampling',
        'file_contents': [{
            'file': 'result.json',
            'to_variable': 'result'
        }]
    }
}
