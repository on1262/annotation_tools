# 基于腹腔镜采集数据的神经标注程序

## 软件部署

首先需要安装Aanaconda3和Python环境：
1. 选择合适的操作系统，下载Anaconda3: https://www.anaconda.com/download#downloads 国内镜像站为 https://mirrors.tuna.tsinghua.edu.cn/anaconda/archive/
2. 安装Anaconda3，安装过程中注意勾选“Add Anaconda to my PATH environment variable”选项
3. (视频标注)安装VLC Media Player的对应操作系统版本: https://www.videolan.org/vlc/

之后需要安装依赖包：
1. 打开Anaconda Prompt，创建虚拟环境：`conda create -n anno python=3.11`
2. 激活虚拟环境：`conda activate anno`
3. 安装依赖包：`pip install opencv-python pyyaml -i https://pypi.tuna.tsinghua.edu.cn/simple`
4. (视频标注)安装附加的依赖包: `pip install wxpython python-vlc -i https://pypi.tuna.tsinghua.edu.cn/simple`

最后配置程序运行环境：
1. 在本文件所在目录下创建`images`文件夹，将待标注图片放入该文件夹
2. 在本文件所在目录下创建`saved_imgs`文件夹，用于保存标注结果
3. 在Annaconda Navigator下打开`anno`虚拟环境，点击`Open Terminal`，进入虚拟环境的命令行
4. 打开命令行，切换到程序所在目录: `cd /path/to/this/dir`
5. 如果想进入图像标注，运行：`python main.py --type image > log.txt`
6. 如果想进入视频标注，运行：`python main.py --type video > log.txt`


一些需要注意的事项：
1. 如果按键失灵，检查是否切换到英文输入法。另外该程序对触控板支持不好，建议使用鼠标
2. 不要多开程序，不要调整边框的大小，可能会出现bug
3. 关闭程序后未保存的标注将会丢失，每张图片在按S键后立刻会被保存。
4. 如果出现意外情况退出，可以查看log.txt文件，里面会记录保存图片名以及标注进度
5. 建议在`images`中存放一次能标注完的量，每批标注完成后将`saved_imgs`中的图片移动到其他文件夹，以免下次标注时重复标注
6. 一些标注习惯的配置文件可以在`config.yaml`中修改，例如滚轮反转、缩放速度、观察者模式的透明度等

## 程序使用

本程序支持两种标注方式：图像标注和视频标注。

**图像标注软件的使用说明**

标注方式为按住鼠标左键画出标注框内的神经区域，大致覆盖神经的范围即可。

为了提高效率，本软件使用快捷键操作：
- `鼠标滚轮`：向前或向后滚动，放大或缩小图片
- `鼠标左键`：按住并拖动鼠标，画出标注框内的神经区域
- `鼠标右键`：按住并拖动鼠标，移动图片
- `Q和E键`：将画笔放大2倍/缩小一半
- `A和D键`：浏览上一个/下一个图片，标注过的内容会被临时保存，但是在按S键后才会保存到文件中。注意：如果不保存到文件中，关闭程序后标注就会丢失。
- `-和=键`：向前或向后跳10张图片
- `S键`：将当前图片和标注保存在saved_imgs下，并自动跳转到下一张图片。如果当前图片已经保存且没有被更改过，则在标题处会显示saved字样
- `R键`：清除当前图片的标注，重新加载原始图片。R键不会覆盖已保存的图片。
- `W键`：进入观察者模式，标题会同步显示watch mode字样，画笔变成白色圆点。在观察者模式下，saved_imgs中的标注信息会以半透明遮罩的形式覆盖在原图上，便于核对标注区域是否正确。一旦进入画图就会退出该模式，返回正常作图的模式中。如果此前没有保存图片到saved_imgs中，则无法启动观察者模式。在观察者模式下，进行A/D键切换时，如果待切换图片存在标注，则维持该模式不变- 其余按键例如R/S/Q/E键等也可以正常工作。
- `Esc键`：退出程序

**视频标注软件的使用说明**

在使用视频标注软件前，需要把视频文件转换成`.mp4`格式（可以用格式工厂），确认转换前后分辨率没有损失，之后按照以下文件层级结构放置视频文件：

```
# .py文件为脚本文件，不要修改
main.py
configs.py
image_annotation.py
video_annotation.py

# .yml文件是用户配置文件，可以修改
configs.yaml

# .sh和.bat文件是启动脚本，可以直接运行
run_image.bat # 启动图像标注软件
run_video.bat # 启动视频标注软件

video_input # 输入的mp4视频放入此处
├── video1.mp4
├── video2.mp4
├── ...
└── videoN.mp4

video_annotation # 存放每一个标记帧的时刻、注释、类型等信息，相当于工程文件
├── video1.pkl
├── video2.pkl
├── ...
└── videoN.pkl

video_output # 输出数据存放在此处
├── video1
│   ├── images # 存放截取的视频帧
│   │   ├── 0001.jpg
│   │   ├── 0002.jpg
│   │   ├── ...
│   │   └── 00NN.jpg
│   └── saved_imgs # 存放标注像素（不包括注释和类型）
│       ├── 0001.jpg
│       ├── 0002.jpg
│       ├── ...
│       └── 00NN.jpg
├── video2
├── ...
└── videoN
```




## 标注事项

为了在保持效率的基础上尽可能增加标注准确度，单人标注或多人协同标注时需要遵守一些约定：
1. 标注区域应当完全覆盖神经区域，并且尽量与神经的边界保持均匀、恒定的距离，不要出现过于显著的人工痕迹。
2. 在多个重叠的框中标注时，保持标注的连续性不受框本身的干扰。
3. 被器械遮挡时，不标出被遮挡的部分，只标出可见的神经区域。但是深埋的神经如果隐约可见，也要标出。

