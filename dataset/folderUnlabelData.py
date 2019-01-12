# extend with UCF data
import sys
sys.path.insert(0, "..")

import os
import cv2
import pickle
import random

import numpy as np
from os.path import join

from generalData import SingleDataset, SequenceDataset


DataFolder = "/home/mohammad/projects/facing_icra/data"


class FolderUnlabelDataset(SequenceDataset):

    def __init__(self, name, img_dir='', data_file=None,
                 img_size=192, data_aug=False, mean=[0, 0, 0], std=[1, 1, 1],
                 seq_length=24, extend=False, include_all=False):

        if data_file != None:
            # load from saved pickle file, priority

            SingleDataset.__init__(self, name, img_size, data_aug, 0, mean, std)
            self.seq_length = seq_length

            with open(data_file, 'rb') as f:
                data = pickle.load(f)
            self.N = data['N']
            self.episodes = data['episodes']
            self.img_seqs = data['img_seqs']

            print "{} loaded from saved file".format(self)
        else:
            # load from folder
            self.include_all = include_all
            self.extend = extend
            self.img_dir = img_dir
            
            SequenceDataset.__init__(self, name, img_size, data_aug, 0, mean, std, seq_length)

            # Save loaded data for future use
            with open(os.path.join(DataFolder, self.saveName), 'wb') as f:
                pickle.dump({'N': self.N, 'episodes': self.episodes,
                             'img_seqs': self.img_seqs}, f, pickle.HIGHEST_PROTOCOL)

            print "{} loaded new".format(self)

        self.read_debug()

        

    def load_image_sequences(self):
        img_folders = []
        if self.include_all:  # Duke
            img_folders = os.listdir(self.img_dir)
            self.saveName = "duke_unlabeldata.pkl"

        elif self.extend:  # UCF
            img_folders = [str(k) for k in range(101, 1040)]
            self.saveName = "ucf_unlabeldata.pkl"

        # process each folder
        for folder in img_folders:
            folder_path = join(self.img_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            # all images in this folder
            img_list = sorted(os.listdir(folder_path))

            sequence = []
            last_idx = -1

            # process the sequence
            for file_name in img_list:
                if not file_name.endswith(".jpg"):  # only process jpg, why really ? 
                    continue

                file_path = join(folder_path, file_name)

                if self.include_all:  # duke dataset
                    sequence.append(file_path)
                    continue

                # filtering the incontineous data
                file_idx = file_name.split('.')[0].split('_')[-1]
                try:
                    file_idx = int(file_idx)
                except:
                    print 'filename parse error:', file_name, file_idx
                    continue

                if last_idx < 0 or file_idx == last_idx + 1:  # continuous index
                    sequence.append(file_path)
                    last_idx = file_idx
                else:  # indexes not continuous
                    sequence = self.save_sequence(sequence)
                    last_idx = -1

            # try save
            sequence = self.save_sequence(sequence)

    def __getitem__(self, idx):
        flip = self.get_flipping()

        out_seq = []
        for img_path in self.items[idx]:
            img = cv2.imread(img_path)
            out_img = self.augment_image(img, flip)
            out_seq.append(out_img)

        return np.array(out_seq)

if __name__ == '__main__': # test
    from generalData import DataLoader
    from utils import get_path, seq_show

    #unlabelset = FolderUnlabelDataset("duke-unlabel", img_dir=get_path("DukeMCMT/train"),
    #                                  seq_length=24, data_aug=True, include_all=True)

    unlabelset = FolderUnlabelDataset("ucf-unlabel", img_dir=get_path("UCF"),
                                      seq_length=24, data_aug=True, extend=True)
    dataloader = DataLoader(unlabelset)

    for count in range(5):
        sample = dataloader.next_sample()
        seq_show(sample.squeeze().numpy(), scale=0.8)
