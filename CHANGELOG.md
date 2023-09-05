# CHANGELOG

## TODO List

- TODO: 进入图像标注时，如果有保存的标注，自动切换watch mode
- TODO: 更新readme
- TODO: 更严格的注释语法检查
- TODO：图像标注时切换前后帧自动保存，除非没有标注

## BUGS

- 按ESC关闭ImageAnnotator时未响应(fixed)
- 保存标注csv时，不存在的key会报错(fixed)
- 鼠标在两个连续的有效帧之间进度条不会跳动(fixed)
- (潜在，尚未稳定产生)center idx和idx不同步跳变，导致帧位置跳变
- vlc硬件加速出错(fixed, 需要更新ffmpeg: conda install -c conda-forge ffmpeg)
- windows下不能对标注帧添加注释, 切换帧注释不能随之切换(fixed)
- windows下手动关闭ImageAnnotator时按钮状态出错
- 空格键只实现了暂停没有继续功能(fixed)

## Fixed

- Selector在有效帧能够停留
- 转到给定帧时会自动更新comment, 并且指针指向最后
- 同时存在两个标亮框