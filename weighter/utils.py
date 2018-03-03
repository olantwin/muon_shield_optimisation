import numpy as np
import os
import rootpy.ROOT as r
import shlex
import subprocess
from array import array


def loss(x):
    '''
    Calulate the muon loss in the numpy way
    '''
    result = np.zeros(len(x))
    mask = np.logical_and(x >= 0, x <= 260)
    result[mask] = np.sqrt(1 - (x[mask] + 300) / 560)
    return result


def get_xs_path(tag, id):
    return os.path.join("/output/previous_results", "xs_" + tag + str(id) + '.npy')


def get_indeces_path(tag, id):
    return os.path.join("/output/previous_results", "index_" + tag + str(id) + '.npy')


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
    if share is None:
        share = 0.05

    weights = muon_loss / muon_indeces
    sample_size = int(len(weights) * share)

    if np.sum(weights) == 0:
        return np.random.choice(len(weights), size=sample_size, replace=True)
    if sample_size == 0:
        raise

    return np.random.choice(len(weights), size=sample_size, p=weights/np.sum(weights), replace=True)


def create_muons_files(filename_read, filename_write, indeces):
    '''
    Function takes all the muons, choose subsample according to indeces and saves it to filename_write
    '''
    f = r.TFile.Open(filename_read, 'read')
    intuple = f.Get('pythia8-Geant4')
    out = r.TFile.Open(filename_write, 'recreate')
    outtuple = intuple.CloneTree(0)

    i = 0
    ind_cur = 0

    tmp = np.bincount(indeces)
    indeces = np.unique(np.sort(indeces))
    counted_indeces = tmp[tmp != 0]

    for muon in intuple:
        if (i == indeces[ind_cur]):
            a = array('f', [y for x in muon.values() for y in x])
            for _ in range(counted_indeces[ind_cur]):
                outtuple.Fill(a)
            ind_cur += 1

        if ind_cur == len(indeces):
            break

        i += 1

    outtuple.Write()
    f.Close()
    out.Close()


def count_muons(filename_read):
    '''
    This function calculates number of muons in the file.
    '''
    f = r.TFile.Open(filename_read, 'read')
    intuple = f.Get('pythia8-Geant4')
    return intuple.GetEntriesFast()


def get_command_line(SLAVE_CMD, args):
    return SLAVE_CMD.format(**vars(args))
