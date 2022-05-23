from execo import *
from execo_g5k import *
from execo_engine import Engine
from arg_parser import ArgsParser
from experiment_plan import experiment_plan_generator
import logging
import time
import os
import threading
username=""
starttime=0

def install_nix(hosts):
    logger.debug("== Installing Nix == \n")
    p = Remote("sudo-g5k su root -c 'echo 1 > /proc/sys/kernel/unprivileged_userns_clone' && curl -L https://nixos.org/nix/install | sh", hosts).start()
    p.wait()

    for k in p.processes:
        logger.debug(k.stdout)
    print("Nix installed : -- %s seconds --" % (time.time()-starttime))

def import_nix_store(hosts, closure):
    logger.debug("== Importing Nix store == \n")
    p = Remote("cat {} | bunzip2 | ~/.nix-profile/bin/nix-store --import".format(closure), hosts).start()
    p.wait()
    for k in p.processes:
        logger.debug(k.stdout)
    print("Nix store imported : -- %s seconds --" % (time.time()-starttime))

def install_open_mpi(hosts):
    logger.debug("== Installing OpenMPI == \n")
    command = "~/.nix-profile/bin/nix-env -i openmpi"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logger.debug(k.stdout)
    print("MPI installed : -- %s seconds --" % (time.time()-starttime))

def install_npb(hosts):
    logger.debug("== Installing NAS Parallel Benchmarks == \n")
    #TODO : check if the user has kapack in his home directory
    command = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA npb -I ~/.nix-defexpr/channels/"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logger.debug(k.stdout)
    print("NPB installed : -- %s seconds --" % (time.time()-starttime))

def install_colmet(collector_host, hosts):
    logger.debug("== Installing Colmet(Rust version) == \n")
    #TODO : check if the user has kapack in his home directory
    #command_node = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet-rs -I ~/.nix-defexpr/channels/"
    #command_collector = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet-collector -I ~/.nix-defexpr/channels"
    #p = Remote(command_node, hosts).start()
    #c = SshProcess(command_collector, collector_host).run()
    #p.wait()
    c = Remote("~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet -I ~/.nix-defexpr/channels/", list(hosts, collector_host)).start()
    c.wait()
    logger.debug(c.stdout)
    #for k in p.processes:
    #    logger.debug(k.stdout)
    print("Colmet installed : -- %s seconds --" % (time.time()-starttime))

def parse_output(s):
    lines=s.splitlines()
    out=""
    for l in lines:
        if l.startswith(" Time in seconds"):
            sp=l.split(" ")
            out=sp[-1]
    return out

def format_walltime(nb_mins):
    return "{}:{}:0".format(int(nb_mins/60), nb_mins%60)

class Colmet_bench(Engine):
    """
    
    """
    def __init__(self):
        self.colmet_launched=False

    def start_colmet(self, collector_parameters, parameters):
        logger.debug("Start colmet node agent on all the compute nodes with the specified parameters and the collector on the corresponding host")
        command_node = ".nix-profile/bin/colmet-node --zeromq-uri tcp://{}:5556 {}".format(self.collector_hostname, parameters)
        #command_collector = "~/.nix-profile/bin/colmet-collector"
        command_collector = "~/.nix-profile/bin/colmet-collector {}".format(collector_parameters)

        self.colmet_nodes = Remote(command_node, self.hostnames).start()
        self.collector = SshProcess(command_collector, self.collector_hostname).start()
        self.colmet_launched=True

    def kill_colmet(self):
        logger.debug("Killing colmet node agent on all the compute nodes")
        # We assign to nothing to suppress outputs
        _ = self.colmet_nodes.kill()
        _ = self.collector.kill()
        _ = self.colmet_nodes.wait()
        _ = self.collector.wait()
        #a = input("Vous avez commis des crimes contre Bordeciel et ses habitants. Payez l'ammende ou allez en prison.")
        self.colmet_launched = False

    def update_hostnames(self, nb_nodes):
        restart_colmet=False
        if nb_nodes != len(self.hostnames):
            restart_colmet=True
        self.hostnames=list()
        hf=open("nodefile","w")
        for i in range(0, nb_nodes):
            self.hostnames.append(self.initial_hostnames[i])
            for _ in range(0, int(get_host_attributes(self.initial_hostnames[i])['architecture']['nb_cores'])):
                hf.write(self.initial_hostnames[i]+"\n")
        hf.close()
        return restart_colmet

    def update_colmet(self, new_sampling_period, new_metrics):
        command_update = "python ~/colmet-rs/configure.py {} {}".format(new_sampling_period, new_metrics)
        u = Remote(command_update, self.hostnames).run()

    def prepare_bench(self, args, walltime):
        """Request a job to g5k and set up the nodes to execute the benchmark"""

        #Requests a job
        self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_nodes), walltime=walltime, additional_options="-O /dev/null -E /dev/null"), args.site)])
        self.job=self.jobs[0]
        job_id, site = self.job
        wait_oar_job_start(job_id)
        # After job is started, recover hostnames
        print("job started : -- %s seconds --" % (time.time()-starttime))
        nodes = get_oar_job_nodes(job_id, site)
        self.initial_hostnames=list()
        self.hostnames=list()
        self.collector_hostname=nodes[0].address
        for i in range(1, len(nodes)):
            self.initial_hostnames.append(nodes[i].address)
        self.initial_nb_hostnames = len(self.initial_hostnames)
        
        # Install the required softwares on the corresponding nodes
        install_nix(nodes)
        if args.store!=None:
            import_nix_store(nodes, args.store)
        #install_open_mpi(self.hostnames)
        install_npb(self.initial_hostnames)
        install_colmet(self.collector_hostname, self.initial_hostnames)
        self.update_hostnames(args.number_nodes-1)
        #colmet_args=" --enable-perfhw"
        #self.start_colmet("", colmet_args)

    def clean_bench(self):
        oardel(self.jobs)
        self.job=None
        self.collector_hostname=None
        self.initial_hostnames=list()
        self.hostnames=list()
        self.params={}
    
    def parse_params(self, parameters):
        p=parameters.split(";")
        self.params={}
        self.params['metrics']=p[1]
        self.params['sampling_period']=p[2]
        self.params['mpi_root_host']=self.hostnames[0]

    def run_xp(self, uniform_parameters, parameters):
        """Execute the bench for a given combination of parameters."""
        self.parse_params(parameters)
        #print(str(self.colmet_launched) + " : "+parameters)
        bench_bin_path = "~/.nix-profile/bin/"
        mpi_executable_name = bench_bin_path + uniform_parameters['bench_name'] + "." + uniform_parameters['bench_class'] + "." + uniform_parameters['bench_type']

        #self.update_colmet(self.params['sampling_period'], self.params['metrics'])
        if self.colmet_launched == True:
            self.kill_colmet()
        self.start_colmet("--enable-stdout-backend -s {}".format(self.params['sampling_period']), "-s {}".format(self.params['sampling_period'])) 

        bench_command = "mpirun -machinefile {}/nodefile -mca mtl psm2 -mca pml ^ucx,ofi -mca btl ^ofi,openib ".format(os.getcwd()) + mpi_executable_name
    
        p = SshProcess(bench_command, self.params['mpi_root_host']).run(timeout=250)
        p.wait()
        return parameters+";"+parse_output(p.stdout)+"\n"

if __name__ == "__main__":
    starttime=time.time()
    approx_time_expe_mins=1
    args = ArgsParser.get_args()
    plan=experiment_plan_generator("expe_4.yml")
    #args.number_nodes=plan.get_max_nb_nodes()+1
    args.number_nodes=5
    logger.setLevel(40 - args.verbosity * 10)
    filename="expe_4_benchmark"
    uniform_parameters={
            'bench_name': args.name_bench, 
            'bench_class': args.class_bench, 
            'bench_type': args.type_bench,
            'nb_nodes': args.number_nodes-1
    }
    f = open(filename, "w")
    f.write("uniform parameters :") 
    f.write(" ".join(list(str(uniform_parameters.values())))+"\n")
    f.write("repetition;metrics;sampling_period;time")
    bench = Colmet_bench()
    bench.prepare_bench(args, format_walltime(plan.get_nb_remaining()*approx_time_expe_mins))
    
    while plan.get_nb_remaining() > 0:
        print("Remaining : "+str(plan.get_percentage_remaining())+"%")
        out=bench.run_xp(uniform_parameters, plan.get_next_config())
        f.write(out)
    f.close()
    bench.clean_bench()
