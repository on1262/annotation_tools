import cv2
import os
from configs import GBL_CONF, isWin, isMacOS
import random


def GetCommentImg(img_path, out_path):
    '''Create a special image that each neuron is colored with a different color and has a number on it
    '''
    img = cv2.imread(img_path) # WHBGR
    target_map = (img[:,:,0] > 240) * (img[:,:,1] < 10) * (img[:,:,2] < 10) # WH
    target_map = target_map.astype('int')*255
    ret, labels = cv2.connectedComponents(target_map.astype('uint8'), connectivity=4)
    anchors = []
    for label in range(1, ret):
        random_color = [random.randint(0, 240), random.randint(100, 240), random.randint(0, 100)] # BGR
        reverse_color = [255 - c for c in random_color]
        mask = labels == label
        img[mask, :] = random_color
        # add number
        x, y = (labels == label).nonzero()
        x, y = round(x.mean()), round(y.mean())
        anchors.append((x, y))
        img = cv2.putText(img, str(label), (y, x), cv2.FONT_HERSHEY_SIMPLEX, 3, reverse_color, 6)
    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, 100])
    return ret - 1, anchors # number of neuros


class ImageAnnotator():
    def __init__(self, addi_params) -> None:
        self.conf = GBL_CONF['image_annotation']
        # single image mode
        self.single_img_mode = False if not addi_params else addi_params['single_img_mode']

        img_dir = "origin_imgs" if addi_params is None else addi_params['img_dir']
        if not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok=True)
        if self.single_img_mode: # sort by tick
            self.img_names = sorted([p for p in os.listdir(img_dir) if p.endswith('.jpg')], key=lambda x: int(x.split('@')[-1].split('.')[0]))
        else:
            self.img_names = sorted([p for p in os.listdir(img_dir) if p.endswith('.jpg')])
        self.img_paths = [os.path.join(img_dir, p) for p in self.img_names]
        self.img_cache = {}
        self.saved_flag = {}
        self.save_folder = "annotated_imgs" if addi_params is None else addi_params['save_folder']
        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder, exist_ok=True)
        self.save_paths = [os.path.join(self.save_folder, p) for p in self.img_names]
        if not addi_params:
            self.img_index = 0
        else:
            self.img_index = self.img_names.index(addi_params['init_img_name'])
        # window
        self.unique_name = "Image"
        # brush
        self.color = (255,0,0)
        self.brush_size = 10
        self.min_size = 2
        # scaling
        self.last_mouse_xy = (0,0)
        self.scale = 1.0
        self.scale_center = (0,0)
        # dragging
        self.dragging = False
        self.drag_start = (0,0)
        # drawing control
        self.drawing = False
        # watch mode
        self.watch_mode = False
        # save option
        self.dirty = False
        cv2.namedWindow(self.unique_name, cv2.WINDOW_NORMAL)
        if isWin:
            win_scale = self.conf['init_resize']['windows']
        elif isMacOS:
            win_scale = self.conf['init_resize']['macOS']
        wh, ww = round(win_scale * 1080), round(win_scale * 1920)
        cv2.resizeWindow(self.unique_name, ww, wh)
        if len(self.img_names) == 0:
            print('没有找到任何图片, 自动退出')
            return
        self.init_img(self.img_index)
        self.main_loop()

    def img_title(self):
        saved_status = ' (saved) ' if self.get_saved_flag() else ' '
        watch_status = ' (watch mode) ' if self.watch_mode else ' '
        return f'[{self.img_index+1}/{len(self.img_paths)}]' + saved_status + watch_status + self.img_names[self.img_index]
    
    def get_saved_flag(self):
        # 只和本次程序启动后的保存情况有关，如果继续增加标注，则保存flag失效
        return self.img_index in self.saved_flag and self.saved_flag[self.img_index] == True

    def init_window(self):
        cv2.setMouseCallback(self.unique_name, self.mouse_callback, None) # type: ignore
    
    def init_img(self, index):
        if index not in self.img_cache.keys():
            self.real_img = cv2.imread(self.img_paths[index])
        else:
            self.real_img = self.img_cache[index].copy()
        self.display_img = self.real_img.copy()
        
        cv2.imshow(self.unique_name, self.real_img)
        self.dirty = False
        self.init_window()
        
        self.drawing = False
        self.dragging = False
        self.scale = 1.0
        h, w = self.real_img.shape[:2]
        self.scale_center = (w // 2, h // 2)
        
        cv2.setWindowTitle(self.unique_name, self.img_title())

        if self.watch_mode or self.single_img_mode:
            self.watch_mode = False
            self.turn_on_watch_mode()

    def shift_xy(self, x1, y1, x2, y2, h, w):
        if x1 < 0:
            x1, x2 = 0, x2 - x1
        if y1 < 0:
            y1, y2 = 0, y2 - y1
        if x2 >= w:
            x1, x2 = x1 - (x2 - w), w
        if y2 >= h:
            y1, y2 = y1 - (y2 - h), h
        return x1, y1, x2, y2
    
    def draw_circle(self, x, y):
        canvas = self.display_img.copy()
        color = (255, 255, 255) if self.watch_mode else self.color
        thickness = -1 if self.watch_mode else 2
        cv2.circle(canvas, (x, y), round(self.brush_size*self.scale), color, thickness)
        cv2.imshow(self.unique_name, canvas)
    
    def rescale_window(self, x, y, origin_scale, new_scale):
        h, w = self.real_img.shape[:2]
        #print(f'origin_scale: {origin_scale}, new_scale: {new_scale}')
        #print(f'x: {x}, y: {y}')
        #print(f'w: {w}, h: {h}')
        x0, y0 = self.scale_center
        # 计算鼠标所处的缩放中心位置
        xm, ym = (x0 + (x - 0.5*w) / origin_scale, y0 + (y - 0.5*h) / origin_scale)
        # 计算缩放后的新角点
        x1, y1 = (xm - x / new_scale, ym - y / new_scale)
        x2, y2 = (xm + (w - x) / new_scale, ym + (h - y) / new_scale)
        # 如果角点碰到边框，则进行平移操作
        x1, y1, x2, y2 = self.shift_xy(x1, y1, x2, y2, h, w)
        x1, x2, y1, y2 = round(x1), round(x2), round(y1), round(y2)
        self.scale_center = ((x1 + x2)//2, (y1 + y2)//2)
        #print(f'x1: {x1}, x2: {x2}, y1: {y1}, y2: {y2}')
        self.display_img = cv2.resize(self.real_img[y1:y2, x1:x2 :], (w, h), interpolation=cv2.INTER_LINEAR)
        cv2.imshow(self.unique_name, self.display_img)
    
    def drag_window(self, start_x, start_y, end_x, end_y):
        # 计算原角点
        h, w = self.real_img.shape[:2]
        x0, y0 = self.scale_center
        dx, dy = (end_x - start_x) / self.scale, (end_y - start_y) / self.scale
        x1, y1 = (x0 - dx - 0.5 * w / self.scale, y0 - dy - 0.5 * h / self.scale)
        x2, y2 = (x0 - dx + 0.5 * w / self.scale, y0 - dy + 0.5 * h / self.scale)
        # 如果角点碰到边框，则进行平移操作
        x1, y1, x2, y2 = self.shift_xy(x1, y1, x2, y2, h, w)
        x1, x2, y1, y2 = round(x1), round(x2), round(y1), round(y2)
        self.scale_center = ((x1 + x2)//2, (y1 + y2)//2)
        self.display_img = cv2.resize(self.real_img[y1:y2, x1:x2 :], (w, h), interpolation=cv2.INTER_LINEAR)
        cv2.imshow(self.unique_name, self.display_img)

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if y > 20: # 拖动窗口时不会触发画图
                self.turn_off_watch_mode()
                self.drawing = True
                self.saved_flag[self.img_index] = False
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
        elif event == cv2.EVENT_RBUTTONDOWN: # start dragging
            self.dragging = True
            self.drag_start = (x, y)
        elif event == cv2.EVENT_RBUTTONUP: # end dragging
            self.dragging = False
        elif flags & cv2.EVENT_FLAG_RBUTTON: # 右键拖拽，用于平移图片
            self.last_mouse_xy = (x, y)
            if self.dragging:
                self.drag_window(self.drag_start[0], self.drag_start[1], x, y)
                self.drag_start = (x, y)
        elif flags & cv2.EVENT_FLAG_LBUTTON: # 左键拖拽，用于画图
            self.last_mouse_xy = (x, y)
            # NOTE: 在mac搭配触控板使用时，这个操作会产生卡顿，在其他系统和其他设备上则不会出现
            if self.drawing:
                canvas = self.real_img.copy()
                h, w = self.real_img.shape[:2]
                xm, ym = (self.scale_center[0] + (x - 0.5*w) / self.scale, self.scale_center[1] + (y - 0.5*h) / self.scale)
                xm, ym = round(xm), round(ym)
                # print(f'xm: {xm}, ym: {ym}')
                self.dirty = True
                cv2.circle(canvas, (xm, ym), self.brush_size, self.color, -1)
                self.real_img = canvas
                self.rescale_window(w // 2, h // 2, 1.0, self.scale)  
        elif event == cv2.EVENT_MOUSEMOVE:
            self.last_mouse_xy = (x, y)
            if not self.drawing:
                self.draw_circle(x, y)
        
        # 如果滚轮向上滚动，放大图片
        if event == cv2.EVENT_MOUSEWHEEL:
            xm, ym = self.last_mouse_xy
            newscale = 1.0
            flag = self.conf['reverse_mouse_wheel']
            if isWin:
                y = 1 if flags > 0 else -1
            if (flag and y < 0) or ((not flag) and y > 0):
                newscale = min(self.scale * self.conf['wheel_zoom_factor'][1], self.conf['scale_range'][1])
            elif y != 0:
                newscale = max(self.scale * self.conf['wheel_zoom_factor'][0], self.conf['scale_range'][0])
            self.rescale_window(xm, ym, self.scale, newscale)
            self.draw_circle(xm, ym)
            self.scale = newscale
    
    def turn_off_watch_mode(self):
        if not self.watch_mode:
            return
        self.watch_mode = False
        if self.img_index in self.img_cache.keys():
            self.real_img = self.img_cache[self.img_index].copy()
        else:
            self.real_img = cv2.imread(self.img_paths[self.img_index])
        h, w = self.real_img.shape[:2]
        self.rescale_window(w//2, h//2, 1.0, self.scale)
        cv2.setWindowTitle(self.unique_name, self.img_title())

    def turn_on_watch_mode(self):
        if self.watch_mode:
            return
        if os.path.exists(self.save_paths[self.img_index]):
            self.watch_mode = True
            self.img_cache[self.img_index] = self.real_img.copy()
            s_img = cv2.imread(self.save_paths[self.img_index])
            origin_img = cv2.imread(self.img_paths[self.img_index])
            # 将该图层与原图叠加
            self.real_img = cv2.addWeighted(origin_img, 1-self.conf['watch_mode_alpha'], s_img, self.conf['watch_mode_alpha'], 0)
            h, w = self.real_img.shape[:2]
            self.rescale_window(w//2, h//2, 1.0, self.scale)
            cv2.setWindowTitle(self.unique_name, self.img_title())
            self.draw_circle(self.last_mouse_xy[0], self.last_mouse_xy[1])
        else:
            print('注意：该图片还没有保存过标注信息, 无法打开观察模式')

    def select_img(self, new_index):
        # 在复制前关闭watch mode
        last_watch_mode = self.watch_mode
        self.turn_off_watch_mode()
        self.img_cache[self.img_index] = self.real_img.copy()
        self.img_index = new_index
        self.init_img(self.img_index)
        if last_watch_mode:
            self.turn_on_watch_mode()

    def main_loop(self):
        while(1):
            if isWin and cv2.getWindowProperty(self.unique_name, cv2.WND_PROP_VISIBLE) < 1:
                cv2.destroyAllWindows()
                return
            key = cv2.waitKey(0)
            if key == ord('q'): # decrease brush size
                self.brush_size = round(max(self.min_size, self.brush_size * 0.7))
                self.draw_circle(self.last_mouse_xy[0], self.last_mouse_xy[1])
            elif key == ord('r'): # reset
                self.img_cache.pop(self.img_index, None)
                self.init_img(self.img_index)
            elif key == ord('e'): # increase brush size
                self.brush_size = round(min(100, self.brush_size / 0.7))
                self.draw_circle(self.last_mouse_xy[0], self.last_mouse_xy[1])
            elif key == ord('w'): # enable watch mode
                if not self.watch_mode:
                    self.turn_on_watch_mode()
                else:
                    self.turn_off_watch_mode()
            elif key == ord('a') or key == ord('d'):
                if key == ord('a'):
                    new_index = max(0, self.img_index - 1)
                else:
                    new_index = min(self.img_index + 1, len(self.img_paths) - 1)
                if new_index != self.img_index:
                    if self.single_img_mode and self.dirty: # save image in this mode
                        self.save_img()
                    self.select_img(new_index)
            elif key == ord('-') or key == ord('='):
                if key == ord('-'):
                    new_index = max(0, self.img_index - 10)
                else:
                    new_index = min(self.img_index + 10, len(self.img_paths) - 1)
                if new_index != self.img_index:
                    self.select_img(new_index)   
            elif key == ord('s'):
                last_watch_mode = self.watch_mode
                self.turn_off_watch_mode()
                self.save_img()
                if self.single_img_mode:
                    cv2.destroyAllWindows()
                    return
                else:
                    self.img_cache[self.img_index] = self.real_img.copy()
                    if self.img_index < len(self.img_paths) - 1:
                        self.img_index += 1
                        self.init_img(self.img_index)
                        if last_watch_mode:
                            self.turn_on_watch_mode()
                    else:
                        print('已经是最后一张图片了')
            elif key == 27:
                cv2.destroyAllWindows()
                return
    
    def save_img(self):
        if (not self.dirty) and (self.conf['save_blank'] == False):
            print('注意：当前图片没有进行任何标注，不保存')
            return
        result = cv2.imwrite(self.save_paths[self.img_index], self.real_img, [cv2.IMWRITE_JPEG_QUALITY, 100])
        if result:
            self.saved_flag[self.img_index] = True
        else:
            print(f'注意：保存{self.save_paths[self.img_index]}时出现错误')
        print(f'已保存[{self.img_index+1}/{len(self.img_paths)}]{self.save_paths[self.img_index]}')
