import numpy as np
import random

import sys
sys.path.append('../../')

import tasks.cnn.proc as proc
from tasks.cbt.proc import pad_sequences


class DataSource(object):

    def __init__(self, datadir=proc.DATA_DIR, 
            window_size=5,
            batch_size=128):

        self.datadir = datadir
        self.window_size = window_size
        self.batch_size = batch_size

        # load data
        self.data, self.metadata  = self.fetch()

        # num of examples
        self.n = {}
        self.n['train'] = len(self.data['train'][0])
        self.n['test']  = len(self.data['test'][0])
        self.n['valid']  = len(self.data['valid'][0])

        # current iteration
        self.i = 0


    def batch(self, i, dtype='train'):
        # fetch 'i'th batch
        s, e = self.batch_size * i, (i+1)* self.batch_size
        return [ d[s:e] for d in self.data[dtype] ]


    def next_batch(self, n=1, dtype='train'):
        bi = self.batch(self.i, dtype=dtype)
        if self.i < self.n[dtype]//self.batch_size:
            self.i = self.i + 1
        else:
            self.i = 0
        return bi


    def fetch(self):
        data, metadata = proc.gather(path=self.datadir, 
                window_size=self.window_size)
        # pad sequences
        data = pad_sequences(data, metadata)

        data_all = {}
        for tag in [('train','training'), ('test', 'test'), 
                ('valid', 'validation')]:
            # init list for each tag
            data_all[tag[0]] = []
            for name in ['queries', 'windows', 'answers', 
                    'candidates', 'window_targets']:
                data_all[tag[0]].append(data[tag[1]][name])
        return data_all, metadata


if __name__ == '__main__':
    ds = DataSource(datadir=proc.DATA_DIR, batch_size=3)
    print(':: <test> batch(i)')
    print(ds.batch(6, dtype='train'))
    print(':: <test> next_batch()')
    print(ds.next_batch())
