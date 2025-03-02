# !/usr/bin/env python
# -- coding: utf-8 --
# @Time : 2022/8/1 9:11
# @Author : liumin
# @File : lspnet.py

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from itertools import chain

from src.losses.seg_loss import CrossEntropyLoss2d
from src.models.backbones import build_backbone
from src.models.heads import build_head

"""
    Lightweight and Progressively-Scalable Networks for Semantic Segmentation
    https://arxiv.org/pdf/2207.13600.pdf
"""


class LSPNet(nn.Module):
    cfgs = {"s": { 'resolutions': [0.75, 0.25], 'depths': [1, 3, 3, 10, 10], 'channels': [8, 24, 48, 96, 96] },
           "m": { 'resolutions': [1, 0.25],    'depths': [1, 3, 3, 10, 10], 'channels': [8, 24, 48, 96, 96] },
           "l": { 'resolutions': [1, 0.25],    'depths': [1, 3, 3, 10, 10], 'channels': [8, 24, 64, 160, 160] }}
    def __init__(self, dictionary=None, model_cfg=None):
        super().__init__()
        self.dictionary = dictionary
        self.model_cfg = model_cfg
        self.input_size = [1024, 2048]
        self.dummy_input = torch.zeros(1, 3, self.input_size[0], self.input_size[1])

        self.num_classes = len(self.dictionary)
        self.category = [v for d in self.dictionary for v in d.keys()]
        self.weight = [d[v] for d in self.dictionary for v in d.keys() if v in self.category]

        self.cfg = self.cfgs[self.model_cfg.TYPE.split("_")[1]]
        self.setup_extra_params()
        self.backbone = build_backbone(self.model_cfg.BACKBONE)
        self.head = build_head(self.model_cfg.HEAD)

        self.criterion = CrossEntropyLoss2d(weight=torch.from_numpy(np.array(self.weight)).float()).cuda()

    def setup_extra_params(self):
        self.model_cfg.BACKBONE.__setitem__('resolutions', self.cfg['resolutions'])
        self.model_cfg.BACKBONE.__setitem__('depths', self.cfg['depths'])
        self.model_cfg.BACKBONE.__setitem__('channels', self.cfg['channels'])
        self.model_cfg.HEAD.__setitem__('channels', self.cfg['channels'])
        self.model_cfg.HEAD.__setitem__('num_classes', self.num_classes)

    def _init_weight(self, *stages):
        for m in chain(*stages):
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.Linear):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)


    def forward(self, imgs, targets=None, mode='infer', **kwargs):
        b, ch, _, _ = imgs.shape
        x = self.head(self.backbone(imgs))
        outputs = F.interpolate(x, size=imgs.size()[2:], mode='bilinear', align_corners=False)

        if mode == 'infer':

            return torch.argmax(outputs, dim=1)
        else:
            losses = {}
            losses['ce_loss'] = self.criterion(outputs, targets)
            losses['loss'] = losses['ce_loss']

            if mode == 'val':
                return losses, torch.argmax(outputs, dim=1)
            else:
                return losses

