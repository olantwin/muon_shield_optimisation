import numpy as np
import os
import ROOT as r
import shlex, subprocess
import argparse

SLAVE_CMD = '''python2 code/slave.py '''
            '''--params {params} '''
            '''-f /shield/worker_files/sampling_is/'''
            '''muons.root '''
            '''--results /output/result.json '''
            '''--hists /output/hists_{tag}.root --seed {seed} '''
            '''--xs_path {xs_path}'''

def loss(x):
    '''
    Calulate the muon loss in the numpy way
    '''
    result = np.zeros(len(x))
    mask = np.logical_and(x >= 0, x <= 260)
    result[mask] = np.sqrt(1 - (x[mask] + 300) / 560)
    return result

def get_xs_path(tag, id):
    return os.path.join("/output", "xs_" + tag + str(id))

def get_indeces_path(tag, id):
    return os.path.join("/output", "index_" + tag + str(id))

def start_slave(command_line):
    '''
    Start the slave.py with Popen and wait to finish.
    '''
    args = shlex.split(command_line)
    proc = subprocess.Popen(args)
    proc.wait()


def load_previous_cumulative_arrays():
    if os.path.exists("/input/cumloss.npy") is True:
        cum_loss = np.load("/input/cumloss.npy")
        cum_indeces = np.load("/input/cumindeces.npy")
        return cum_loss, cum_indeces
    else:
        return np.array([]), np.array([])

def sample_muons(muon_loss, muon_indeces, share=0.05):
    '''
    Function sample the indexes of muons according to weights
    '''
    if share == None:
        share = 0.05

    weights = muon_loss / moun_indeces
    sample_size = int(len(weigths) * share)

    if sample_size == 0:
        raise

    return np.random.choice(len(weights), size=sample_size, p=weigts/np.sum(weights), replace=True)

def create_muons_files(filename_read, filename_write, indexes): # TODO fix that
    '''
    Function takes all the muons, choose subsample according to indeces and saves it to filename_write
    '''
    f = r.TFile.Open(filename_read, 'read')
    intuple = f.Get('pythia8-Geant4')
    out = r.TFile.Open(filename_write, 'recreate')
    outtuple = intuple.CloneTree(0)

    i = 0
    ind_cur = 0
    indexes = np.sort(indexes)

    for muon in intuple:
        while (i == indexes[ind_cur]):
            outtuple.Fill(muon)
            if (ind_cur < len(indexes) - 1 and
                indexes[ind_cur] != indexes[ind_cur + 1]):
                ind_cur += 1
                break
            ind_cur += 1
            if (ind_cur == len(indexes)):
                break
        i += 1

    outtuple.Write()
    f.Close()

def count_muons(filename_read):
    '''
    This function calculates number of muons in the file.
    '''
    f = r.TFile.Open(filename_read, 'read')
    intuple = f.Get('pythia8-Geant4')
    return intuple.GetEntriesFast()

def get_command_line(SLAVE_CMD, args):
    return SLAVE_CMD.format(**vars(args))

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
    args.xs_path = os.path.join("/output", get_xs_path(args.tag, args.point_id))

    number_of_muons = count_muons(args.input)
    muon_loss, muon_indeces = load_previous_cumulative_arrays():

    if len(muon_loss) == 0:
        next_indeces = np.arange(number_of_muons)
        np.save("/output/cumloss.npy", np.zeros(number_of_muons))
        np.save("/output/cumindeces.npy", np.ones(number_of_muons) * 1e-5)
    else:
        next_indeces = sample_muons(muon_loss, muon_indeces, share=args.share_muons)

    create_muons_files(args.input, "/shield/worker_files/sampling_is/muons.root", next_indeces)
    np.save(get_indeces_path(args.tag, args.point_id), next_indeces)

    command_line = get_command_line(SLAVE_CMD, args)
    start_slave(command_line)

if __name__ == '__main__':
    main()
