import os, yaml

class Configs():
    def __init__(self) -> None:
        with open('configs.yml', 'r') as fp:
            self.conf = yaml.load(fp, Loader=yaml.FullLoader)
    
    def __getitem__(self, index):
        return self.conf[index]
    
GBL_CONF = Configs()