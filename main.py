from image_annotation import ImageAnnotation
from video_annotation import start_video_annotation
import argparse

# 调用主函数
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', type=str, default='image', help='image or video')
    args = parser.parse_args()
    if args.type == 'image':
        tool = ImageAnnotation()
    elif args.type == 'video':
        start_video_annotation()

