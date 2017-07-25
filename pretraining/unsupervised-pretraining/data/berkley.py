import os
import pathlib
import numpy as np
from PIL import Image

import torch
import torch.utils.data as data
from torchvision import transforms

def collate_fn(args):
    # assume all data is of same length 
    batch_size = len(args)
    seq_length = len(args[0][0]) # assuming non empty data
    data = []
    for seq in range(seq_length):
        cframes = []
        nframes = []
        segs = []
        valid = []
        for arg in args:
            f, n, s, v = arg
            cframes.append(torch.unsqueeze(f[seq], 0))
            nframes.append(torch.unsqueeze(n[seq], 0))
            segs.append(torch.unsqueeze(s[seq], 0))
            valid.append(v[seq])
        cframes = torch.cat(cframes, 0)
        nframes = torch.cat(nframes, 0)
        segs = torch.cat(segs, 0)
        data.append((cframes, nframes, segs, valid))
    return data

class UnsupervisedVideo(data.Dataset):
    '''
    Load the dataset into sequences of given length
    '''
    def __init__(self, root, seq_length, transform=transforms.ToTensor(), split=None):
        root = pathlib.Path(root)
        frame_path = root / 'UnsupVideo_Frames'
        seg_path = root / 'UnsupVideo_Segments'
        if not (frame_path.exists() and seg_path.exists()):
            print("Dataset Error")
            exit(-1)

        frame_path = list(os.walk(frame_path.as_posix()))
        seg_path = list(os.walk(seg_path.as_posix()))

        vid_index = {}
        for (fbase,_,fnames), (sbase,_,snames) in zip(frame_path, seg_path):
            fnames = sorted(fnames)
            snames = sorted(snames)
            for f, s in zip(fnames, snames):
                video_id = f.split('/')[-1].split('_')[0]
                if video_id not in vid_index:
                    vid_index[video_id] = ([], [])
                vid_index[video_id][0].append(os.path.join(fbase, f))
                vid_index[video_id][1].append(os.path.join(sbase, s))

        videos = sorted(vid_index.keys())
        if not split is None:
            if split > 0:
                start = 0
                end = int(len(videos)*split)
            if split < 0:
                split = 1 + split
                start = int(len(videos)*split)
                end = -1
            videos = videos[start:end]

        data = []
        for vid in videos:
            frames, segs = vid_index[vid]
            if len(frames) < 3: continue # not useful for training
            cframes = frames[:-1]
            nframes = frames[1:]
            segs = segs[1:]
            for i in range(0, len(cframes), seq_length):
                start = i
                end   = i + seq_length
                if end > len(cframes):
                    start = -seq_length
                    end = len(cframes)
                data.append((cframes[start:end], nframes[start:end], segs[start:end]))

        self.data = data
        self.transform = transform
        self.T = seq_length

    def __getitem__(self, index):
        # segs are scaled from 0 to 100 in the dataset
        # PIL rescales 0 - 255 by default, so adjust for that
        cframes, nframes, segs = self.data[index]
        cframes = [Image.open(f) for f in cframes]
        nframes = [Image.open(f) for f in nframes]
        segs   = [Image.open(s) for s in segs]
        valid  = [True for _ in cframes]
        if len(cframes) < self.T:
            cframes += [Image.new(cframes[-1].mode, cframes[-1].size) for _ in range(self.T - len(cframes))]
            nframes += [Image.new(nframes[-1].mode, nframes[-1].size) for _ in range(self.T - len(nframes))]
            segs    += [Image.new(segs[-1].mode, segs[-1].size) for _ in range(self.T - len(segs))]
            valid   += [False for _ in range(self.T - len(valid))]

        cframes = [self.transform(f) for f in cframes]
        nframes = [self.transform(f) for f in nframes]
        segs    = [(self.transform(s)/(100/255)) for s in segs]
        return cframes, nframes, segs, valid

    def __len__(self):
        return len(self.data)
