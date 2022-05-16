from execo import *
from execo_g5k import *
from execo_engine import Engine
from arg_parser import ArgsParser
import logging
import time
import os
username=""
starttime=0

def install_nix(hosts):
    logging.debug("== Installing Nix == \n")
    p = Remote("sudo-g5k su root -c 'echo 1 > /proc/sys/kernel/unprivileged_userns_clone' && curl -L https://nixos.org/nix/install | sh", hosts).start()
    p.wait()

    for k in p.processes:
        logging.debug(k.stdout)
    print("Nix installed : -- %s seconds --" % (time.time()-starttime))

def import_nix_store(hosts, closure):
    logging.debug("== Importing Nix store == \n")
    p = Remote("cat {} | bunzip2 | ~/.nix-profile/bin/nix-store --import".format(closure), hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)
    print("Nix store imported : -- %s seconds --" % (time.time()-starttime))

"""
def install_softwares(hosts, store):
    if store != None:
        command = "bash {}/install_commands.sh -s {}".format(os.getcwd(), store)
    else:
        command = "bash {}/install_commands.sh".format(os.getcwd()) 
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)

"""
def install_open_mpi(hosts):
    logging.debug("== Installing OpenMPI == \n")
    command = "~/.nix-profile/bin/nix-env -i openmpi"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)
    print("MPI installed : -- %s seconds --" % (time.time()-starttime))

def install_npb(hosts):
    logging.debug("== Installing NAS Parallel Benchmarks == \n")
    #TODO : check if the user has kapack in his home directory
    command = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA npb -I ~/.nix-defexpr/channels/"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)
    print("NPB installed : -- %s seconds --" % (time.time()-starttime))

def install_colmet(hosts):
    logging.debug("== Installing Colmet(Rust version) == \n")
    #TODO : check if the user has kapack in his home directory
    command = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA colmet-rs -I ~/.nix-defexpr/channels/"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)
    print("Colmet installed : -- %s seconds --" % (time.time()-starttime))

def start_colmet(hosts, parameters):
    logging.debug("Start colmet node agent on all the compute nodes with the specified parameters")
    command = ".nix-profile/bin/colmet-node &"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)


def kill_colmet(hosts):
    logging.debug("Killing colmet node agent on all the compute nodes")
    command = "killall colmet-node"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        logging.debug(k.stdout)

def parse_output(s):
    lines=s.splitlines()
    out=""
    for l in lines:
        if l.startswith(" Time in seconds"):
            sp=l.split(" ")
            out=sp[-1]
    return out

class Colmet_bench(Engine):
    """
    
    """
    def __init__(self):
        pass

    def prepare_bench(self, args):
        """Request a job to g5k and set up the nodes to execute the benchmark"""
        self.jobs = oarsub([(OarSubmission(resources="cluster=1/nodes={}".format(args.number_nodes), walltime="2:0:0", additional_options="-O /dev/null -E /dev/null"), args.site)])
        self.job=self.jobs[0]
        job_id, site = self.job
        wait_oar_job_start(job_id)
        print("job started : -- %s seconds --" % (time.time()-starttime))
        nodes = get_oar_job_nodes(job_id, site)
        self.hostnames=list()
        self.collector_hostname=nodes[0]
        for i in range(1, len(nodes)):
            self.hostnames.append(nodes[i].address)
        print("lists made : -- %s seconds --" % (time.time()-starttime))
        #install_softwares(self.hostnames, args.store)
        install_nix(self.hostnames)
        if args.store!=None:
            import_nix_store(self.hostnames, args.store)
        install_open_mpi(self.hostnames)
        install_npb(self.hostnames)
        install_colmet(self.hostnames)
        print("software installed : -- %s seconds --" % (time.time()-starttime))

    def clean_bench(self):
        oardel(self.jobs)
        self.job=None
        self.collector_hostname=None
        self.hostnames=list()
        self.params={}
    
    def parse_params(self, parameters):
        p=parameters.split(";")
        self.params={}
        self.params['username']=p[0]
        self.params['bench_name']=p[1]
        self.params['bench_class']=p[2]
        self.params['bench_type']=p[3]
        self.params['bench_nb_repeat']=int(p[4])
        self.params['colmet_on_off']=p[5]
        self.params['mpi_root_host']=self.hostnames[0]

    def run_xp(self, parameters):
        """Execute the bench for a given combination of parameters."""
        self.parse_params(parameters)
        bench_bin_path = "/home/{user}/.nix-profile/bin/".format(user=self.params['username'])
        mpi_executable_name = bench_bin_path + self.params['bench_name'] + "." + self.params['bench_class'] + "." + self.params['bench_type']
        out=""
        if self.params['colmet_on_off'] == 'on':
            start_colmet(self.hostnames, ())
        for bench_nb in range(self.params['bench_nb_repeat']):
            #bench_command = "mpirun  --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' ".format(nodefile=self.hostnames) + mpi_executable_name
            bench_command = "mpirun  " + mpi_executable_name
    
            p = SshProcess(bench_command, self.params['mpi_root_host']).run(timeout=250)
            p.wait()
            out+=parameters+";"+parse_output(p.stdout)+"\n"
        return out

if __name__ == "__main__":
    starttime=time.time()
    args = ArgsParser.get_args()
    username=os.getlogin()
    logging.basicConfig(
            format = '%(asctime)s - %(levelname)s - %(message)s',
            datefmt = '%d/%m/%Y %H:%M:%S',
            level = 40 - args.verbosity * 10)
    filename="test_benchmark"
    f = open(filename, "w")

    bench = Colmet_bench()
    bench.prepare_bench(args)
    #out=bench.run_xp("imeignanmasson;lu;C;mpi;5;off")
    #f.write(out)
    #out=bench.run_xp("imeignanmasson;lu;C;mpi;5;on")
    #f.write(out)
    #f.close()
    #bench.clean_bench()
