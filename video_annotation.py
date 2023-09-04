#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# <https://github.com/oaubert/python-vlc/blob/master/examples/wxvlc.py>
#
# WX example for VLC Python bindings
# Copyright (C) 2009-2010 the VideoLAN team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.
#
"""
A simple example for VLC python bindings using wxPython.

Author: Michele Orrù
Date: 23-11-2010

Modified by: YuTong Chen
Data: 02-09-2023
"""

# Tested with Python 3.7.4, wxPython 4.0.6 on macOS 10.13.6 only.
__version__ = '19.07.28'  # mrJean1 at Gmail dot com

# import external libraries
from tracemalloc import start
import wx  # 2.8 ... 4.0.6
import vlc

# import standard libraries
import os
from os.path import basename, expanduser, isfile, exists, join as joined
import sys
import math
from configs import GBL_CONF
import numpy as np
import re, csv
from image_annotation import ImageAnnotator, GetCommentImg

class AnnotationData():
    def __init__(self) -> None:
        self.data = {}
        self.sorted_keys = []

    def load_data(self, csv_path):
        self.data = {}
        videoname = os.path.split(csv_path)[-1][:-4] + '.mp4'
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data[int(row['tick'])] = {
                    'type': row['type'],
                    'videoname': videoname,
                    'img_name': row['img_name'],
                    'region_count': row['region_count'],
                    'sample_attr': row['attr'],
                    'frame_attr': row['frame_attr'],
                    'comment': row['comment']
                }
        self.sorted_keys = sorted(list(self.data.keys()))
    
    def save_data(self, csv_path):
        videoname = os.path.split(csv_path)[-1][:-4] + '.mp4'
        with open(csv_path, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['tick', 'type', 'videoname', 'img_name', 'region_count', 'sample_attr', 'frame_attr', 'comment'])
            for tick in sorted(self.data.keys()):
                writer.writerow([
                    tick, 
                    self.data[tick]['type'], 
                    videoname,
                    self.data[tick]['img_name'],
                    self.data[tick]['region_count'], 
                    self.data[tick]['sample_attr'], 
                    self.data[tick]['frame_attr'],
                    self.data[tick]['comment']
                ])

    def register(self, reg_dict:dict):
        assert(isinstance(reg_dict, dict))
        tick = reg_dict['tick']
        reg_dict.pop('tick')
        assert(isinstance(tick, int))
        if tick not in self.data: # create item
            self.data[tick] = reg_dict
            self.sorted_keys.append(tick)
            self.sorted_keys = sorted(self.sorted_keys)
        else: # overwrite value
            for key in self.data[tick]:
                if key in reg_dict:
                    if key == 'type' and self.data[tick][key] == 'image': # comment will not over write picture
                        continue
                    self.data[tick][key] = reg_dict[key]

    def query_ticks(self, t_min, t_max):
        # get ticks in [t_min, t_max)
        result = set()
        assert(isinstance(t_min, int) and isinstance(t_max, int))
        assert(t_max >= t_min)
        index_min = np.searchsorted(self.sorted_keys, t_min)
        index_max = np.searchsorted(self.sorted_keys, t_max)
        index_min = max(0, index_min - 1)
        index_max = min(len(self.sorted_keys), index_max + 1)
        for i in range(index_min, index_max):
            if t_min <= self.sorted_keys[i] < t_max:
                result.add(self.data[self.sorted_keys[i]]['type'])
            if 'image' in result and 'comment_only' in result:
                return result
        return result


VIDEO_ANNO = AnnotationData()

def create_file_folder():
    paths = [
        'video_input',
        'video_annotation',
        'video_output'
    ]
    for p in paths:
        if not exists(p):
            os.makedirs(p, exist_ok=True)
    for pv in sorted(os.listdir('video_input')):
        if pv.endswith('.mp4'):
            po = joined('video_output', pv)
            if not exists(po):
                os.makedirs(po, exist_ok=True)
                os.makedirs(joined(po, 'saved_imgs'), exist_ok=True)
                os.makedirs(joined(po, 'images'), exist_ok=True)

class Selector(wx.MiniFrame):
    def __init__(self, parent):
        wx.MiniFrame.__init__(self, parent, -1, 'Floating Panel', style=wx.NO_BORDER | wx.FRAME_FLOAT_ON_PARENT)
        self.SetTransparent(150)
        self.panel = wx.Panel(self, -1)
        self.panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.panel.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.panel.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.panel.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        # selection information
        self.tick_option = [ # (ms, text, margin, frame_width)
            (1000.0/30.0, '1 frame', 5, 25),
            (100.0, '100 ms', 6, 25),
            (500.0, '500 ms', 7, 25),
            (1000.0, '1 second', 10, 25),
            (5000.0, '5 seconds', 12, 25),
            (10000.0, '10 seconds', 13, 25),
            (30000.0, '30 seconds', 14, 25),
            (60*1000.0, '1 minute', 15, 25),
            (5*60*1000.0, '5 minutes', 17, 25),
        ]
        self.current_tick_option = 3

        # painting
        self.paint_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.paint_timer)
        self.init_mouse_x = None
        self.init_time = None
        self.x_delta = 0
        
        self.frame_width = 25
        self.frame_height = 60
        self.margin = 5
        self.window_height = 150
        self.window_width = 11*(self.frame_width + self.margin)
        self.draw_y = self.panel.GetSize().GetHeight() // 2 + self.frame_height // 2

    def OnMouseWheel(self, evt):
        # reset initial mouse xy if scale is changed
        _, self.init_time = self.GetCurrentMouseTick(self.init_mouse_x + self.x_delta)
        self.init_mouse_x += self.x_delta
        self.x_delta = 0
        delta = evt.GetWheelRotation()
        if delta > 0:
            self.current_tick_option = min(self.current_tick_option + 1, len(self.tick_option) - 1)
        else:
            self.current_tick_option = max(self.current_tick_option - 1, 0)
        self.margin, self.frame_width = self.tick_option[self.current_tick_option][2:]
        self.panel.Refresh()
    
    def OnTimer(self, evt):
        self.panel.Refresh()

    def OnShow(self, mouse_pos, init_time):
        self.init_mouse_x = self.window_width // 2
        self.init_time = init_time
        self.x_delta = 0
        self.panel.Bind(wx.EVT_MOTION, self.OnMotion)

        self.paint_timer.Start(30)
        parent_position = self.Parent.GetPosition()
        self.SetSize((self.window_width, self.window_height))
        # top-bottom: y, left-right: x
        # set center position to mouse position
        self.SetPosition((parent_position.x + mouse_pos.x - self.window_width // 2, parent_position.y + mouse_pos.y - self.window_height // 2))
        self.Show()
        self.Raise()

    def OnHide(self):
        self.paint_timer.Stop()
        self.panel.Unbind(wx.EVT_MOTION)
        self.x_delta = 0
        self.Hide()

    def OnPaint(self, evt):
        size = self.panel.GetSize() # w,h
        tile_width = self.frame_width + self.margin
        t_interval = self.tick_option[self.current_tick_option][0] # ms
        start_idx = -round((self.window_width / tile_width) // 2) - 1 # left
        end_idx = -start_idx # right

        dc = wx.PaintDC(self.panel)
        dc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 128)))

        # paint text on top center
        dc.SetFont(wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        dc.DrawText('Tick: ' + self.tick_option[self.current_tick_option][1], size[0] // 2 - 60, 0)
        # sensor area
        sensor = {}
        corrected_x = self.x_delta
        center_idx = 0
        t_bounds = {}
        for idx in range(start_idx, end_idx+1):
            if (idx - 0.5 <= self.x_delta / tile_width < idx + 0.5):
                center_idx = idx # idx=0 is always around w//2. idx - center_idx is unchanged in mouse moving

        for idx in range(start_idx, end_idx+1):
            t_bounds[idx] = [
                int(self.init_time + (idx - center_idx - 0.5) * t_interval),
                int(self.init_time + (idx - center_idx + 0.5) * t_interval)
            ]
            sensor[idx] = VIDEO_ANNO.query_ticks(t_bounds[idx][0], t_bounds[idx][1])

        if (len(sensor[0]) > 0): # select valid tick, freeze motion animation
            corrected_x = 0
            
        for idx in range(start_idx, end_idx+1):
            dc.SetPen(wx.TRANSPARENT_PEN)
            draw_x = round(size[0] // 2 + (idx-1) * tile_width + (corrected_x + 0.5*tile_width) % tile_width)
            if (draw_x - size[0] // 2) * (draw_x + tile_width - size[0] // 2) <= 0: # now selected rectangle
                dc.SetPen(wx.Pen(wx.Colour(233, 232, 88, 250), 2))
            query_result = sensor[idx]
            # TODO banner will not move if mouse is on annotated ticks
            if 'image' in query_result and 'comment_only' in query_result:
                dc.SetBrush(wx.Brush(wx.Colour(64, 150, 243, 200)))
                dc.DrawRectangle(draw_x, self.draw_y + self.frame_height // 2, self.frame_width, self.frame_height // 2)
                dc.SetBrush(wx.Brush(wx.Colour(68, 194, 146, 200)))
                dc.DrawRectangle(draw_x, self.draw_y, self.frame_width, self.frame_height // 2)
            elif 'image' in query_result: # blue
                dc.SetBrush(wx.Brush(wx.Colour(64, 150, 243, 200)))
                dc.DrawRectangle(draw_x, self.draw_y, self.frame_width, self.frame_height)
            elif 'comment_only' in query_result: # green
                dc.SetBrush(wx.Brush(wx.Colour(68, 194, 146, 200)))
                dc.DrawRectangle(draw_x, self.draw_y, self.frame_width, self.frame_height)
            else:
                dc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 128)))
                dc.DrawRectangle(draw_x, self.draw_y, self.frame_width, self.frame_height)

            dc.SetFont(wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText(str(idx - center_idx), draw_x+2, self.draw_y + self.frame_height - 20)
            #else:
            #    dc.DrawText(str(idx), draw_x+2, self.draw_y + 2)
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText(str(t_bounds[idx][0]), draw_x+2, self.draw_y + self.frame_height + 10)
            dc.DrawText(str(t_bounds[idx][1]), draw_x+2, self.draw_y + self.frame_height + 20)

        # draw center dash line
        dc.SetPen(wx.Pen('black', 2))
        dc.DrawLine(size[0] // 2, 30, size[0] // 2, size[1] - 20)

    def GetCurrentMouseTick(self, mouse_x):
        # change painting
        x_delta = (mouse_x - self.init_mouse_x)
        
        # send event to parent
        delta_tick = self.tick_option[self.current_tick_option][0] / (self.frame_width + self.margin) * x_delta
        return x_delta, round(-delta_tick + self.init_time)

    def OnMotion(self, evt):
        mouse_x = evt.GetPosition().x
        x_delta, new_tick = self.GetCurrentMouseTick(mouse_x)
        if new_tick <= 0 or new_tick > self.Parent.timeslider.GetMax():
            # move init mouse position if out of range
            self.init_mouse_x = mouse_x
            self.x_delta = 0
            self.init_time = self.Parent.player.get_time()
        else:
            self.x_delta = x_delta
            self.Parent.OnVideoMotion(new_tick)
    
    def OnLeftUp(self, evt):
        self.Parent.OnVideoLeftClick(evt)

    def OnRightUp(self, evt):
        # cancel selection, move to original tick
        self.Parent.OnVideoMotion(self.init_time)
        self.Parent.OnSelectFlushTimer(None)
        self.Parent.OnVideoLeftClick(evt)

class VideoAnnotator(wx.Frame):
    """The main window has to deal with events.
    """
    def __init__(self):
        wx.Frame.__init__(self, None, -1, title='wxVLC', pos=wx.DefaultPosition, size=(550, 500))

        self.conf = GBL_CONF['video_annotation']

        # init regex
        self.init_regex()

        # search input folder
        create_file_folder()
        self.video_names = []
        for pv in sorted(os.listdir('video_input')):
            if pv.endswith('.mp4'):
                self.video_names.append(pv)
        self.video_idx = 0
        self.video_path = joined('video_input', self.video_names[self.video_idx]) if len(self.video_names) > 0 else None

        # Menu Bar
        # File Menu
        self.frame_menubar = wx.MenuBar()
        self.file_menu = wx.Menu()
        self.file_menu.Append(1, "&Open...", "Open from file...")
        self.file_menu.AppendSeparator()
        self.file_menu.Append(2, "&Close", "Quit")
        self.file_menu.AppendSeparator()
        self.file_menu.Append(3, '&Toggle Next Video')
        self.file_menu.AppendSeparator()
        self.file_menu.Append(4, "&Export All Annotations")
        self.Bind(wx.EVT_MENU, self.OnOpen, id=1)
        self.Bind(wx.EVT_MENU, self.OnExit, id=2)
        self.frame_menubar.Append(self.file_menu, "File")
        self.SetMenuBar(self.frame_menubar)

        # Panels
        # The first panel holds the video and it's all black
        self.videopanel = wx.Panel(self, -1)
        self.videopanel.SetBackgroundColour(wx.BLACK)

        # The second panel holds controls
        ctrlpanel = wx.Panel(self, -1)
        self.timeslider = wx.Slider(ctrlpanel, -1, 0, 0, 1000)
        self.timeslider.SetRange(0, 1000)

        # third panel for frame selection
        self.selecting = False
        self.select_flush_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnSelectFlushTimer, self.select_flush_timer)
        self.mouse_tick = 0
        self.selectframe = Selector(self)
        self.selectframe.Hide()

        # fourth panel for comment
        self.commentpanel = wx.Panel(self, -1)
        self.commentpanel.SetBackgroundColour(wx.BLACK)
        self.commentpanel.Bind(wx.EVT_PAINT, self.OnPaintCommentImg)
        self.commentpanel.Hide()

        self.pause = wx.Button(ctrlpanel, label="Pause")
        self.pause.Disable()
        self.play = wx.Button(ctrlpanel, label="Play")
        self.stop = wx.Button(ctrlpanel, label="Stop")
        self.stop.Disable()
        self.comment = wx.TextCtrl(ctrlpanel, style=wx.TE_PROCESS_ENTER | wx.TE_MULTILINE | wx.TE_RICH2)
        self.comment.SetEditable(False)
        self.comment.SetMaxSize((1920, 30))
        self.comment.Bind(wx.EVT_TEXT_ENTER, self.OnFinishComment)
        self.comment.Bind(wx.EVT_TEXT, self.OnInputComment)

        # Bind controls to events
        self.Bind(wx.EVT_BUTTON, self.OnPlay,   self.play)
        self.Bind(wx.EVT_BUTTON, self.OnPause,  self.pause)
        self.Bind(wx.EVT_BUTTON, self.OnStop,   self.stop)
        self.videopanel.Bind(wx.EVT_KEY_DOWN, self.OnPressKey)

        self.videopanel.Bind(wx.EVT_LEFT_UP, self.OnVideoLeftClick)
        # Bind the time slider to the seek function
        self.seeking = False
        self.Bind(wx.EVT_SCROLL_THUMBTRACK, self.OnSeek, self.timeslider)
        self.Bind(wx.EVT_SCROLL_THUMBRELEASE, self.OnRelease, self.timeslider)

        self.seek_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnSeekTimer, self.seek_timer)

        # Give a pretty layout to the controls
        ctrlbox = wx.BoxSizer(wx.VERTICAL)
        box1 = wx.BoxSizer(wx.HORIZONTAL)
        box2 = wx.BoxSizer(wx.HORIZONTAL)
        box3 = wx.BoxSizer(wx.HORIZONTAL)
        # box1 contains the timeslider
        box1.Add(self.timeslider, 1)
        # box2 contains some buttons and the volume controls
        box2.Add(self.play, flag=wx.RIGHT, border=5)
        box2.Add(self.pause)
        box2.Add(self.stop)
        box2.Add((-1, -1), 1)
        box3.Add(self.comment, 1, wx.EXPAND)
        # Merge box1 and box2 to the ctrlsizer
        ctrlbox.Add(box1, flag=wx.EXPAND | wx.BOTTOM, border=10)
        ctrlbox.Add(box2, 1, wx.EXPAND)
        ctrlbox.Add(box3, flag=wx.EXPAND)
        ctrlpanel.SetSizer(ctrlbox)
        # Put everything togheter
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.videopanel, 1, flag=wx.EXPAND)
        sizer.Add(self.commentpanel, 1, flag=wx.EXPAND)
        sizer.Add(ctrlpanel, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=10)
        self.SetSizer(sizer)
        self.SetMinSize((350, 300))

        # finally create the timer, which updates the timeslider
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnSliderTimer, self.timer)

        # image annotating flag
        self.img_annotating = False

        # VLC player controls
        self.Instance = vlc.Instance()
        self.player = self.Instance.media_player_new()

    def init_regex(self):
        sample_tag_body = r"\b(?:" + '|'.join(self.conf['comment']['sample_keys']) + r")\b(?:,\b(?:" \
            + '|'.join(self.conf['comment']['sample_keys']) + r")\b)*"
        frame_tag_body = r"\b(?:" + '|'.join(self.conf['comment']['frame_keys']) + r")\b(?:,\b(?:" \
            + '|'.join(self.conf['comment']['frame_keys']) + r")\b)*"
        self.re_pattern = r"\d" + "@" + sample_tag_body + "|" + 'frm' + "@" + frame_tag_body
        print('RE_PATTERN:', self.re_pattern)
        self.comment_info = None

    def ToggleVideo(self, new_idx):
        if new_idx < len(self.video_names) and new_idx >= 0:
            self.video_idx = new_idx
            self.video_path = joined('video_input', self.video_names[self.video_idx])
            self.OnStop(None)
            self.OnOpen(None)
    
    def GetSnapshoot(self, out_path):
        # return successful or not
        if self.player.get_media():
            return self.player.video_take_snapshot(0, out_path, 0, 0)
        else:
            return -1
    
    def OnPressKey(self, evt):
        # press c to comment
        code = evt.GetKeyCode()
        if code == ord('c') or code == ord('C'):
            # add comment though text
            if (not self.selecting) and (not self.player.is_playing()):
                comment_img_path = joined('video_output', self.video_names[self.video_idx], 'saved_imgs', 
                    str.split(self.video_names[self.video_idx], '.')[0] + '@' + str(self.player.get_time()) + '.jpg')
                out_path = joined('video_cache', str.split(self.video_names[self.video_idx], '.')[0] + '@' + str(self.player.get_time()) + '.jpg')
                if exists(comment_img_path):
                    self.comment_img_path = out_path
                    self.videopanel.Hide()
                    self.commentpanel.SetSize(self.videopanel.GetSize())
                    self.commentpanel.Show()
                else:
                    self.comment_img_path = None
                self.comment.SetEditable(True)
                self.comment.SetFocus()
        elif code == ord('s') or code == ord('S'): 
            if (not self.selecting) and (self.player.get_media() is not None):
                self.StartImageAnnotator(self.player.get_time(), 'Annotation', self.comment.GetValue())
        elif code == wx.WXK_SPACE:
            self.OnPause(evt)
    
    def OnPaintCommentImg(self, evt):
        dc = wx.PaintDC(self.commentpanel)
        # dc.SetBrush(wx.Brush(wx.Colour(0, 0, 255, 128)))
        # dc.DrawRectangle(0, 0, self.commentpanel.GetSize().GetWidth(), self.commentpanel.GetSize().GetHeight())
        # calculate real video size
        ori_size = self.player.video_get_size()
        wh_ratio = ori_size[0] / ori_size[1]
        vs = self.videopanel.GetSize()
        if vs[0] / vs[1] < wh_ratio:
            w, h = vs[0], round(vs[0] / wh_ratio)
            w_offset, h_offset = 0, (vs[1] - h) // 2
        else:
            w, h = round(vs[1]*wh_ratio), vs[1]
            w_offset, h_offset = (vs[0] - w) // 2, 0
        wximg = wx.Image(self.comment_img_path, wx.BITMAP_TYPE_ANY)
        wximg = wximg.Scale(w, h, quality=wx.IMAGE_QUALITY_HIGH)
        wximg = wx.Bitmap(wximg)
        dc.DrawBitmap(wximg, w_offset, h_offset)
    
    def StartImageAnnotator(self, tick, type, comment):
        # take a snapshoot and boot image annotator
        img_dir = joined('video_output', self.video_names[self.video_idx], 'images')
        save_folder = joined('video_output', self.video_names[self.video_idx], 'saved_imgs')
        img_name = str.split(self.video_names[self.video_idx], '.')[0] + '@' + str(self.player.get_time()) + '.jpg'
        out_path = joined('video_cache', str.split(self.video_names[self.video_idx], '.')[0] + '@' + str(self.player.get_time()) + '.jpg')
        comment_img_path = joined('video_output', self.video_names[self.video_idx], 'saved_imgs', 
            str.split(self.video_names[self.video_idx], '.')[0] + '@' + str(self.player.get_time()) + '.jpg')
        if self.player.video_take_snapshot(0, joined(img_dir, img_name), 0, 0) == 0:
            self.img_annotating = True
            # disable components to prevent time changing
            self.timeslider.Disable()
            play_status = self.play.IsEnabled()
            stop_status = self.stop.IsEnabled()
            if play_status:
                self.play.Disable()
            if stop_status:
                self.stop.Disable()
            
            ImageAnnotator(addi_params={
                'img_dir': img_dir,
                'save_folder': save_folder,
                'init_img_name': img_name,
                'single_img_mode': True
            })
            # create img for comment
            if exists(comment_img_path):
                n_region = GetCommentImg(comment_img_path, out_path)
            # register annotation
            # ['tick', 'type', 'videoname', 'img_name', 'region_count', 'sample_attr', 'frame_attr']
            reg_dict = {
                'tick': self.player.get_time(),
                'type': 'image',
                'video_name': self.video_names[self.video_idx],
                'img_name': img_name,
                'region_count':n_region
            }
            VIDEO_ANNO.register(reg_dict)

            if play_status:
                self.play.Enable()
            if stop_status:
                self.stop.Enable()
            self.img_annotating = False
            self.timeslider.Enable()
            
            self.Raise() # fetch focus

    def OnFinishComment(self, evt):
        # register annotation
        # TODO add annotation check
        # ['tick', 'type', 'videoname', 'img_name', 'region_count', 'sample_attr', 'frame_attr', 'comment']
        if self.comment_info is not None:
            reg_dict = {
                'tick': self.player.get_time(),
                'type': 'comment_only',
                'video_name': self.video_names[self.video_idx],
                'comment': self.comment_info['comment']
            }
            sample_attr = []
            for s in self.comment_info['fields']:
                s = str(s)
                if s.startswith('frm@'):
                    reg_dict['frame_attr'] = s.split('@')[-1]
                else:
                    num, attr = s.split('@')
                    sample_attr.append((num, attr))
            if len(sample_attr) > 0:
                reg_dict['sample_attr'] = ';'.join([s[1] for s in sorted(sample_attr, key=lambda x:x[0])])
            VIDEO_ANNO.register(reg_dict)
        self.commentpanel.Hide()
        self.videopanel.Show()
        self.comment.SetEditable(False)
        self.comment_info = None
    
    def OnInputComment(self, evt):
        # run regex
        input_str = evt.GetString()
        result = re.findall(self.re_pattern, input_str)
        spt = re.split('(' + self.re_pattern + ')', input_str)
        spt = [s for s in spt if s != '']
        for idx in range(len(spt)):
            i_start = 0 if idx == 0 else len(''.join(spt[0:idx]))
            if spt[idx] in result:
                self.comment.SetStyle(i_start, i_start + len(spt[idx]), \
                    wx.TextAttr(wx.Colour(70, 184, 92), wx.WHITE, font=wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)))
            else:
                self.comment.SetStyle(i_start, i_start + len(spt[idx]), \
                    wx.TextAttr(wx.Colour(113, 113, 113), wx.Colour(200, 200, 200), font=wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)))
        # update comment
        unmatched = ' '.join([s for s in spt if (s not in result) and (s.strip() != '')])
        self.comment_info = {
            'comment': input_str, # original comment
            'fields': result,
            'unmatched':  unmatched
        }
    
    def OnExit(self, evt):
        """Closes the window.
        """
        self.Close()

    def OnOpen(self, evt):
        """Pop up a new dialow window to choose a file, then play the selected file.
        """
        # if a file is already running, then stop it.
        self.OnStop(None)

        if not self.video_path: # Create a file dialog opened in the current home directory,
            # to show all kind of files, having as title "Choose a ...".
            dlg = wx.FileDialog(self, "Choose a video file", expanduser('~'),
                                      "", "*.*", wx.FD_OPEN)  # XXX wx.OPEN
            if dlg.ShowModal() == wx.ID_OK:
                self.video_path = joined(dlg.GetDirectory(), dlg.GetFilename())
            # finally destroy the dialog
            dlg.Destroy()

        if isfile(self.video_path):  # Creation
            self.Media = self.Instance.media_new(self.video_path)
            self.player.set_media(self.Media)
            # Report the title of the file chosen
            title = self.player.get_title()
            # if an error was encountred while retrieving the title,
            # otherwise use filename
            self.SetTitle("%s - %s" % (title if title != -1 else 'wxVLC', basename(self.video_path)))

            # set the window id where to render VLC's video output
            handle = self.videopanel.GetHandle()
            if sys.platform.startswith('linux'):  # for Linux using the X Server
                self.player.set_xwindow(handle)
            elif sys.platform == "win32":  # for Windows
                self.player.set_hwnd(handle)
            elif sys.platform == "darwin":  # for MacOS
                self.player.set_nsobject(handle)
            self.OnPlay(None)

    def OnPlay(self, evt):
        """Toggle the status to Play/Pause.

        If no file is loaded, open the dialog window.
        """
        # check if there is a file to play, otherwise open a
        # wx.FileDialog to select a file
        if not self.player.get_media():
            self.OnOpen(None)
            self.seeking = False
            # Try to launch the media, if this fails display an error message
        elif self.player.play():  # == -1:
            self.errorDialog("Unable to play.")
        elif (not self.seeking) and (not self.img_annotating):
            # adjust window to video aspect ratio
            # w, h = self.player.video_get_size()
            # if h > 0 and w > 0:  # often (0, 0)
            #     self.videopanel....
            self.timer.Start(100)  # XXX millisecs
            self.play.Disable()
            self.pause.Enable()
            self.stop.Enable()

    def OnVideoLeftClick(self, evt):
        if self.selecting:
            self.selecting = False
            self.select_flush_timer.Stop()
            self.selectframe.OnHide()
            self.videopanel.SetFocus()
        else:
            self.selecting = True
            if self.player.is_playing():
                self.OnPause(None)
            self.select_flush_timer.Start(100)
            self.mouse_tick = self.player.get_time() # initial mouse tick
            self.selectframe.OnShow(evt.GetPosition(), self.player.get_time())

    def OnVideoMotion(self, new_tick):
        if (not self.selecting) or (not self.player.get_media()):
            return
        # update the time on the slider
        self.mouse_tick = max(0, min(self.timeslider.GetMax(), new_tick))
    
    def OnSelectFlushTimer(self, evt):
        if self.mouse_tick < self.timeslider.GetMax():
            self.player.set_time(self.mouse_tick)
            self.timeslider.SetValue(self.mouse_tick)

    def OnPause(self, evt):
        """Pause the player.
        """
        if self.seeking or self.img_annotating:
            return
        if self.player.is_playing():
            self.play.Enable()
            self.pause.Disable()
        else:
            self.play.Disable()
            self.pause.Enable()
        self.player.pause()

    def OnStop(self, evt):
        """Stop the player.
        """
        if self.img_annotating:
            return
        self.seeking = False
        self.player.stop()
        # reset the time slider
        self.timeslider.SetValue(0)
        self.timer.Stop()
        self.play.Enable()
        self.pause.Disable()
        self.stop.Disable()

    def OnSliderTimer(self, evt):
        """Update the time slider according to the current movie time.
        """
        if self.seeking or self.selecting:
            return
        # since the self.player.get_length can change while playing,
        # re-set the timeslider to the correct range.
        length = self.player.get_length()
        self.timeslider.SetRange(-1, length)
        # update the time on the slider
        time = self.player.get_time()
        self.timeslider.SetValue(time)

    def OnSeek(self, evt):
        """Seek the player according to the time slider.
        """
        if not self.seeking:
            self.seeking = True
            self.OnPause(None)
            self.seek_timer.Start(100)  # XXX millisecs

    def OnSeekTimer(self, evt):
        offset = self.timeslider.GetValue()
        # Don't seek when the slider is at the end
        if offset < self.timeslider.GetMax():
            self.player.set_time(offset)
    
    def OnRelease(self, evt):
        self.seeking = False
        self.seek_timer.Stop()
        self.OnPlay(None)

    def errorDialog(self, errormessage):
        """Display a simple error dialog.
        """
        edialog = wx.MessageDialog(self, errormessage, 'Error', wx.OK|
                                                                wx.ICON_ERROR)
        edialog.ShowModal()


def start_video_annotation():
    # Create a wx.App(), which handles the windowing system event loop
    app = wx.App()  # XXX wx.PySimpleApp()
    # Create the window containing our media player
    player = VideoAnnotator()
    # show the player window centred
    player.Centre()
    player.Show()
    # run the application
    app.MainLoop()
