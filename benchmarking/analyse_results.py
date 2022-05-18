import matplotlib
import csv
import sys
import yaml
from math import fsum
from collections import defaultdict
from itertools import combinations

if __name__ == "__main__":
    results_file = sys.argv[1]
    expe_file = sys.argv[2]
    csv_file = open(results_file, 'r')
    reader = csv.reader(csv_file, delimiter=";")
    yml_file = open(expe_file, 'r')
    expe = yaml.safe_load(yml_file)
    sums = defaultdict(list)
    for row in reader:
        sums[";".join(row[4:-1])].append(float(row[-1]))

    param_keys = list(expe.keys())
    letters = list()
    combi = list()
    for i in range(len(param_keys) - 1):
        letters.append(chr(65 + i))
        combi.append(letters[i])

    for i in range(2, len(param_keys)):
        c = combinations(letters, i)
        for j in c:
            combi.append("".join(j))
    results = defaultdict(list)

    print(" ".join(combi))
    for i in range(len(sums.keys())):
        k = list(sums.keys())[i]
        s = fsum(sums[k])
        avg = s / len(sums[k])
        key_parts = k.split(";")
        out_string = "1 "
        for i in range(len(key_parts)):
            if(str(key_parts[i]) == str(expe[param_keys[i + 1]][0])):
                out_string += "-1 "
            else:
                out_string += " 1 "
        out_string += " {}".format(format(avg, ".3f"))
        print(out_string)

    csv_file.close()
    yml_file.close()
