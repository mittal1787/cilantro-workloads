import json
import logging
import os
import subprocess
import threading
import time
from typing import Dict, List
import traceback

from kubernetes import client, config

logger = logging.getLogger(__name__)


class K6Driver(object):
    """
    This is the driver that is called from shell and invokes wrk2 repeatedly.
    """
    K8S_NAMESPACE = 'default'
    MICROSERVICES = ['consul', 'frontend', 'geo', 'jaeger',
                     'memcached-profile', 'memcached-rate', 'memcached-reserve',
                     'mongodb-geo', 'mongodb-profile', 'mongodb-rate',
                     'mongodb-recommendation', 'mongodb-reservation',
                     'mongodb-user', 'profile', 'rate', 'recommendation',
                     'reservation', 'search', 'user']


    def k6_file(self):
        return """import http from 'k6/http';
import { check, sleep } from 'k6';

const url = """ + f"\"{self.k6_url}\"" + """;

export const options = {
    scenarios: {
        open_model: {
        executor: 'constant-arrival-rate',
        rate:""" + f"{self.k6_qps}" + f""",
        timeUnit: '1s',
        duration: '{self.k6_duration}s',
        preAllocatedVUs:{self.k6_preallocated_VUs},
        maxVUs: 5000000,
        """ + """},
    },
};

function getUser() {
  const id = Math.floor(Math.random() * 501);
  const userName = `Cornell_${id}`;
  let passWord = "";
  for (let i = 0; i < 10; i++) {
    passWord += id.toString();
  }
  return { userName, passWord };
}

function searchHotel() {
  const inDate = Math.floor(Math.random() * (24 - 9 + 1)) + 9;
  const outDate = Math.floor(Math.random() * (24 - inDate)) + inDate + 1;

  const inDateStr = inDate <= 9 ? `2015-04-0${inDate}` : `2015-04-${inDate}`;
  const outDateStr = outDate <= 9 ? `2015-04-0${outDate}` : `2015-04-${outDate}`;

  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const method = "GET";
  const path = `${url}/hotels?inDate=${inDateStr}&outDate=${outDateStr}&lat=${lat}&lon=${lon}`;

  const headers = {};
  return http.get(path)
//   return { method, path, headers };
}

function recommend() {
  const coin = Math.random();
  let reqParam = "";
  if (coin < 0.33) {
    reqParam = "dis";
  } else if (coin < 0.66) {
    reqParam = "rate";
  } else {
    reqParam = "price";
  }

  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const method = "GET";
  const path = `${url}/recommendations?require=${reqParam}&lat=${lat}&lon=${lon}`;
  const headers = {};
  return http.get(path);
//   return { method, path, headers };
}

function reserve() {
  const inDate = Math.floor(Math.random() * (23 - 9 + 1)) + 9;
  const outDate = inDate + Math.floor(Math.random() * 5) + 1;

  const inDateStr = inDate <= 9 ? `2015-04-0${inDate}` : `2015-04-${inDate}`;
  const outDateStr = outDate <= 9 ? `2015-04-0${outDate}` : `2015-04-${outDate}`;
  
  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const hotelId = Math.floor(Math.random() * 80) + 1;
  const { userName, passWord } = getUser();
  const custName = userName;

  const numRoom = "1";

//   const method = "POST";
  const path = `${url}/reservation?inDate=${inDateStr}&outDate=${outDateStr}&lat=${lat}&lon=${lon}&hotelId=${hotelId}&customerName=${custName}&username=${userName}&password=${passWord}&number=${numRoom}`;
//   const headers = {};
  return http.post(path);
}

function userLogin() {
  const { userName, passWord } = getUser();
  const method = "POST";
  const path = `${url}/user?username=${userName}&password=${passWord}`;
  const headers = {};
  http.post(path)
  return http.post(path);
}

function request() {
  const searchRatio = 0.6;
  const recommendRatio = 0.39;
  const userRatio = 0.005;
  const reserveRatio = 0.005;

  const coin = Math.random();
  if (coin < searchRatio) {
    return searchHotel();
  } else if (coin < searchRatio + recommendRatio) {
    return recommend();
  } else if (coin < searchRatio + recommendRatio + userRatio) {
    return userLogin();
  } else {
    return reserve();
  }
}
export default function() {
    const res = request()
    check(res, {
        'status is 200': (r) => r.status === 200,
    });
}


"""


    def __init__(self,
                 log_output_dir: str = None,
                 k6_qps: int = None,
                 k6_duration: int = 30,
                 k6_preallocated_VUs: int = 30000,
                 k6_url: str = 'http://frontend.default.svc.cluster.local:5000'
                 ):
        """
        :param log_output_dir: Output dir for the logs
        :param executable_path: Path to the wrk2 executable
        :param workload_script_path: Path to the workload script
        """

        self.log_output_dir = log_output_dir
        self.k6_qps = k6_qps
        self.k6_duration = k6_duration
        self.k6_preallocated_VUs = k6_preallocated_VUs
        self.k6_url = k6_url
        self.k6_filename = "hotel_reservation_k6.js"


        # Init k8s clients
        self.load_k8s_config()
        self.appsapi = client.AppsV1Api()

        # These are the number of resources allocated to all microservices
        # This is externally controlled by k8s, we just need to poll it's state.
        self.resource_allocs = self.get_alloc()
        logger.info(f"Got an initial resource allocs: {self.resource_allocs}")

        with open(self.k6_filename, "w") as f:
            f.write(self.k6_file())

        # Start thread to update resource count in background.
        resource_update_thread = threading.Thread(
            target=self.update_resource_alloc_thread, args=())
        resource_update_thread.start()

    def construct_command(self):
        command = f"k6 run {self.k6_filename} --out json={self.json_filepath} --summary-trend-stats \"min,avg,med,max,p(95),p(99),p(99.99)\""
        return command

    def load_k8s_config(self):
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logger.debug(
                'Detected running inside cluster. Using incluster auth.')
            config.load_incluster_config()
        else:
            logger.debug('Using kube auth.')
            config.load_kube_config()

    def update_resource_alloc_thread(self, sleep_time=1):
        logger.info("Running resource alloc updater thread.")
        while True:
            new_resource_alloc = self.get_alloc()
            if new_resource_alloc != self.resource_allocs:
                logger.info(
                    f"Got new resource count! Setting resources to {new_resource_alloc}")
                self.resource_allocs = new_resource_alloc
            time.sleep(sleep_time)

    def get_alloc(self) -> Dict[str, int]:
        """
        Gets the number of resources allocated to each of the microservices.
        Uses kubernetes API to get the replica count.
        :return: Dict of microservice name to number of replicas (resources).
        """
        try:
            deps = self.appsapi.list_namespaced_deployment(namespace=self.K8S_NAMESPACE)
        except Exception as e:
            logger.error("Failed to get deployment list.")
            return {}
        deps = {d.metadata.name: d for d in deps.items if
                d.metadata.name.replace('root--', '') in self.MICROSERVICES}  # Filter only deployments which are actual workloads. This is to exclude cilantro client and app client deployments.

        # Use ready replicas instead of total replicas to get actual current resource allocation
        current_allocations = {dep_name: d.status.ready_replicas for
                               dep_name, d in deps.items()}
        return current_allocations

    @staticmethod
    def average_list_of_dictionaries(list_of_dicts: List[Dict[str, int]]) -> Dict[str, int]:
        """
        Given a list of dictionaries, returns a dictionary of the average values for each key.
        :param list_of_dicts: List of dictionaries.
        :return: Dictionary of average values for each key.
        """
        avg_dict = {}
        for key in list_of_dicts[0].keys():
            avg_dict[key] = sum([d[key] for d in list_of_dicts if d[key] is not None]) / len(list_of_dicts)
        return avg_dict

    def write_output_to_disk(self,
                             avg_allocs: Dict[str, float],
                             qps: int,
                             event_start_time: float,
                             event_end_time: float,
                             wrk_stdout: str
                             ):
        """
        Writes the utility message to a log file on disk.
        The utility message is written as a json.
        :return:
        """
        # timestr = time.strftime("%Y%m%d-%H%M%S-%f")[:-3]
        # log_filename = "output_%s.log" % timestr  # This will be the final name of the log
        # log_filepath = os.path.join(self.log_output_dir, log_filename)

        with open(self.log_filepath, 'w') as f:
            f.write(json.dumps(avg_allocs) + '\n')
            f.write(str(qps) + '\n')
            f.write(f"event_start_time:{event_start_time}" + '\n')
            f.write(f"event_end_time:{event_end_time}" + '\n')
            f.write(wrk_stdout)
            logger.info(wrk_stdout)


    def run_loop(self):
        while True:
            # Get the command
            timestr = time.strftime("%Y%m%d-%H%M%S-%f")[:-3]
            log_filename = "output_%s.log" % timestr  # This will be the final name of the log
            json_filename = "output_%s.json" % timestr
            self.log_filepath = os.path.join(self.log_output_dir, log_filename)
            self.json_filepath = os.path.join(self.log_output_dir, json_filename)
            command = self.construct_command()
            logger.info(f"Running command: {command}")
            start_time = time.time()
            allocs = []
            try:
                # Run subprocess in background and collect stdout
                proc = subprocess.Popen(command,
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                # logger.info(f"Executed command {command}")
                while proc.poll() is None:
                    # Update and average allocations while the job is running.
                    time.sleep(0.5)
                    allocs.append(self.resource_allocs) # This is updated in the background thread.
                    logger.info("k6 still running")
                end_time = time.time()
                avg_allocs = self.average_list_of_dictionaries(allocs)
                logger.info("Reading k6 run")
                stdout, stderr = proc.communicate()
                if stdout is not None:
                    logger.info("Output produced when executing command")
                    stdout = stdout.decode('utf-8')
                if stderr is not None:
                    logger.info("Error occured when executing command")
                    stderr = stderr.decode('utf-8')
                logger.info(f"Command finished with exit code {proc.returncode}")
                if proc.returncode != 0:
                    err_msg = stdout + "\n" + stderr
                    logger.error(f'Command failed with stderr: {err_msg}')
                    raise Exception(f"Command failed with stderr: {stderr}")
                # Check resource count in background and average it
            except Exception as e:
                logger.error(
                    f"Something went wrong but DONT PANIC. I'll not report any utility this window and "
                    f"reattempt in 1 second. Error: {e}")
                traceback.print_exc()
                time.sleep(1)
                continue

            logger.info(f"Round complete with allocation {avg_allocs}. Writing results to disk.")
            self.write_output_to_disk(avg_allocs, self.k6_qps, start_time, end_time, stdout)
