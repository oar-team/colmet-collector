from execo import *
from execo_g5k import *
from execo_engine import Engine
from experiment_plan import experiment_plan_generator
from nixos_compose.nxc_execo import get_oar_job_nodes_nxc, build_nxc_execo
import traceback
import logging
import time
import os
import sys
import threading
username=""
starttime=0

def parse_output(s):
    lines=s.splitlines()
    out=""
    for l in lines:
        if l.startswith(" Time in seconds"):
            sp=l.split(" ")
            out=sp[-1]
    return out

def reserve_nodes(nb_nodes, site, cluster, walltime=3600):
    jobs=oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(nb_nodes), walltime=walltime, additional_options="-O /dev/null -E /dev/null"), site)])
    return jobs

def write_nodefile(nodes):
    hf=open("{}/nodefile".format(os.getcwd()),"w")
    for n in nodes:
        print(n)
        for _ in range(0, int(get_host_attributes(n)['architecture']['nb_threads'])):
            hf.write(n+"\n")
    hf.close()

class Colmet_bench(Engine):
    """
    
    """
    def __init__(self):
        super(Colmet_bench, self).__init__()
        parser = self.args_parser
        parser.add_argument('--nxc_build_file', help='Path to the NXC deploy file')
        parser.add_argument('--build', action='store_true', help='Build the composition')
        parser.add_argument('--nxc_folder', default="~/nixProjects/nixos-compose", help="Path to the NXC folder")
        parser.add_argument('--experiment_file', help="File describing the experiment to perform", default="expe_5.yml")
        parser.add_argument('--result_file', help="Output file", default="expe_5_benchmark")
        parser.add_argument('--time_experiment', default=90, help="Time needed to perform one repetition (in sec)")
        parser.add_argument('--site', default="grenoble", help="G5K site where the submission will be issued")
        parser.add_argument('--cluster', default="dahu", help="G5K cluster from where nodes should be requested")
        parser.add_argument('-v', '--verbose', action='count', dest="verbosity", default=1)
        parser.add_argument('-n', '--nb_nodes', dest="number_nodes", default="1")
        parser.add_argument('--name_bench', default="lu")
        parser.add_argument('--class_bench', default="C")
        parser.add_argument('--type_bench', default="mpi")
        self.nodes = {}
        self.oar_job_id = -1
        self.colmet_launched = False

    def init(self):
        logger.setLevel(40 - self.args.verbosity * 10)
        self.plan = experiment_plan_generator(self.args.experiment_file)
        nxc_build_file = None
        if self.args.build:
            (nxc_build_file, _time, _size) = build_nxc_execo(self.args.nxc_folder, site, cluster, walltime=15*60)
        elif self.args.nxc_build_file is not None:
            nxc_build_file = self.args.nxc_build_file
        else:
            raise Exception("No compose info file")
        oar_job = reserve_nodes(self.plan.get_required_nb_node()+1, self.args.site, self.args.cluster, walltime = self.plan.get_nb_remaining()*self.args.time_experiment)
        self.oar_job_id, site = oar_job[0]
        roles = {"collector":1, "compute":self.plan.get_required_nb_node()}
        node_hostnames = get_oar_job_nodes(self.oar_job_id, self.args.site)
        self.nodes = get_oar_job_nodes_nxc(self.oar_job_id, self.args.site, compose_info_file=nxc_build_file, roles_quantities=roles)
        compute_hosts = [ node_hostnames[i].address for i in range(1, len(node_hostnames)) ]
        self.plan = experiment_plan_generator(self.args.experiment_file)
        write_nodefile(compute_hosts)
        print("Nodes : ", self.nodes)

    def start_colmet(self, collector_parameters, parameters):
        """Starts colmet node agent on all the compute nodes with the specified parameters and the collector on the corresponding host"""
        command_node = "colmet-node --zeromq-uri tcp://{}:5556 {}".format(self.nodes["collector"], parameters)
        command_collector = "colmet-collector"

        self.colmet_nodes = Remote(command_node, self.nodes["compute"], connection_params={"user" : "root"}).start()
        self.collector = SshProcess(command_collector, self.nodes["collector"], connection_params={'user' : 'root'}).start()
        self.colmet_launched=True

    def kill_colmet(self):
        """Killing colmet node agent on all the compute nodes"""
        # We assign to nothing to suppress outputs
        _ = self.colmet_nodes.kill()
        #_ = self.collector.kill()
        _ = self.colmet_nodes.wait()
        #_ = self.collector.wait()
        self.colmet_launched = False

    def update_colmet(self, new_sampling_period, new_metrics):
        self.kill_colmet()
        colmet_args=" --enable-perfhw -s {} -m {}".format(new_sampling_period, new_metrics)
        collector_args=""
        self.start_colmet(collector_args, colmet_args)

    def parse_params(self, parameters):
        p=parameters.split(";")
        self.params={}
        self.params['metrics']=p[1]
        self.params['sampling_period']=p[2]

    def run(self):
        colmet_args=" --enable-perfhw"
        self.start_colmet("", colmet_args)
        self.uniform_parameters = {
                'bench_name':self.args.name_bench,
                'bench_class':self.args.class_bench,
                'bench_type':self.args.type_bench,
                'nb_nodes':self.args.number_nodes
                }
        f = open("expe_result", "w")
        f.write("repetition;sampling;metrics;time\n")
        while self.plan.get_nb_remaining() > 0:
            print("Remaining : "+str(self.plan.get_percentage_remaining())+"%")
            f.write(self.do_repetition(self.plan.get_next_config()))
        f.close()


    def do_repetition(self, parameters):
        """Execute the bench for a given combination of parameters."""
        self.parse_params(parameters)
        bench_bin_path = "~/.nix-profile/bin/"
        mpi_executable_name = bench_bin_path + self.uniform_parameters['bench_name'] + "." + self.uniform_parameters['bench_class'] + "." + self.uniform_parameters['bench_type']

        self.update_colmet(self.params['sampling_period'], self.params['metrics'])
        
        bench_command = "mpirun -machinefile {}/nodefile -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib ".format(os.getcwd()) + mpi_executable_name
    
        p = SshProcess(bench_command, self.nodes['compute'][0]).run(timeout=self.args.time_experiment)
        p.wait()
        return parameters+";"+parse_output(p.stdout)+"\n"

if __name__ == "__main__":
    bench = Colmet_bench()
    try:
        bench.start()
        oardel([(bench.oar_job_id, None)])
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)
        oardel([(bench.oar_job_id, None)])
