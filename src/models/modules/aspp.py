# !/usr/bin/env python
# -- coding: utf-8 --
# @Time : 2020/9/15 14:27
# @Author : liumin
# @File : aspp.py

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class _ASPPModule(nn.Module):
    def __init__(self, inplanes, planes, kernel_size, padding, dilation):
        super(_ASPPModule, self).__init__()
        self.atrous_conv = nn.Conv2d(inplanes, planes, kernel_size=kernel_size,
                                            stride=1, padding=padding, dilation=dilation, bias=False)
        self.bn = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)

        self._init_weight()

    def forward(self, x):
        x = self.atrous_conv(x)
        x = self.bn(x)

        return self.relu(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

class ASPP(nn.Module):
    def __init__(self, inplanes=2048, output_stride=16, drop_rate=0.1):
        super(ASPP, self).__init__()
        mid_channels = 256
        if output_stride == 16:
            dilations = [6, 12, 18]
        elif output_stride == 8:
            dilations = [12, 24, 36]
        else:
            raise NotImplementedError


        self.aspp1 = _ASPPModule(inplanes, mid_channels, 1, padding=0, dilation=dilations[0])
        self.aspp2 = _ASPPModule(inplanes, mid_channels, 3, padding=dilations[0], dilation=dilations[0])
        self.aspp3 = _ASPPModule(inplanes, mid_channels, 3, padding=dilations[1], dilation=dilations[1])
        self.aspp4 = _ASPPModule(inplanes, mid_channels, 3, padding=dilations[2], dilation=dilations[2])

        self.global_avg_pool = nn.Sequential(nn.AdaptiveAvgPool2d((1, 1)),
                                             nn.Conv2d(inplanes, mid_channels, 1, stride=1, bias=False),
                                             nn.BatchNorm2d(mid_channels),
                                             nn.ReLU(inplace=True))
        self.conv_bn_relu = nn.Sequential(nn.Conv2d(mid_channels*5, mid_channels, 1, bias=False) ,
                                          nn.BatchNorm2d(mid_channels),nn.ReLU(inplace=True))
        self.dropout = nn.Dropout(p=drop_rate)
        self._init_weight()

    def forward(self, x):
        x1 = self.aspp1(x)
        x2 = self.aspp2(x)
        x3 = self.aspp3(x)
        x4 = self.aspp4(x)
        x5 = self.global_avg_pool(x)
        x5 = F.interpolate(x5, size=x4.size()[2:], mode='bilinear', align_corners=True)
        x = torch.cat((x1, x2, x3, x4, x5), dim=1)

        x = self.conv_bn_relu(x)
        return self.dropout(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                # n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                # m.weight.data.normal_(0, math.sqrt(2. / n))
                torch.nn.init.kaiming_normal_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.Linear):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
