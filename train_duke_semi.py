import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from os.path import join
import random

from utils import loadPretrain2, loadPretrain
from labelData import LabelDataset
from folderUnlabelData import FolderUnlabelDataset
from trackingLabelData import TrackingLabelDataset
from MobileReg import MobileReg

import sys
sys.path.append('../WorkFlow')
from workflow import WorkFlow

exp_prefix = '1_1_'
Batch = 128
UnlabelBatch = 24 #32
Lr = 0.0005
Trainstep = 50000
Lamb = 0.05
Thresh = 0.005


Snapshot = 5000 # do a snapshot every Snapshot steps
TestIter = 100 # do a testing every TestIter steps
ShowIter = 50 # print to screen

datasetdir = '/datadrive/datasets'
trainfile = 'trainval_duke.txt'
saveModelName = 'facing'

pre_mobile_model = 'pretrained_models/mobilenet_v1_0.50_224.pth'
LoadPreMobile = True
pre_model = ''
LoadPreTrain = False

LogParamList= ['Batch', 'UnlabelBatch', 'Lr', 'Trainstep', 'Lamb', 'Thresh'] # these params will be log into the file

class MyWF(WorkFlow.WorkFlow):
    def __init__(self, workingDir, prefix = "", suffix = ""):
        super(MyWF, self).__init__(workingDir, prefix, suffix)

        # === Custom member variables. ===
        logstr = ''
        for param in LogParamList: # record useful params in logfile 
            logstr += param + ': '+ str(globals()[param]) + ', '
        self.logger.info(logstr) 

        self.countEpoch = 0
        self.unlabelEpoch = 0
        self.countTrain = 0
        self.device = 'cuda'

        # Dataloader for the training and testing
        labeldataset = LabelDataset(balence=True)
        unlabeldataset = FolderUnlabelDataset(batch = UnlabelBatch, data_aug=True, datafile='duke_unlabeldata.pkl')
        testdataset = TrackingLabelDataset(filename='test_duke.txt', data_aug=True)
        self.train_loader = DataLoader(labeldataset, batch_size=Batch, shuffle=True)
        self.train_unlabel_loader = DataLoader(unlabeldataset, batch_size=1, shuffle=True)
        self.test_loader = torch.utils.data.DataLoader(testdataset, batch_size=Batch, shuffle=True)

        self.train_data_iter = iter(self.train_loader)
        self.train_unlabeld_iter = iter(self.train_unlabeld_loader)
        self.test_data_iter = iter(self.test_loader)

        self.model = MobileReg()
        if LoadPreMobile:
            self.model.load_pretrained_pth(pre_mobile_model)
        self.optimizer = optim.Adam(self.model.parameters(), lr=Lr)
        self.criterion = nn.MSELoss()

        self.AV['loss'].avgWidth = 100 # there's a default plotter for 'loss'
        self.add_accumulated_value('label_loss', 100) # second param is the number of average data
        self.add_accumulated_value('unlabel_loss', 100) 
        self.add_accumulated_value('test_loss')
        self.add_accumulated_value('test_label')
        self.add_accumulated_value('test_unlabel')

        self.AVP.append(WorkFlow.VisdomLinePlotter("total_loss", self.AV, ['loss', 'test_loss'], [True, False])) # False: no average line
        self.AVP.append(WorkFlow.VisdomLinePlotter("label_loss", self.AV, ['label_loss', 'test_label'], [True, False]))
        self.AVP.append(WorkFlow.VisdomLinePlotter("unlabel_loss", self.AV, ['unlabel_loss', 'test_unlabel'], [True, False]))

    def initialize(self, device):
        super(MyWF, self).initialize()

        # === Custom code. ===
        self.logger.info("Initialized.")
        self.device = device
        self.model.to(device)

    def unlabel_loss(self, output_unlabel):
        loss_unlabel = torch.Tensor([0]).to(self.device)
        unlabel_batch = output_unlabel.size()[0]
        for ind1 in range(unlabel_batch-5): # try to make every sample contribute
            # randomly pick two other samples
            ind2 = random.randint(ind1+2, unlabel_batch-1) # big distance
            ind3 = random.randint(ind1+1, ind2-1) # small distance

            # target1 = Variable(x_encode[ind2,:].data, requires_grad=False).cuda()
            # target2 = Variable(x_encode[ind3,:].data, requires_grad=False).cuda()
            # diff_big = criterion(x_encode[ind1,:], target1) #(output_unlabel[ind1]-output_unlabel[ind2])*(output_unlabel[ind1]-output_unlabel[ind2])
            diff_big = (output_unlabel[ind1]-output_unlabel[ind2])*(output_unlabel[ind1]-output_unlabel[ind2])
            diff_big = diff_big.sum()/2.0
            # diff_small = criterion(x_encode[ind1,:], target2) #(output_unlabel[ind1]-output_unlabel[ind3])*(output_unlabel[ind1]-output_unlabel[ind3])
            diff_small = (output_unlabel[ind1]-output_unlabel[ind3])*(output_unlabel[ind1]-output_unlabel[ind3])
            diff_small = diff_small.sum()/2.0
            # import ipdb; ipdb.set_trace()
            loss_unlabel = loss_unlabel + (diff_small-Thresh-diff_big).clamp(0)
        return loss_unlabel


    def forward_unlabel(self, sample):

        # unlabeled data
        inputValue = sample.squeeze().to(self.device)
        output = self.model(inputValue)
        loss_unlabel = self.unlabel_loss(output)

        return loss_unlabel


    def forward_label(self, sample):

        # labeled data
        inputValue = sample['img'].to(self.device)
        targetValue = sample['label'].to(self.device)

        # forward + backward + optimize
        output = self.model(inputValue)
        loss_label = self.criterion(output, targetValue)

        return loss_label


    def test_label_unlabel(val_sample, net, criterion):
        inputImgs = val_sample['imgseq'].squeeze().to(self.device)
        labels = val_sample['labelseq'].squeeze().to(self.device)

        output = self.model(inputImgs)
        loss_label = self.criterion(output, labels)
        loss_unlabel = self.unlabel_loss(output)
        loss = loss_label + Lamb * loss_unlabel

        return loss, loss_label, loss_unlabel 


    def train(self):
        super(MyWF, self).train()
        self.countTrain += 1

        # === Custom code for training ===
        self.model.train()

        try:
            sample = self.train_data_iter.next()
        except:
            self.train_data_iter = iter(self.train_loader)
            sample = self.train_data_iter.next()
            self.countEpoch += 1

        try:
            sample_unlabel = self.train_unlabeld_iter.next()
        except:
            self.train_unlabeld_iter = iter(self.train_unlabeld_loader)
            sample_unlabel = self.train_unlabeld_iter.next()
            self.unlabelEpoch += 1

        self.optimizer.zero_grad()
        label_loss = self.forward_label(sample)
        unlabel_loss = self.forward_unlabel(sample_unlabel)
        loss = label_loss + Lamb * unlabel_loss
        loss.backward()
        self.optimizer.step()

        # print and visualization
        self.AV['loss'].push_back(loss.item())
        self.AV['label_loss'].push_back(label_loss.item())
        self.AV['unlabel_loss'].push_back(unlabel_loss.item())

        if self.countTrain % ShowIter == 0:
            losslogstr = self.get_log_str()
            self.logger.info("%s #%d - (%d %d) %s lr: %.6f" % (exp_prefix[:-1], 
                self.countTrain, self.countEpoch, self.unlabelEpoch, losslogstr, Lr))

        if ( self.countTrain % Snapshot == 0 ):
            self.write_accumulated_values()
            self.draw_accumulated_values()
            self.save_model(self.model, saveModelName+'_'+str(self.countTrain))

    def test(self):
        super(MyWF, self).test()

        self.model.eval()

        try:
            sample = self.test_data_iter.next()
        except:
            self.test_data_iter = iter(self.test_loader)
            sample = self.test_data_iter.next()

        loss, loss_label, loss_unlabel = self.test_label_unlabel(sample)

        self.AV['test_loss'].push_back(loss.item())
        self.AV['test_label'].push_back(label_loss.item())
        self.AV['test_unlabel'].push_back(unlabel_loss.item())

    def finalize(self):
        super(MyWF, self).finalize()
        self.print_delimeter('finalize ...')
        self.write_accumulated_values()
        self.draw_accumulated_values()
        self.save_model(self.model, saveModelName+'_'+str(self.countTrain))


    def load_model(self, model, modelname):
        preTrainDict = torch.load(modelname)
        model_dict = model.state_dict()
        preTrainDict = {k:v for k,v in preTrainDict.items() if k in model_dict}
        for item in preTrainDict:
            print('  Load pretrained layer: ',item )
        model_dict.update(preTrainDict)
        model.load_state_dict(model_dict)
        return model    

    def save_model(self, model, modelname):
        modelname = self.prefix + modelname + self.suffix + '.pkl'
        torch.save(model.state_dict(), self.modeldir+'/'+modelname)

if __name__ == "__main__":

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    try:
        # Instantiate an object for MyWF.
        wf = MyWF("./", prefix = exp_prefix)

        # Initialization.
        wf.initialize(device)

        while True:
            

            wf.train()

            if wf.countTrain % TestIter == 0:
                wf.test()

            if (wf.countTrain>=Trainstep):
                break

        wf.finalize()

    except WorkFlow.SigIntException as e:
        wf.finalize()
    except WorkFlow.WFException as e:
        print( e.describe() )


