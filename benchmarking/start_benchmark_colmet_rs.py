# Original version of this program was implemented by Lambert Rocher.

from execo import *
from execo_g5k import *
from urllib3.exceptions import InsecureRequestWarning
import sys
import requests
import json
import os.path
import os
import datetime
import logging
import subprocess

site = "grenoble"
username = "imeignanmasson"
log = logging.getLogger(__name__)
nodefile=os.environ['OAR_NODE_FILE']
nodefile_call = subprocess.run(["cat", nodefile], stdout=subprocess.PIPE, text=True)
nodefile=nodefile_call.stdout
nodes=nodefile.splitlines()
hosts=list(set(nodes))
print(hosts)


class Oarapi:
    """
    Class to access informations from the oarapi.
    Note that the class only questions one site for the moment.
    For multi site experiment, you can either ask me to adapt it, or to create one api for each site.
    The official documentation can be found at this link: http://oar.imag.fr/docs/latest/user/api.html
    """

    def __init__(self, baseurl, session=None, extension="json"):
        self.base_url = baseurl
        self.template_command = baseurl + "/{request}." + extension
        self.user = None

        if session is None:
            self.session = requests.Session()
        else:
            self.session = session

    def _do_get_request(self, request, payload={}):
        """
        Internal method that performs a get request
        and return its results in case of success or raise
        the occured error.

        Keyword arguments:
            request: the path (as string) of the request. Example https://myapp/resource
            payload: a dict containing the paramenters to send with the request.

        Returns:
            return the request on sucess. Otherwise raise an error.
        """

        resp = self.session.get(request, params=payload)

        if resp.status_code != 200:
            raise NameError(resp.text)
        else:
            return resp

    def get_user(self, save_user=True, force_refresh=False):
        """
        Get the current connected user name.
        If this executed from g5k, this should work out of the box.

        This function has the side effect to save the username
        internaly to authenticate future requests.

        When executed many times, the function does not re-send
        the request but the saved user name. To force the request
        set the parameter `force_refresh` to True.

        `oarapi.get_user(force_refresh=True)`
        """

        if self.user is not None and not force_refresh:
            return self.user

        resp = self._do_get_request(self.template_command.format(request="whoami"))
        if resp.status_code != 200:
            raise NameError(resp.text)
        else:
            user = resp.json()["authenticated_user"]
            if save_user:
                self.user = user
            return user

    def get_jobs(self, user=None, with_details=False):
        """
        Execute the request `/jobs/[details]`.
        If an username is given it is forwarded as a paramenter to the request.
        Returns:
            A list of jobs (as Json).
        """

        payload = {}
        request = "jobs"

        if user is not None:
            payload = {'user': user}

        if with_details:
            request += "/details"

        resp = self._do_get_request(self.template_command.format(request=request), payload=payload)

        return resp.json()["items"]

    def get_job(self, jobid, with_details=False):
        """
        Get the job given as id.
        Mirror for: `jobs/{id}/[details]`
        """
        payload = {}
        request = "jobs/{jobid}".format(jobid=jobid)

        if with_details:
            request += "/details"

        resp = self._do_get_request(self.template_command.format(request=request))
        return resp.json()

    def get_job_details(self, jobid):
        """
        Shortcut for `get_job(id, with_details=True)
        """

        return self.get_job(jobid, with_details=True)

    def get_job_nodes(self, jobid):
        """
        Get the node for a given job.
        Mirror for: jobs/{jobid}/nodes
        """

        payload = {}
        request = "jobs/{jobid}/nodes".format(jobid=jobid)

        resp = self._do_get_request(self.template_command.format(request=request))
        return resp.json()["items"]

    def get_job_resources(self, jobid):
        """
        Get the resources for a given job.
        Mirror for: jobs/{jobid}/resources
        """
        payload = {}
        request = "jobs/{jobid}/resources".format(jobid=jobid)

        resp = self._do_get_request(self.template_command.format(request=request))
        return resp.json()["items"]


def install_nix():
    print("== Installing Nix == \n")
    # We install nix on each nodes
    # https://unix.stackexchange.com/a/495523
    # Activate user namespace in debian
    # https://superuser.com/questions/1094597/enable-user-namespaces-in-debian-kernel
    p = Remote("sudo-g5k su root -c 'echo 1 > /proc/sys/kernel/unprivileged_userns_clone'", hosts).start()
    p.wait()

    # We install nix on each nodes
    p = Remote("curl -L https://nixos.org/nix/install | sh", hosts).start()
    p.wait()

    # Print output
    for k in p.processes:
        log.debug(k.stdout)


def import_nix_store():
    print("== Importing my Nix store == \n")
    closure = "my_store.bz"
    p = Remote("cat {} | bunzip2 | ~/.nix-profile/bin/nix-store --import".format(closure), hosts).start()
    p.wait()
    for k in p.processes:
        print(k.stdout)

def install_colmet():
    print("== Installing Colmet (node and collector) == \n")
    
    p = Remote("sudo-g5k pip install /home/{user}/colmet".format(user=username), hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)


def install_open_mpi():
    print("== Installing OpenMPI == \n")
    command = "~/.nix-profile/bin/nix-env -i openmpi"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)


def install_npb():
    print("== Installing NAS Parallel Benchmarks == \n")
    #TODO : check if the user has kapack in his home directory
    command = "~/.nix-profile/bin/nix-env -f ~/nur-kapack -iA npb -I ~/.nix-defexpr/channels/"
    p = Remote(command, hosts).start()
    p.wait()
    for k in p.processes:
        log.debug(k.stdout)


def restart_colmet(sampling_period):
    kill_colmet()

    print(" Restarting colmet with sampling perdiod = {sampling_period} sec ".format(sampling_period=sampling_period))

    colmet_collector_nodes = [hosts.copy()[0]]
    colmet_nodes_nodes = hosts.copy()[1:]

    print("colmet-collector running on :", colmet_collector_nodes)
    print("colmet-node running on :", colmet_nodes_nodes)

    port = 5665
    timestamp = datetime.datetime.now().timestamp()

    # The path where to store the data
    # Be carreful, the directory must be accessible by anybody, a quick workaround is to do an evil+777 chmod.
    hdf5_file = os.path.join("data_hdf5", "{job_id}_{timestamp}_{sampling}sec.hdf5".format(
        job_id=str(job["id"]),
        timestamp=str(timestamp),
        sampling=str(sampling_period)))

    collector_uri = "tcp://{address}:{port}".format(address="*", port=port)
    node_uri = "tcp://{address}:{port}".format(address=colmet_collector_nodes[0], port=port)

    collector_path = "python3 /usr/local/lib/python3.5/dist-packages/colmet/collector/main.py".format(user=username)
    node_path = "python3 /usr/local/lib/python3.5/dist-packages/colmet/node/main.py".format(user=username)

    collector_options = "-s " + str(sampling_period)
    collector_options += " --zeromq-bind-uri " + collector_uri
    collector_options += " --hdf5-filepath " + hdf5_file
#     collector_options += " --elastic-host " + "http://fgrenoble.grenoble.grid5000.fr:9200"
    # collector_options += " --enable-stdout-backend"

    node_options = "-s " + str(sampling_period)
    node_options += " --zeromq-uri " + node_uri
    node_options += " --enable-infiniband"
    node_options += " --enable-lustre"
    node_options += " --enable-perfhw"
    node_options += " --enable-RAPL"
    node_options += " -vvv"

    collector_command = "sudo-g5k -H {exe} {options}".format(exe=collector_path, options=collector_options)
    node_command = "sudo-g5k -H {exe} {options}".format(exe=node_path, options=node_options)

    print("commande colmet-collector : ", collector_command)
    print("commande colmet-node : ", node_command)

    collector_process = Remote(collector_command, colmet_collector_nodes).start()
    nodes_processes = Remote(node_command, colmet_nodes_nodes).start()

    # with collector_process.start() and nodes_processes.start():
    #     pass

    for s in nodes_processes.processes + collector_process.processes:
        pass


#         print("process : ", s)
#         print("process.stdout : ", s.stdout)
#         print("process.stderr :  ", s.stderr)

def kill_colmet():
    p = Remote("sudo-g5k killall colmet-node", hosts).start()
    p.wait()
    
    colmet_collector_nodes = [hosts.copy()[0]]
    colmet_nodes_nodes = hosts.copy()[1:]
    p = Remote("sudo killall .colmet-node-wrapped", colmet_nodes_nodes).start()
    p.wait()
    p = Remote("sudo killall .colmet-collector-wrapped", colmet_collector_nodes).start()
    p.wait()
    print("killed colmet")


def do_expe():
    bench_name = "lu"
    bench_class = "B"
    bench_type = "mpi"
    bench_bin_path = "/home/{user}/.nix-profile/bin/".format(user=username)
    mpi_executable_name = bench_bin_path + bench_name + "." + bench_class + "." + bench_type

    bench_nb_repeat = 10

    for bench_nb in range(bench_nb_repeat):
            bench_command = "mpirun -machinefile {nodefile} --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' ".format(nodefile=nodefile) + mpi_executable_name

            #print("mpi commande : ", bench_command)

            p = Process(bench_command, shell=True).run(timeout=250)
            p.wait()
            # print(p.stdout)


"""
    for sample_period in [5, 4, 3]:
        print("changing sample period to :", sample_period)

        restart_colmet(sample_period)

        bench_name = "lu"
        bench_class = "D"
        bench_nb_procs = "128"
        bench_bin_path = "/home/{user}/.nix-profile/bin/".format(user=username)
        mpi_executable_name = bench_bin_path + bench_name + "." + bench_class + "." + bench_nb_procs

        bench_nb_repeat = 10

        job = oarapi.get_jobs(user=user)[0]

        for bench_nb in range(bench_nb_repeat):
            #             bench_command = "mpirun -hostfile /tmp/hosts -map-by node --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' " + mpi_executable_name + "| sed -n -e  '/Time in seconds/p' | sed -e 's/Time in seconds = *//'"
            #             bench_command = "mpirun -hostfile /tmp/hosts -map-by node --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' " + mpi_executable_name
            bench_command = "mpirun -hostfile /tmp/hosts --map-by socket --bind-to core --mca btl openib --mca btl_openib_allow_ib 1 --mca btl_tcp_if_include ib0 --mca orte_rsh_agent 'oarsh' " + mpi_executable_name + " > /home/lrocher/mpi_out/mpi_out_{sample_period}s_{bench_nb}".format(
                sample_period=sample_period, bench_nb=bench_nb)

            print("mpi commande : ", bench_command)

            # print("executing :", bench_command)

            command = "OAR_JOB_ID={jobid} oarsh {host} {bench_command}".format(
                jobid=job["id"],
                bench_command=bench_command,
                host=hosts[0]
            )
            sleep(1)
            p = Process(command, shell=True).run(timeout=250)
     
#             p.wait()
            print(p.stdout)
            sleep(5)
        
               
            p = Remote("sudo killall mpirun", [hosts.copy()[0]]).start()
            p.wait()


#             for k in p.processes:
#                 print(k.stdout)
"""

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)

    """session = requests.Session()
    session.verify = False  # Disable ssl checking
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)  # Disable insecure requests warnings
    base_url = "http://api.grid5000.fr/stable/sites/{site}/internal/oarapi".format(
    site=site)  # Get the end point of the oarapi for this site
    oarapi = Oarapi(base_url, session=session)  # Create one instance of the Oarapi to request the site

    # We get the current user, f the notebook is launched from the frontend, you should be authenticated
    user = oarapi.get_user()"""
    user_call = subprocess.run(["whoami"], stdout=subprocess.PIPE, text=True)
    user=user_call.stdout
    print("Connected as:", user)

    """
    # Get the jobs belonging to the current user
    # and select the first one
    jobs = oarapi.get_jobs(user=user)

    hosts = []

    # Print the job list
    for job in jobs:
        print("job: ", job["id"])

    # By default pick the first job

    job = jobs[0]

    nodes = oarapi.get_job_nodes(job["id"])
    for node in nodes:
        hosts.append(node["network_address"])

    hosts.sort()
    print(hosts)

    # add hosts for mpi in /temp/hosts file
    p = Remote("echo -e " + "'" + "\n".join(hosts[1:]) + "'" + "> /tmp/hosts", hosts).start()
    p.wait()"""

    # Requesting root access
    #p = Remote("sudo-g5k", hosts).start()
    #p.wait()

    #setting up environment
    install_nix()
    #import_nix_store()
    #install_colmet()
    install_open_mpi()
    install_npb()
    #sleep(5)
    #restart_colmet(sampling_period=3)
    do_expe()
