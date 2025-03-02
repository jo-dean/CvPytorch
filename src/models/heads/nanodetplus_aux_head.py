# !/usr/bin/env python
# -- coding: utf-8 --
# @Time : 2021/12/28 14:29
# @Author : liumin
# @File : nanodetplus_aux_head.py

import torch
import torch.nn as nn

from src.models.modules.convs import ConvModule
from src.models.modules.scales import Scale


class NanoDetPlusAuxHead(nn.Module):
    def __init__(
        self,
        num_classes,
        input_channel,
        feat_channels=256,
        stacked_convs=4,
        strides=[8, 16, 32],
        conv_cfg=None,
        norm_cfg=dict(type="GN", num_groups=32, requires_grad=True),
        activation="LeakyReLU",
        reg_max=16,
        **kwargs
    ):
        super(NanoDetPlusAuxHead, self).__init__()
        self.num_classes = num_classes
        self.in_channels = input_channel
        self.feat_channels = feat_channels
        self.stacked_convs = stacked_convs
        self.strides = strides
        self.reg_max = reg_max

        self.conv_cfg = conv_cfg
        self.norm_cfg = norm_cfg
        self.activation = activation
        self.cls_out_channels = num_classes

        self._init_layers()
        self.init_weights()

    def _init_layers(self):
        self.relu = nn.ReLU(inplace=True)
        self.cls_convs = nn.ModuleList()
        self.reg_convs = nn.ModuleList()
        for i in range(self.stacked_convs):
            chn = self.in_channels if i == 0 else self.feat_channels
            self.cls_convs.append(
                ConvModule(
                    chn,
                    self.feat_channels,
                    3,
                    stride=1,
                    padding=1,
                    conv_cfg=self.conv_cfg,
                    norm_cfg=self.norm_cfg,
                    activation=self.activation,
                )
            )
            self.reg_convs.append(
                ConvModule(
                    chn,
                    self.feat_channels,
                    3,
                    stride=1,
                    padding=1,
                    conv_cfg=self.conv_cfg,
                    norm_cfg=self.norm_cfg,
                    activation=self.activation,
                )
            )
        self.gfl_cls = nn.Conv2d(
            self.feat_channels, self.cls_out_channels, 3, padding=1
        )
        self.gfl_reg = nn.Conv2d(
            self.feat_channels, 4 * (self.reg_max + 1), 3, padding=1
        )
        self.scales = nn.ModuleList([Scale(1.0) for _ in self.strides])

    def init_weights(self):
        for m in self.cls_convs:
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, 0, 0.01)
                if hasattr(m, "bias") and m.bias is not None:
                    nn.init.constant_(m.bias, 0)
        for m in self.reg_convs:
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, 0, 0.01)
                if hasattr(m, "bias") and m.bias is not None:
                    nn.init.constant_(m.bias, 0)
        bias_cls = -4.595
        m = self.gfl_cls
        if isinstance(m, nn.Conv2d):
            nn.init.normal_(m.weight, 0, 0.01)
            if hasattr(m, "bias") and m.bias is not None:
                nn.init.constant_(m.bias, bias_cls)
        m = self.gfl_reg
        if isinstance(m, nn.Conv2d):
            nn.init.normal_(m.weight, 0, 0.01)
            if hasattr(m, "bias") and m.bias is not None:
                nn.init.constant_(m.bias, 0)

    def forward(self, feats):
        outputs = []
        for x, scale in zip(feats, self.scales):
            cls_feat = x
            reg_feat = x
            for cls_conv in self.cls_convs:
                cls_feat = cls_conv(cls_feat)
            for reg_conv in self.reg_convs:
                reg_feat = reg_conv(reg_feat)
            cls_score = self.gfl_cls(cls_feat)
            bbox_pred = scale(self.gfl_reg(reg_feat)).float()
            output = torch.cat([cls_score, bbox_pred], dim=1)
            outputs.append(output.flatten(start_dim=2))
        outputs = torch.cat(outputs, dim=2).permute(0, 2, 1)
        return outputs