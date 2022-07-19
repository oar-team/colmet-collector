import argparse

DESCRIPTION = "Start a benchmark of Colmet and logs the time under various situation."
VERSION = "1.0"


class ArgsParser(object):

    @staticmethod
    def get_args():
        formatter = argparse.ArgumentDefaultsHelpFormatter
        parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=formatter)

        parser.add_argument('--version', action='version', version='colmet benchmark version %s' % VERSION)

        parser.add_argument('-v', '--verbose', action='count', dest="verbosity", default=1)

        group = parser.add_argument_group('Program to benchmark')
        
        group.add_argument('-t', '--type-bench', dest='type_bench', default="mpi",
                            help='Type of benchmark (OpenMP or MPI)')
        
        group.add_argument('-name', '--name-bench', dest='name_bench', default="lu",
                            help='Name of benchmark (lu, ft, etc...)')
        group.add_argument('-c', '--class-bench', dest='class_bench', default="D", 
                            help='Class of benchmark ( C, D or E are the most likely)')
        parser.add_argument('-n', '--nb_cmp_nodes', dest="number_compute_nodes", type=int, default=4)

        parser.add_argument_group(group)

        group.add_argument('-s', '--site', dest='site', default='grenoble', help='Site to request nodes')

        group.add_argument('--store', dest='store', default=None, help='Nix store with OpenMPI, NPB and Colmet already installed. Speeds up the building process')

        group.add_argument("--time_expe", dest="time_expe", default="5")
        
        group.add_argument("--monitoring_soft", dest="monitoring_soft", default="Colmet Rust")
        
        group.add_argument("--reservation_date", dest="reservation_date")

        group.add_argument('-f', "--expe-file", dest='expe_file', help="File describing the parameters of the exeperiment")

        group.add_argument('-o', '--output-file', dest="output_file", help="Path to the file where the results are written")
       
        parser.add_argument_group(group)

        args = parser.parse_args()
        return args
