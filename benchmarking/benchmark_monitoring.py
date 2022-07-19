from execo import *
from execo_g5k import *
from execo_engine import Engine
from arg_parser import ArgsParser
from experiment_plan import experiment_plan_generator
import logging
import time
import os
import threading
from tqdm import tqdm
username=""
starttime=0
monitoring_soft=""

def install_nix(hosts):
    p = Remote("sudo-g5k su root -c 'echo 1 > /proc/sys/kernel/unprivileged_userns_clone' && curl -L https://nixos.org/nix/install | sh", hosts).run()
    print("Nix installed : -- %s seconds --" % (time.time()-starttime))

def install_npb(hosts):
    #TODO : check if the user has kapack in his home directory
    p = Remote("~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA npb -I ~/.nix-defexpr/channels/", hosts).run()
    print("NPB installed : -- %s seconds --" % (time.time()-starttime))

def install_monitoring_software(collector_host, hosts):
    #TODO : check if the user has kapack in his home directory
    if monitoring_soft == "Colmet Rust":
        command_node = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet-rs -I ~/.nix-defexpr/channels/"
        command_collector = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet-collector -I ~/.nix-defexpr/channels"
        p = Remote(command_node, hosts).start()
        c = SshProcess(command_collector, collector_host).run()
        p.wait()

    if monitoring_soft == "Colmet Python":
        _ = Remote("~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet -I ~/.nix-defexpr/channels/", hosts).run()

    if monitoring_soft == "Likwid":
        _ = Remote("~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA likwid -I ~/.nix-defexpr/channels/ && echo -1 | sudo-g5k tee /proc/sys/kernel/perf_event_paranoid", hosts).run()
    print("Colmet installed : -- %s seconds --" % (time.time()-starttime))

def parse_output(s):
    lines=s.splitlines()
    out=""
    for l in lines:
        if l.startswith(" Time in seconds"):
            sp=l.split(" ")
            out+=sp[-1]
        elif l.startswith(" Mop/s total"):
            sp=l.split(" ")
            out+=","+sp[-1]
    return out

def format_walltime(nb_mins):
    return "{}:{}:0".format(int(nb_mins/60), nb_mins%60)

class Colmet_bench(Engine):
    """
    
    """
    def __init__(self):
        self.colmet_launched=False

    def write_nodefile(self):
        hf=open("nodefile","w")
        for a in self.hostnames:
            for _ in range(0, int(get_host_attributes(a)['architecture']['nb_cores'])):
                hf.write(a+"\n")
        hf.close()

    def kill_colmet(self, monitoring_soft):
        logger.debug("Killing colmet node agent on all the compute nodes")
        # We assign to nothing to suppress outputs
        _ = self.colmet_nodes.kill()
        if monitoring_soft != "Likwid":
            if monitoring_soft == "Colmet Python":
                _ = SshProcess("killall .python-collect", self.collector_hostname).run()
            else:
                _ = self.collector.kill()
                _ = self.collector.wait()
        _ = self.colmet_nodes.wait()
        self.colmet_launched = False


    def update_colmet(self, parameters):
        if self.colmet_launched :
            self.kill_colmet(parameters['monitoring_soft'])
        if parameters['monitoring_soft'] != "Without":
            if (parameters['monitoring_soft'] == "Colmet Rust"):
                node_command = "~/.nix-profile/bin/colmet-node --enable-perfhw true -s {} -m {} --zeromq-uri tcp://{}:5556".format(parameters["sampling_period"], parameters["metrics"], self.collector_hostname)
                collector_command = "~/.nix-profile/bin/colmet-collector"
            elif parameters['monitoring_soft'] == "Colmet Python":
                node_command = "sudo-g5k /home/imeignanmasson/.nix-profile/bin/python-node -s {} --zeromq-uri tcp://{}:5556".format(parameters["sampling_period"], self.collector_hostname)
                collector_command = "~/.nix-profile/bin/python-collector -s {} --enable-stdout-backend".format(parameters["sampling_period"])
            elif parameters['monitoring_soft'] == "Likwid":
                node_command = "~/.nix-profile/bin/likwid-perfctr -g FLOPS_DP -t {}ms".format(parameters["sampling_period"])
                collector_command = ""
            self.colmet_nodes = Remote(node_command, self.hostnames).start()
            if parameters['monitoring_soft'] != "Likwid":
                self.collector = SshProcess(collector_command, self.collector_hostname).start()
            self.colmet_launched = True

    def prepare_bench(self, args, walltime):
        """Request a job to g5k and set up the nodes to execute the benchmark"""

        #Requests a job
        if(args.reservation_date is None):
            if(args.monitoring_soft == "Without" or args.monitoring_soft == "Likwid"):
                self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_compute_nodes), walltime=walltime, additional_options="-O /dev/null -E /dev/null"), args.site)])
            else:
                self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_compute_nodes+1), walltime=walltime, additional_options="-O /dev/null -E /dev/null"), args.site)])
        else:
            if(args.monitoring_soft == "Without" or args.monitoring_soft == "Likwid"):
                self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_compute_nodes), walltime=walltime, reservation_date=args.reservation_date, additional_options="-O /dev/null -E /dev/null"), args.site)])
            else:
                self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_compute_nodes+1), walltime=walltime, reservation_date=args.reservation_date, additional_options="-O /dev/null -E /dev/null"), args.site)])
        self.job=self.jobs[0]
        job_id, site = self.job
        wait_oar_job_start(job_id)
        # After job is started, recover hostnames
        print("job started : -- %s seconds --" % (time.time()-starttime))
        nodes = get_oar_job_nodes(job_id, site)
        self.hostnames=list()
        if(args.monitoring_soft == "Without" or args.monitoring_soft == "Likwid"):
            for i in range(0, len(nodes)):
                self.hostnames.append(nodes[i].address)
            self.write_nodefile()
        else:
            self.collector_hostname=nodes[0].address
            for i in range(1, len(nodes)):
                self.hostnames.append(nodes[i].address)
            self.write_nodefile()
            print(self.collector_hostname)
        print(self.hostnames)
        
        # Install the required softwares on the corresponding nodes
        install_nix(nodes)
        install_npb(self.hostnames)
        if monitoring_soft == "Colmet Rust":
            install_monitoring_software(self.collector_hostname, self.hostnames)
        if monitoring_soft == "Colmet Python":
            install_monitoring_software("", nodes)
        if monitoring_soft == "Likwid":
            install_monitoring_software("", nodes)
        
    def run_xp(self, uniform_parameters, parameters):
        """Execute the bench for a given combination of parameters."""
        bench_bin_path = "~/.nix-profile/bin/"
        executable_name = bench_bin_path + uniform_parameters['bench_name'] + "." + uniform_parameters['bench_class'] + "." + uniform_parameters['bench_type']

        self.update_colmet(parameters)

        if uniform_parameters['bench_type'] == "mpi":
            bench_command = "mpirun -machinefile {}/nodefile -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib ".format(os.getcwd()) + executable_name
        elif uniform_parameters['bench_type'] == "omp":
            bench_command = executable_name
    
        p = SshProcess(bench_command, self.hostnames[0]).run(timeout=300)
        p.wait()
        return "{repetitions},{monitoring_soft},{sampling_period},\"{metrics}\"".format(**parameters)+","+parse_output(p.stdout)

if __name__ == "__main__":
    starttime=time.time()
    approx_time_setup=20
    args = ArgsParser.get_args()
    approx_time_expe_mins=int(args.time_expe)
    plan=experiment_plan_generator(args.expe_file)
    monitoring_soft=plan.monitoring_soft[0]
    filename="{}_{}_{}_{}_{}.csv".format(args.output_file, monitoring_soft.replace(" ", "_"), args.number_compute_nodes, args.name_bench, args.class_bench)
    f = open(filename, "w")
    f.write("repetitions,monitoring_software,sampling_period,metrics,time,Mops,nb_nodes\n")
    logger.setLevel(40 - args.verbosity * 10)
    uniform_parameters={
            'bench_name': args.name_bench, 
            'bench_class': args.class_bench, 
            'bench_type': args.type_bench,
            'nb_nodes': args.number_compute_nodes
    }
    bench = Colmet_bench()
    bench.prepare_bench(args, format_walltime(approx_time_setup + plan.get_nb_remaining() * approx_time_expe_mins))
    #a=input("Stop") 
    for i in tqdm(range(plan.get_nb_total()), desc="Progress"):
        #print("Remaining : "+str(plan.get_percentage_remaining())+"%")
        out=bench.run_xp(uniform_parameters, plan.get_next_config())+",{}\n".format(args.number_compute_nodes)
        f.write(out)
    f.close()
    oardel(bench.jobs)
