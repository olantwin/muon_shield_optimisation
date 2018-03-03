import numpy as np
import os
import argparse
from utils import *


SLAVE_CMD = '''python2 /code/slave.py ''' \
            '''--params {params} ''' \
            '''-f /home/muons.root ''' \
            '''--results /output/result.json ''' \
            '''--hists /output/hists_{tag}.root --seed {seed} ''' \
            '''--xs_path {xs_path}'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--input',
        default='/input/pythia8_Geant4-withCharm_onlyMuons_4magTarget.root')
    parser.add_argument('--results', default='results.json')
    parser.add_argument('--hists', default='hists.root')
    parser.add_argument('--params', required=True)
    parser.add_argument('--point_id', type=int, required=True)
    parser.add_argument('--tag', default="")
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--share_muons', type=float)

    args = parser.parse_args()
    args.xs_path = get_xs_path(args.tag, args.point_id)

    number_of_muons = count_muons(args.input)
    muon_loss, muon_indeces = load_previous_cumulative_arrays()

    if len(muon_loss) == 0:
        next_indeces = np.arange(number_of_muons)
        np.save("/output/cumloss.npy", np.zeros(number_of_muons))
        np.save("/output/cumindeces.npy", np.ones(number_of_muons) * 1e-5)
    else:
        next_indeces = sample_muons(muon_loss, muon_indeces, share=args.share_muons)

    create_muons_files(args.input, "/home/muons.root", next_indeces)
    np.save(get_indeces_path(args.tag, args.point_id), next_indeces)

    command_line = get_command_line(SLAVE_CMD, args)
    start_slave(command_line)


if __name__ == '__main__':
    main()
