from execo import *
from execo_g5k import *
from execo_engine import *

class experiment_plan_generator():
    def __init__(self, variables_dict):
        s=sweep(variables_dict)
        print(s)

if __name__ == "__main__":
    dico = {}
    dico['colmet']=["on","off"]
    dico['sampling_periods']=[1,10]
    dico['nodes']=[2,10]
    plan=experiment_plan_generator(dico)
