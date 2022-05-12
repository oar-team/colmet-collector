from execo import *
from execo_g5k import *
from execo_engine import *
from .arg_parser import ArgsParser

def install_nix(hosts):
    log.debug("== Installing Nix == \n")
    p = Remote("sudo-g5k su root -c 'echo 1 > /proc/sys/kernel/unprivileged_userns_clone' && curl -L https://nixos.org/nix/install | sh", hosts).start()
    p.wait()

    for k in p.processes:
        log.debug(k.stdout)

def import_nix_store(hosts, closure):
    log.debug("== Importing Nix store == \n")
    p = Remote("cat {} | bunzip2 | ~/.nix-profile/bin/nix-store --import".format(closure), hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)

def install_colmet(hosts):
    log.debug("== Installing Colmet (node and collector) == \n")
    
    p = Remote("sudo-g5k pip install /home/{user}/colmet".format(user=username), hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)


def install_open_mpi(hosts):
    log.debug("== Installing OpenMPI == \n")
    command = "~/.nix-profile/bin/nix-env -i openmpi"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)


def install_npb(hosts):
    log.debug("== Installing NAS Parallel Benchmarks == \n")
    #TODO : check if the user has kapack in his home directory
    command = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA npb -I ~/.nix-defexpr/channels/"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)

class Colmet_bench(Engine):
    """
    
    """
    def __init__(self):
        pass

    def prepare_bench(self, args):
        """Request a job to g5k and set up the nodes to execute the benchmark"""
        jobs = oarsub([(OarSubmission("cluster=1/nodes={}".format(args.number_nodes), walltime=args.walltime), args.site)])
        this.job=jobs[0]
        wait_oar_job_start(this.job)
        job_id, site = this.job
        this.nodes = get_oar_job_nodes(job_id, site)
        if(args.store != None)
            import_nix_store(args.store)
        else
            install_nix()
            install_open_mpi()
            # install_colmet()
            install_npb()

    def clean_bench(self):
        oardel(this.job)
    
    def parse_params(self, parameters):
        p=parameters.split(";")
        this.params={}
        this.params['username']=p[0]
        this.params['bench_name']=p[1]
        this.params['bench_class']=p[2]
        this.params['bench_type']=p[3]
        this.params['bench_nb_repeat']=p[4]

    def run_xp(self, parameters):
        """Execute the bench for a given combination of parameters."""
        this.parse_params(parameters)
        bench_bin_path = "/home/{user}/.nix-profile/bin/".format(user=this.params['username'])
        mpi_executable_name = bench_bin_path + this.params['bench_name'] + "." + this.params['bench_class'] + "." + this.params['bench_type']
        out=""
        for bench_nb in range(this.params['bench_nb_repeat']):
            bench_command = "mpirun -machinefile {nodefile} --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' ".format(nodefile=this.nodes) + mpi_executable_name
    
            p = SshProcess(bench_command, this.params['mpi_root_host']).run(timeout=250)
            p.wait()
            out+=p.stdout+"\n"
        return out

if __name__ == "__main__":
    args = ArgsParser.get_args()
    logging.basicConfig(
            format = '%(asctime)s - %(levelname)s - %(message)s',
            datefmt = '%d/%m/%Y %H:%M:%S',
            level = 40 - args.verbosity * 10)
            )

        
    bench = Colmet_bench()
    bench.prepare_bench(args)
    bench.run_xp("imeignanmasson;lu;B;mpi;3")
