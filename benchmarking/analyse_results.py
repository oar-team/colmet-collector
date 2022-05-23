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
        sums[";".join(row[5:-1])].append(float(row[-1]))

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
    
    for i in range(len(sums.keys())):
        results['I'].append(1)
 
    for i in range(len(sums.keys())):
        k = list(sums.keys())[i]
        s = fsum(sums[k])
        avg = s / len(sums[k])
        key_parts = k.split(";")
        for j in range(len(key_parts) - 1):
            if(str(key_parts[j]) == str(expe[param_keys[j + 1]][0])):
                results[letters[j]].append(-1)
            else:
                results[letters[j]].append(1)
        for k in range(len(letters), len(combi)):
            res = 1
            for p in range(len(letters)):
                if letters[p] in combi[k]:
                    res *= results[letters[p]][i]
            results[combi[k]].append(res)
        results["avg"].append(avg)

    for i in range(len(results.keys()) - 1):
        k = list(results.keys())[i]
        s = 0
        for r in range(len(sums.keys())):
            s += results[k][r] * results["avg"][r]
        results[k].append(format(s, ".3f"))
        results[k].append(format(s / len(sums.keys()), '.3f'))
    results["avg"].append(0)
    results["avg"].append(0)

    """sst = 0
    for i in range(len(combi)):
        sst += len(sums.keys()) * (results[combi[i]][-1]**2)

    results["I"].append("X")
    for i in range(len(results.keys()) - 1):
        k = list(results.keys())[i]
        results[k].append(format(len(sums.keys()) * (results[k][-1]**2) / sst, '.3f'))"""

    print(": ".join(list(results.keys())))
    for i in range(len(results["I"])):
        out_string = str(results['I'][i])
        for j in range(len(combi)):
            out_string += ", {}".format(str(results[combi[j]][i]))
        out_string += ", {}".format(format(results["avg"][i], '.3f'))
        print(out_string)

    csv_file.close()
    yml_file.close()
