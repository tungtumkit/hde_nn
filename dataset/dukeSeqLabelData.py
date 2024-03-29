import os
import numpy as np
import pandas as pd 

from .sequenceData import SequenceLabelDataset


class DukeSeqLabelDataset(SequenceLabelDataset):

    def init_data(self):
        data_file = self.path

        frame_iter = 6
        base_folder = os.path.dirname(data_file)
        data = pd.read_csv(data_file).to_dict(orient="records")

        last_idx = -1
        last_cam = -1
        last_seq = -1
        seq = []  # current image sequence

        for point in data:
            img_name = os.path.basename(point["path"]).strip()
            img_path = os.path.join(base_folder, point["path"])

            angle = point["angle"]
            label = np.array([np.sin(angle), np.cos(angle)], dtype=np.float32)

            cam_num = img_name.split("_")[0]  # camera number
            seq_id = img_name.split(".")[0].split("_")[-1]
            frame_id = int(img_name.split("_")[1][5:]) # frame id
        
            #if not ((seq == []) or ((frame_id == last_idx + frame_iter) and (cam_num == last_cam))): # split here
            if not (seq==[] or (cam_num==last_cam and seq_id==last_seq)):
                self.save_sequence(seq)
                seq = []

            last_idx = frame_id
            last_cam = cam_num
            last_seq = seq_id
            seq.append((img_path, label))

        self.save_sequence(seq)
