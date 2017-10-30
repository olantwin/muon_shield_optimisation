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
RESULTS_TEMPLATE = {
    'error': None,
    'weight': None,
    'length': None,
    'muons': None,
    'muons_w': None,
}
JOB_TEMPLATE = {
    "descriptor": {
        "input": [],

        "container": {
            "workdir": "",
            "name": "{}:{}".format(IMAGE, IMAGE_TAG),
            "volumes": [
                "/home/sashab1/ship-shield:/shield",
                "/path/to/shared:/shared"  # TODO add shared folder path
            ],
            "cpu_needed": 1,
            "max_memoryMB": 1024,
            "min_memoryMB": 512,
            "run_id": "near_run3",
            "cmd": '''/bin/bash -l -c 'source /opt/FairShipRun/config.sh; '''
                   '''python2 /code/slave.py '''
                   '''--params {params} '''
                   '''-f /shield/worker_files/sampling_{sampling}/'''
                   '''muons_{job_id}_16.root '''
                   '''--results /output/result.json '''
                   '''--hists /output/hists.root --seed {seed}''',
        },

        "required_outputs": {
            "output_uri": "host:/srv/local/skygrid-local-storage/$JOB_ID",
            "file_contents": [
                {"file": "result.json", "to_variable": "result"}
            ]
        }
    }
}
