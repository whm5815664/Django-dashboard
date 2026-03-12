from skimage import feature
from skimage import transform,data  # 图片大小调整
from skimage.color import rgb2gray  # 转灰度图像

import os                       # for working with files
import numpy as np              # for numerical computationss
import torch                    # Pytorch module 
import torch.nn as nn           # for creating  neural networks
from torch.utils.data import DataLoader # for dataloaders 
from PIL import Image           # for checking images
import torch.nn.functional as F # for functions for calculating loss
import torchvision.transforms as transforms   # for transforming images into tensors 
from torchvision.utils import make_grid       # for data checking
from torchvision.datasets import ImageFolder  # for working with classes and images
import cv2


# base class for the model
class ImageClassificationBase(nn.Module):

    def accuracy(outputs, labels):
        _, preds = torch.max(outputs, dim=1)
        return torch.tensor(torch.sum(preds == labels).item() / len(preds))
    
    def training_step(self, batch):
        images, labels = batch
        out = self(images)                  # Generate predictions
        loss = F.cross_entropy(out, labels) # Calculate loss
        return loss
    
    def validation_step(self, batch):
        images, labels = batch
        out = self(images)                   # Generate prediction
        loss = F.cross_entropy(out, labels)  # Calculate loss 交叉熵
        acc = self.accuracy(out, labels)          # Calculate accuracy
        return {"val_loss": loss.detach(), "val_accuracy": acc}
    
    def validation_epoch_end(self, outputs):
        batch_losses = [x["val_loss"] for x in outputs]
        batch_accuracy = [x["val_accuracy"] for x in outputs]
        epoch_loss = torch.stack(batch_losses).mean()       # Combine loss  
        epoch_accuracy = torch.stack(batch_accuracy).mean()
        return {"val_loss": epoch_loss, "val_accuracy": epoch_accuracy} # Combine accuracies
    
    def epoch_end(self, epoch, result):
        print("Epoch [{}], last_lr: {:.5f}, train_loss: {:.4f}, val_loss: {:.4f}, val_acc: {:.4f}".format(
            epoch, result['lrs'][-1], result['train_loss'], result['val_loss'], result['val_accuracy']))
        

# convolution block with BatchNormalization 卷积
def ConvBlock(in_channels, out_channels, pool=False):
    layers = [nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
             nn.BatchNorm2d(out_channels),
             nn.ReLU(inplace=True)]
    if pool:
        layers.append(nn.MaxPool2d(4))
    return nn.Sequential(*layers)


class BasicConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, **kwargs):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, **kwargs)
        self.bn = nn.BatchNorm2d(out_channels)
        
    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        return F.relu(x)


def Lbp(x):
    b,c,w,h = x.shape
    # batchsize中每张图片取出做LBP手工特征提取，提取后从新装回batchsize中
    temp = []
    for i in x:
        i = i.reshape(c,w,h) # 维度变换
        i = i.detach().cpu().numpy() # tensor转换为cpu版本的numpy
        i = i*255
        
        #得到L维度
        np_img = i.transpose(1, 2, 0)
        img = np_img.astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(img)
        
        lbp = feature.local_binary_pattern(l_channel,1,8,'ror') # lbp特征图
        temp.append(lbp)
        
    lbp_out = torch.tensor(temp).type(torch.float32)/255 # 将lbp特征从numpy转换为tensor，数据为float类型 归一化
    lbp_out = lbp_out.reshape(b, 1, 256, 256)
    
    return lbp_out


# 收缩模块 1 基于senet
class Shrinkage(nn.Module):
    def __init__(self,  channel, gap_size):
        super(Shrinkage, self).__init__()
        
        self.gap = nn.AdaptiveAvgPool2d(gap_size)  # 全局池化可选Maxpool、Avgpool
        
#         self.fc = nn.Sequential(
#             nn.Linear(channel, channel), 
#             nn.BatchNorm1d(channel),
#             nn.ReLU(inplace=True),
#             nn.Linear(channel, channel),
#             nn.Sigmoid(),   # 激活可选ReLU、Tanh、Sigmoid
#         )
        
        # 改进fc conv1x1代替Linner
        self.fc = nn.Sequential(
            nn.Conv2d(channel, channel, 1, 1, 0),
            nn.BatchNorm2d(channel),
            nn.ReLU(inplace=True),
            nn.Conv2d(channel, channel, 1, 1, 0),
            nn.Sigmoid()
        )
        
        

    def forward(self, x):
        b,c,w,h = x.shape

        #GAP
        x_raw = x
        x = torch.abs(x) # 绝对值
        x_abs = x
        x = self.gap(x) # 全局平均池化[b,c,1,1]
        #print('gap',x.shape)

        # 展品成一维向量
#         x = torch.flatten(x, 1)
        average = x   # 获得新特征A（全局平均池化 average(Xij) 去除wh维）
    
        
        # FC层 获取系数a
        x = self.fc(x)   # 获得系数a
        #print('FC',x.shape)
        
        
        x = torch.mul(average, x)   # 获得阈值┏=axA
        x = x.reshape(b,c,1,1)
        
        # 软阈值化
        sub = x_abs - x
        zeros = sub - sub
        n_sub = torch.max(sub, zeros)
        x = torch.mul(torch.sign(x_raw), n_sub)
        return x
    
    

class Shrinkage_SAM(nn.Module):
    def __init__(self, in_channels, kernel_size=7):
        super(Shrinkage_SAM, self).__init__()
        assert kernel_size in (3, 7), 'kernel size must be 3 or 7'  # 卷积核conv layer大小必须为3或7
        padding = 3 if kernel_size == 7 else 1   # 当卷积核大小为7时，输入的每一条边补充3的层数；当卷积核大小为3时，输入的每一条边补充1的层数

        self.conv1 = nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)  # 卷积：输入维度2[MaxPool,AvgPool]，输出维度1
        self.sigmoid = nn.Sigmoid()
        

    def forward(self, x):
        
        x_raw = x
        x = torch.abs(x) # 绝对值
        x_abs = x
        
        avg_out = torch.mean(x, dim=1, keepdim=True)    # 去除c维,获得新特征A（全局平均池化 average(Xc) 去除wh维）
        max_out, _ = torch.max(x, dim=1, keepdim=True)  

        x = torch.cat([avg_out, max_out], dim=1)  
        x = self.conv1(x)  
        x = self.sigmoid(x) # 输入特征层每一个特征点的权值 a
        
        #x = torch.mul(avg_out, x) # 获得阈值┏=axA
        
        # 软阈值化
        sub = x_abs - x
        zeros = sub - sub
        n_sub = torch.max(sub, zeros)
        x = torch.mul(torch.sign(x_raw), n_sub)
        
        return x



# 残差模块 论文残差收缩
class residual_block(nn.Module):
    def __init__(self, in_channels):
        super(residual_block, self).__init__()
        
        hidden_channels = in_channels//2
        
        half_channels = hidden_channels//4
        
        
        self.convDown = nn.Conv2d(in_channels, hidden_channels, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(hidden_channels)
        self.convUp = nn.Conv2d(hidden_channels, in_channels, kernel_size=1, bias=False)
        self.bn2 = nn.BatchNorm2d(in_channels)
        
        
        #branch1: avgpool --> conv1*1(256)
        self.b1_1 = nn.AvgPool2d(kernel_size=3, padding=1, stride=1)
        self.b1_2 = BasicConv2d(hidden_channels, half_channels, kernel_size=1)
        
        #branch2: conv1*1(256)
        self.b2 = BasicConv2d(hidden_channels, half_channels, kernel_size=1)
        
        #branch3: conv1*1(256)->conv3x1(256)
        self.b3_1 = BasicConv2d(hidden_channels, half_channels, kernel_size=1)
        self.b3_2 = BasicConv2d(half_channels, half_channels, kernel_size=(3,1), stride=1, padding=(1,0))
        self.b3_3 = BasicConv2d(half_channels, half_channels, kernel_size=(1,3), stride=1, padding=(0,1))
        
        #branch4: conv1*1(256)->conv3x1(256)->conv3x1(256)
        self.b4_1 = BasicConv2d(hidden_channels, half_channels, kernel_size=1)
        self.b4_2 = BasicConv2d(half_channels, half_channels, kernel_size=(3,1), stride=1, padding=(1,0))
        self.b4_3 = BasicConv2d(half_channels, half_channels, kernel_size=(1,3), stride=1, padding=(0,1))
        self.b4_4 = BasicConv2d(half_channels, half_channels, kernel_size=(3,1), stride=1, padding=(1,0))
        self.b4_5 = BasicConv2d(half_channels, half_channels, kernel_size=(1,3), stride=1, padding=(0,1))
         
        # 残差收缩
        self.Shrinkage = Shrinkage(in_channels, gap_size=(1, 1))
        
        # 卷积
        self.conv3 = BasicConv2d(in_channels, in_channels*2, kernel_size=3, stride=1, padding=1)
    
             
        
        
    def forward(self, xb): # xb is the loaded batch
       
        # shortcut
        identify = xb
        
        
        # bottleneck
        down = self.bn1(self.convDown(xb))
        
        
        y1 = self.b1_2(self.b1_1(down))
        #print(y1.shape)
        y2 = self.b2(down)
        #print(y2.shape)
        y3 = self.b3_3(self.b3_2(self.b3_1(down)))
        #print(y3.shape)
        y4 = self.b4_5(self.b4_4(self.b4_3(self.b4_2(self.b4_1(down)))))
        #print(y4.shape)
                                   
        outputsA = [y1, y2, y3, y4]
        cat = torch.cat(outputsA, 1)
        #print(out.shape)
        
        
        # bottleneck
        up = self.bn2(self.convUp(cat))
        
        out = self.Shrinkage(up)
        
        out = out + identify
        out = self.conv3(out)
        
        return out


# resnet architecture 
class TCMRSN(ImageClassificationBase):
    def __init__(self, in_channels, num_diseases):
        super().__init__()
        
        
        
        # stem 输出维度[128,64,64]
        #----------------------------------------------------
        # 通道数比例 4:6（卷积1：26\38  卷积2:52\76）
        # 通道数比例 4:6（卷积1：12\20  卷积2:25\39）
        # RGB通道
        self.convRGB = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=26, kernel_size=7, stride=2, padding=3, bias=False),     # H/2,W/2。
            nn.BatchNorm2d(26),
            nn.ReLU(inplace=True),
            #nn.MaxPool2d(kernel_size=3, stride=2, padding=1)     # H/2,W/2。C不变
        )
        
        # LBP通道
        self.Shrinkage_SAM = Shrinkage_SAM(3)   # 输出(1,256,256)  
        self.convLBP = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=38, kernel_size=7, stride=2, padding=3, bias=False),     # H/2,W/2。
            nn.BatchNorm2d(38),
            nn.ReLU(inplace=True),
            #nn.MaxPool2d(kernel_size=3, stride=2, padding=1)     # H/2,W/2。C不变
        )
        
        # concat合并 输出(64,256,256)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.maxpool2 = nn.MaxPool2d(4)
        
        self.residual = residual_block(64)
           
        self.residual2 = residual_block(128) 
        
        
         
        self.classifier = nn.Sequential(nn.AvgPool2d(4),
                                       nn.Flatten(),
                                       nn.Linear(256, num_diseases))
        
        
    def forward(self, xb): # xb is the loaded batch
        
        #print('import',xb.shape)
        
        # stem
        #---------------------
        # RGB输入
        rgb = self.convRGB(xb)
        #print('rgb',rgb.shape)
        
        # LBP输入
        sam = self.Shrinkage_SAM(xb) # (1,256,256)
        #print(sam.shape)
        lbp_out = Lbp(sam)  # (1,256,256)
        #print('lbp',lbp_out.shape) 
        # 通过卷积处理
        lbp_out = self.convLBP(lbp_out) 
        
        # 特征拼接
        out = torch.cat([rgb, lbp_out], dim=1)
        #print('concat',out.shape)
        out = self.maxpool(out)
        #print('maxpool',out.shape)
        
        out = self.residual(out)
        out = self.maxpool2(out)
        #print('conv1',out.shape)
        
        out = self.residual2(out)
        out = self.maxpool2(out)
        #print('conv2',out.shape)
        
       
        #print(out.shape)
        
        
        out = self.classifier(out)
        return out   


# 加载模型，读取一个图像进行情绪识别
def disease_recognize(image_path):
    
    lables = [
    # 苹果
    '苹果黑星病', '苹果黑腐病', '苹果雪松锈病', '苹果健康',
    # 背景
    '无叶片背景',
    # 蓝莓
    '蓝莓健康',
    # 樱桃
    '樱桃健康', '樱桃白粉病',
    # 玉米
    '玉米灰斑病', '玉米普通锈病', '玉米健康', '玉米北方叶枯病',
    # 葡萄
    '葡萄黑腐病', '葡萄黑麻疹病', '葡萄健康', '葡萄叶枯病',
    # 柑橘
    '柑橘黄龙病',
    # 桃
    '桃细菌性斑病', '桃健康',
    # 甜椒
    '甜椒细菌性斑病', '甜椒健康',
    # 马铃薯
    '马铃薯早疫病', '马铃薯健康', '马铃薯晚疫病',
    # 树莓
    '树莓健康',
    # 大豆
    '大豆健康',
    # 西葫芦
    '西葫芦白粉病',
    # 草莓
    '草莓健康', '草莓叶焦病',
    # 番茄
    '番茄细菌性斑病', '番茄早疫病', '番茄健康', '番茄晚疫病', 
    '番茄叶霉病', '番茄叶斑病', '番茄二斑叶螨', 
    '番茄靶斑病', '番茄花叶病毒病', '番茄黄化曲叶病毒病'
]
    
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    
    model_path = os.path.join(base_dir, 'TC-MRSN.pth')
    
    try:
        # 创建新的模型实例
        model = TCMRSN(3, 39).to('cpu')
        
        # 尝试加载模型权重
        checkpoint = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)
        
        # 加载权重到模型实例
        if hasattr(checkpoint, 'state_dict'):
            model.load_state_dict(checkpoint.state_dict())
        elif isinstance(checkpoint, dict):
            model.load_state_dict(checkpoint)
        else:
            model.load_state_dict(checkpoint)
            
        model.eval()  # 设置为评估模式

    except Exception as e:
        print(f"模型加载失败: {e}")
    
    # 通过PIL读取图片
    image = Image.open(image_path)
    # 转换成tensor并进行归一化处理
    trans = transforms.Compose([
        transforms.Resize(256),     # 缩放图片，保持长宽比不变，最短边为256像素
        transforms.CenterCrop(256),  # 从图片中间裁剪出256*256的图片
        transforms.ToTensor(),  
    ])
    image = trans(image)
    # 将图像转换为4维tensor
    image = image.unsqueeze(0)
    # 输入模型进行识别
    output = model(image)
    # 获取最大概率的标签
    _, predicted = torch.max(output.data, 1)
    # 获取标签
    label = lables[predicted.item()]
    print("label:", label)
    return label
