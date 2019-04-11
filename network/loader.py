import sys
sys.path.insert(0, "..")
import os

from .hdeReg import HDEReg
from .mobileRNN import MobileRNN
from .mobileReg import MobileReg
from .hdeRNN import HDE_RNN

from utils import read_json

class ModelLoader(object):

    def __init__(self):
        self.name = "Model-Loader"

    def load(self, config):
        model = None
        mtrained = config["trained"]

        if mtrained is not None: # load a trained config
            path = os.path.join(mtrained["path"], "train/config.json")
            config = read_json(path)["model"]
        
        mtype = config["type"]
        if mtype == 0:
            model = HDEReg(config)
        elif mtype == 1:
            model = MobileRNN(config)
        elif mtype == 2:
            model = MobileReg(config)
        elif mtype == 3:
            model = HDE_RNN(config)

        if mtrained is not None:
            model.load_pretrained(mtrained)

        return model