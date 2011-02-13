import re
import copy

import yaml

def load_yaml_file(filepath):
    file = open(filepath, "r")
    yamlstr = file.read()
    file.close()
    return load_yaml(yamlstr)
    
def load_yaml(yamlstr):
    return yaml.load(yamlstr)
    
class ConfigReader:
    def __init__(self, filename):
        self.yml = load_yaml_file(filename)
    
    def get(self, path):
        path_list = path.split(':')
        
        value = copy.copy(self.yml)
        
        for i, key in enumerate(path_list):
            if type(value) is not dict or not value.has_key(key):
                raise Exception("path '%s' does not exist" % path)
            
            value = value[key]
        
        return value
    