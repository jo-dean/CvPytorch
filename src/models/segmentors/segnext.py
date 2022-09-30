# !/usr/bin/env python
# -- coding: utf-8 --
# @Time : 2022/9/26 14:17
# @Author : liumin
# @File : segnext.py

"""
    SegNeXt: Rethinking Convolutional Attention Design for Semantic Segmentation
    https://arxiv.org/pdf/2209.08575.pdf
"""


import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from src.models.backbones import build_backbone
from src.models.heads import build_head
from src.losses.seg_loss import CrossEntropyLoss2d


class SegNeXt(nn.Module):
    def __init__(self, dictionary=None, model_cfg=None):
        super().__init__()
        self.dictionary = dictionary
        self.model_cfg = model_cfg
        self.input_size = [1024, 2048]
        self.dummy_input = torch.zeros(1, 3, self.input_size[0], self.input_size[1])

        self.num_classes = len(self.dictionary)
        self.category = [v for d in self.dictionary for v in d.keys()]
        self.weight = [d[v] for d in self.dictionary for v in d.keys() if v in self.category]

        self.setup_extra_params()
        self.backbone = build_backbone(self.model_cfg.BACKBONE)
        self.head = build_head(self.model_cfg.HEAD)

        self.criterion = CrossEntropyLoss2d(weight=torch.from_numpy(np.array(self.weight)).float()).cuda()


    def setup_extra_params(self):
        self.model_cfg.HEAD.__setitem__('num_classes', self.num_classes)


    def forward(self, imgs, targets=None, mode='infer', **kwargs):
        batch_size, ch, _, _ = imgs.shape
        feats = self.backbone(imgs)
        feats = self.head(feats)
        outputs = F.interpolate(feats, size=imgs.size()[2:], mode='bilinear', align_corners=False)

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
