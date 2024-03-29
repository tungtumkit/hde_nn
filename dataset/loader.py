from .generalData import DataLoader, MixDataset
from .singleLabelData import SingleLabelDataset 
from .sequenceUnlabelData import SequenceUnlabelDataset, ViratUnlabelDataset
from .dukeSeqLabelData import DukeSeqLabelDataset
from .unlabelData import UnlabelDataset

"""
Dataset type
0: single 
1: sequence unlabel
2: duke seq
3: virat seq
"""

#TODO: replace self.mean and self.std
class DatasetLoader(object):

    def __init__(self, mean=[0, 0, 0], std=[1, 1, 1]):
        self.name = "Dataset-Loader"

    def loader(self, dataset, batch_size=1, shuffle=True, num_workers=4):
        # fill up so size of dataset is multiple of batch size
        dataset.round_up(batch_size) 

        return DataLoader(dataset, batch_size, shuffle, num_workers)        

    def try_load(self, name, config):
        if name not in config:
            return None 

        mean = config["mean"]
        std = config["std"]

        s_config = config[name]
        t = s_config["type"]

        dts = None
        if t == 0:
            dts = SingleLabelDataset(s_config, mean, std)
        elif t == 1:
            dts = SequenceUnlabelDataset(s_config, mean, std)
        elif t == 2:
            dts = DukeSeqLabelDataset(s_config, mean, std)
        elif t == 3:
            dts = ViratUnlabelDataset(s_config, mean, std)

        size = s_config["size"]
        if size is not None:
            dts.shuffle()
            dts.resize(size)

        return dts

    def load_dataset(self, config):
        train = self.try_load("train", config)
        unlabel = self.try_load("unlabel", config)
        val = self.try_load("val", config)
        val_unlabel = self.try_load("val_unlabel", config)
        test = self.try_load("test", config)

        if test is not None:
            return test
        elif val_unlabel is not None:
            return (train, unlabel, val, val_unlabel)
        elif unlabel is not None:
            return (train, unlabel, val)
        else:
            return (train, val)