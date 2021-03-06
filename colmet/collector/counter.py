import os
import sys
import yaml
import glob

def load_metrics_orders():
    metrics_orders = {}
    d = os.path.dirname(sys.modules["colmet"].__file__)
    for metrics_orders_file in glob.glob(d + '/collector/metrics/*.yml'):
        with open(metrics_orders_file, 'r') as stream:
            try:
                mo = yaml.safe_load(stream)
                v = mo['meta']['version']
                metrics_orders[v] = {}
                for i, metric_name in enumerate(mo['metrics_order']):
                  metrics_orders[v][i] = metric_name
            except yaml.YAMLError as exc:
                print(exc)
    print(metrics_orders)
    return metrics_orders


class Counter:
    def __init__(self, hostname, timestamp, job_id, backend_name, metrics):
        self.hostname = hostname
        self.timestamp = timestamp
        self.job_id = job_id
        self.backend_name = backend_name
        self.metrics = metrics


class CounterFactory:
    metrics_orders = load_metrics_orders()
    def __init__(self, data):
        self.counters = []
        for job_id, payload in data[0].items():
            print(payload)
            self.hostname = payload[0].decode('utf-8')
            self.timestamp = payload[1]
            version = payload[2]
            print("Version:", version)
            if version not in CounterFactory.metrics_orders:
                print("Version {} of metrics is not supported".format(version))
            else:
                self.job_id = job_id
                for backend in payload[3]:
                    self.backend_name = backend[0].decode('utf-8')
                    tmp = backend[1]
                    self.metric_names = []
                    for compressed_metric_name in tmp:
                        self.metric_names.append(CounterFactory.metrics_orders[version][compressed_metric_name])
                    self.metric_values = backend[2]
                    self.backend_metrics = dict(zip(self.metric_names, self.metric_values))
                    counter = Counter(self.hostname, self.timestamp, self.job_id,
                                      self.backend_name, self.backend_metrics)
                    self.counters.append(counter)

    def get_counters(self):
        return self.counters
