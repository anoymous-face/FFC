#!/usr/bin/env python
# encoding: utf-8
'''
@author: wujiyang
@contact: wujiyang@hust.edu.cn
@file: mobilefacenet.py
@time: 2018/12/21 15:45
@desc: mobilefacenet backbone
'''

import torch
from torch import nn
import math
import torch.nn.functional as F
# from ptflops import get_model_complexity_info


MobileFaceNet_BottleNeck_Setting = [
    # t, c , n ,s
    [2, 64, 5, 2],
    [4, 128, 1, 2],
    [2, 128, 6, 1],
    [4, 128, 1, 2],
    [2, 128, 2, 1]
]

class BottleNeck(nn.Module):
    def __init__(self, inp, oup, stride, expansion):
        super(BottleNeck, self).__init__()
        self.connect = stride == 1 and inp == oup

        self.conv = nn.Sequential(
            # 1*1 conv
            nn.Conv2d(inp, inp * expansion, 1, 1, 0, bias=False),
            nn.BatchNorm2d(inp * expansion),
            nn.PReLU(inp * expansion),

            # 3*3 depth wise conv
            nn.Conv2d(inp * expansion, inp * expansion, 3, stride, 1, groups=inp * expansion, bias=False),
            nn.BatchNorm2d(inp * expansion),
            nn.PReLU(inp * expansion),

            # 1*1 conv
            nn.Conv2d(inp * expansion, oup, 1, 1, 0, bias=False),
            nn.BatchNorm2d(oup),
        )

    def forward(self, x):
        if self.connect:
            return x + self.conv(x)
        else:
            return self.conv(x)


class ConvBlock(nn.Module):
    def __init__(self, inp, oup, k, s, p, dw=False, linear=False):
        super(ConvBlock, self).__init__()
        self.linear = linear
        if dw:
            self.conv = nn.Conv2d(inp, oup, k, s, p, groups=inp, bias=False)
        else:
            self.conv = nn.Conv2d(inp, oup, k, s, p, bias=False)

        self.bn = nn.BatchNorm2d(oup)
        if not linear:
            self.prelu = nn.PReLU(oup)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        if self.linear:
            return x
        else:
            return self.prelu(x)


class MobileFaceNet(nn.Module):
    def __init__(self, feat_dim=128, fp16=False, bottleneck_setting=MobileFaceNet_BottleNeck_Setting):
        super(MobileFaceNet, self).__init__()
        self.conv1 = ConvBlock(3, 64, 3, 2, 1)
        self.dw_conv1 = ConvBlock(64, 64, 3, 1, 1, dw=True)

        self.cur_channel = 64
        block = BottleNeck
        self.blocks = self._make_layer(block, bottleneck_setting)

        self.conv2 = ConvBlock(128, 512, 1, 1, 0)
        self.linear7 = ConvBlock(512, 512, 7, 1, 0, dw=True, linear=True)
        self.linear1 = ConvBlock(512, feat_dim, 1, 1, 0, linear=True)
        self.fp16 = fp16

    def _make_layer(self, block, setting):
        layers = []
        for t, c, n, s in setting:
            for i in range(n):
                if i == 0:
                    layers.append(block(self.cur_channel, c, s, t))
                else:
                    layers.append(block(self.cur_channel, c, 1, t))
                self.cur_channel = c

        return nn.Sequential(*layers)

    def forward(self, x):
        if self.fp16:
            with torch.cuda.amp.autocast():    
                x = self.conv1(x)
                x = self.dw_conv1(x)
                x = self.blocks(x)
                x = self.conv2(x)
                x = self.linear7(x)
                x = self.linear1(x)
                x = torch.flatten(x, 1) # x.view(x.size(0), -1)
                return F.normalize(x)
        else:
            x = self.conv1(x)
            x = self.dw_conv1(x)
            x = self.blocks(x)
            x = self.conv2(x)
            x = self.linear7(x)
            x = self.linear1(x)
            x = torch.flatten(x, 1) #x.view(x.size(0), -1)
            return F.normalize(x)


if __name__ == "__main__":
    net = MobileFaceNet()
    # macs, params = get_model_complexity_info(net, (3, 112, 112))
    # print('#params: %s, #flops: %s' % (params, macs))

