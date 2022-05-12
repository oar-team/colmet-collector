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

        group.add_argument('-t', '--type-bench', dest='type_bench', default=mpi,
                            help='Type of benchmark (OpenMP or MPI)')

        group = parser.add_argument_group('Program to benchmark')
        
        group.add_argument('-t', '--type-bench', dest='type_bench', default=mpi,
                            help='Type of benchmark (OpenMP or MPI)')
        
        group.add_argument('-name', '--name-bench', dest='name_bench', default=lu,
                            help='Name of benchmark (lu, ft, etc...)')
        group.add_argument('-c', '--class-bench', dest='class_bench', default=B, 
                            help='Class of benchmark (B, C or D are the most likely)')

        parser.add_argument_group(group)

        group = parser.add_argument_group('Benchmark settings')

        group.add_argument('-n', '--number-nodes', type=int, dest='number_nodes', 
                default=2, help="Number of nodes to consider for the benchmark'")

        group.add_argument('-r', '--repetitions-exerience', type=int, dest='repetitions',
                default=10, help="Number of time to run each benchmark'")

        group.add_argument('-w', '--walltime', type=int, dest='walltime', default='60', help='Walltime given to a complete job. WARNING : the time allocated to one repetition will be walltime/nb_repetitions')

        group.add_argument('-s', '--site', dest='site', default='grenoble', help='Site to request nodes')

        group.add_argument('--store', dest='store', default=None, help='Nix store with OpenMPI, NPB and Colmet already installed. Speeds up the building process')
       
        parser.add_argument_group(group)

        args = parser.parse_args()
        return args
