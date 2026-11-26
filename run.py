import argparse

from proxyproof.scheduler import Scheduler

parser = argparse.ArgumentParser(description='ProxyProof')
parser.add_argument('--processor', type=str, help='processor to run')
args = parser.parse_args()

if __name__ == '__main__':
    # if processor set, just run it
    if args.processor:
        getattr(Scheduler(), f'run_{args.processor}')()
    else:
        Scheduler().run()
