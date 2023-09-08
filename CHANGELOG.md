# CHANGELOG

## TODO List

- TODO: 进入图像标注时，如果有保存的标注，自动切换watch mode(Done)
- 图像标注时切换前后帧自动保存，除非没有标注(Done)

## BUGS



## Fixed

- Selector在有效帧能够停留
- 转到给定帧时会自动更新comment, 并且指针指向最后
- 同时存在两个标亮框
- 按ESC关闭ImageAnnotator时未响应(fixed)
- 保存标注csv时，不存在的key会报错(fixed)
- 鼠标在两个连续的有效帧之间进度条不会跳动(fixed)
- (潜在，尚未稳定产生)center idx和idx不同步跳变，导致帧位置跳变
- vlc硬件加速出错(fixed, 需要更新ffmpeg: conda install -c conda-forge ffmpeg)
- windows下不能对标注帧添加注释, 切换帧注释不能随之切换(fixed)
- windows下手动关闭ImageAnnotator时按钮状态出错(fixed)
- 空格键只实现了暂停没有继续功能(fixed)
- 退出时提示保存, 如果取消则直接关闭(fixed)
- 保存标注时没有检测是否为空白标注(fixed)
- 保存csv时没有去掉换行标识符(fixed)
- 切换A/D后未保存的标注没有被视为dirty=True, 并且未保存返回后没有检查文件是否存在(fixed)
- 直接切换视频产生闪退(fixed)
- windows下指针锁定没有在中间(fixed)
- 捕获保存文件时的异常