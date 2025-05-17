import argparse
import logging
import os

from k6_driver import K6Driver

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(levelname)-6s | %(name)-40s || %(message)s',
                    datefmt='%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def get_env_name(k8s_svc_name: str) -> str:
    """
    Gets the envvar name for a k8s service by replacing - with _ and makign it all uppercase
    """
    env_name = k8s_svc_name.replace('-', '_')
    env_name = env_name.upper()
    return env_name


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to run the Wrk load generator.')

    # ======= WrkDriver Args ===========
    parser.add_argument('--k6-logdir', type=str, default="/tmp/",
                        help='Output log dir.')
    parser.add_argument('--k6-qps', type=int, default=100, help='Target QPS')
    parser.add_argument('--k6-duration', type=int, default=30,
                        help='Duration to run k6 for')
    parser.add_argument('--k6-preallocated-vus', type=int, default=30000,
                        help='Number of connections to run wrk with')
    parser.add_argument('--k6-url', type=str,
                        default="http://frontend.default.svc.cluster.local:5000",
                        help='Target URL for wrk')
    args = parser.parse_args()

    # ======== Initialize Wrk Driver =========
    os.makedirs(args.k6_logdir, exist_ok=True)
    driver = K6Driver(log_output_dir=args.k6_logdir,
                       k6_qps=args.k6_qps,
                       k6_duration=args.k6_duration,
                       k6_preallocated_VUs=args.k6_preallocated_vus,
                       k6_url=args.k6_url)

    # ======== Run Driver =========
    driver.run_loop()
