#!/usr/bin/env python

import itertools
import json
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os
import requests
import signal
import time

from matplotlib.font_manager import FontProperties
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Misc config
executor = 'mesos'
health_checker = 'marathon'
num_nodes = 1
protocol = 'TCP'
base_dir = '{}-{}-{}-{}'.format(executor, health_checker, protocol, num_nodes)
step = 10

# HTTP config
base = 'https://ken-3fqyd-elasticl-1joi109afqfod-1807274520.us-west-2.elb.amazonaws.com/marathon'
headers = {
        'Authorization': 'token=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1aWQiOiJib290c3RyYXB1c2VyIiwiZXhwIjoxNTQ2OTgyNTY4fQ.BeH7IuyVDAGFxnzyFllpxJ33iokuMmJJhRCoqR43XWoedHC3O6TsH4FOtc_L4Dw9zs15aLWHZO4YSA4ZrWyT762yb6BPOAVOeLgwwZhKTcg_979lvFW6Sn0KkqM7pO4Ek-dHV3TOnh3XWV1ThPlvSVS4P87ihhRc4fkufTdvVOPAX-YcPPhNSKWXJzhZBdEKTELEP9LtMShn-KGhznLGkE8dcnTD1BWc5BIe2yXkXuwPCSeWZsT_1w9kVgumujBjvxB-KkyiymBGG5QFXNCYO1Fmf109rJFMgALs-zWoB1Ygh_lJ2GjktWT5uRiQm7TV4ynwrvZ-gGd39AEMJ-VZaw',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
        }
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Plot config
title = '{} {} check - {} Executor - {} Agent(s)'.format(health_checker.title(), protocol,
                                                         executor.title(), num_nodes)
states = [
        'TASK_HEALTHY',
        'TASK_UNHEALTHY',
        'TASK_KILLING',
        'TASK_RUNNING',
        'TASK_STAGING',
        'UNSCHEDULED'
        ]

data = {
        'TASK_HEALTHY': {'count': [], 'color': 'darksage'},
        'TASK_RUNNING': {'count': [], 'color': 'steelblue'},
        'TASK_STAGING': {'count': [], 'color': '0.55'},
        'TASK_UNHEALTHY': {'count': [], 'color': 'indianred'},
        'TASK_KILLING': {'count': [], 'color': 'purple'},
        'UNSCHEDULED': {'count': [], 'color': '0.85'}
        }

# Ugly global state
max_count = 0
start_time = time.time()
shutting_down = False


def scale_to(instances, time_delta, force=False):
    print('===================================')
    print('Time: {} - Scaling to {}'.format(time_delta, instances))
    print('===================================')
    print()

    app = fetch_app()

    app["scaling"]["instances"] = instances

    url = '{}/v2/pods/hc'.format(base)

    params = {'force': 'true' if force else 'false'}

    r = requests.put(url, headers=headers, params=params, json=app, verify=False)

    r.raise_for_status()


def fetch_app():
    url = '{}/v2/pods/hc'.format(base)
    params = {}

    r = requests.get(url, headers=headers, params=params, verify=False)

    r.raise_for_status()

    return r.json()


def fetch_app_status():
    url = '{}/v2/pods/hc::status'.format(base)
    params = {}

    r = requests.get(url, headers=headers, params=params, verify=False)

    r.raise_for_status()

    return r.json()


def fetch_deployments():
    url = '{}/v2/deployments'.format(base)
    params = {}

    r = requests.get(url, headers=headers, params=params, verify=False)

    r.raise_for_status()

    return r.json()


def task_status(task):
    # TODO(KGS): Need to see how we can get this out of pods
    # if task['status'] == 'TASK_RUNNING':
        # Task running
        # if 'healthCheckResults' in task:
        #     if task['healthCheckResults'][0]['alive']:
        #         return 'TASK_HEALTHY'
        #     else:
        #         return 'TASK_UNHEALTHY'
    return task['status']


def pods_to_containers(tasks):
    c = []
    for task in tasks:
        for containers in task["containers"]:
            c.append(containers)
    return c


def print_task_summary(app, time_delta):

    tasks = app['instances']
    instances = app["spec"]["scaling"]["instances"]

    containers = pods_to_containers(tasks)
    print('Time: {}\tTasks: {}/{}'.format(time_delta, len(containers), instances))
    print('===================================')    
    # commented until we find a solution for groupby for pods
    tasks_by_state = itertools.groupby(sorted(containers, key=task_status), key=task_status)

    for state, taskIter in tasks_by_state:
        tasks = list(taskIter)
        print ('{}\t{}/{}'.format(state, len(tasks), instances))

    print ('===================================')
    print()


def process_results(app):
    tasks = app['tasks']
    goal = app['instances']

    iterator = itertools.groupby(sorted(tasks, key=task_status), key=task_status)
    tasks_by_state = dict((k, list(g)) for k, g in iterator)
    acc = 0
    for state in states[:-1]:
        if state in tasks_by_state.keys():
            count = len(tasks_by_state[state])
            acc = acc + count
            data[state]['count'].append(count)
        else:
            data[state]['count'].append(0)

    data['UNSCHEDULED']['count'].append(goal - acc)


def plot(time_delta):
    fig = plt.figure(dpi=100, figsize=(10.24, 7.68))
    ax = plt.subplot(111)

    num_requests = len(data[states[0]]['count'])
    ind = np.arange(0, num_requests) # the x locations

    bottom = np.zeros(num_requests)
    for state in states:
        counts = np.array(data[state]['count'])
        color = data[state]['color']
        ax.bar(ind, counts, 0.75, color=color, linewidth=0, bottom=bottom)

        bottom = bottom + counts

    plt.title(title)

    plt.xlim(xmin=0, xmax=num_requests + 1)
    plt.xlabel('Request #')

    plt.ylabel('Number of tasks')

    # Make the legend font small
    font = FontProperties()
    font.set_size('small')

    ax.legend([state.replace('TASK_', '') for state in states],
            loc='upper left', prop=font)

    plt.savefig('{}/{}.png'.format(base_dir, time_delta))
    plt.close(fig)


def dump_app(app, time_delta):
    f = open('{}/{}.json'.format(base_dir, time_delta), 'w')
    f.write(json.dumps(app, indent=2))
    f.close()


"""Main testing loop.

It will:

    1. Scale the app down to 0 instances.
    2. Increase the instances count by 10 tasks and wait for the deployment to
       complete.
    3. Go back to the previous step.
"""


def main_loop():
    global start_time

    app = fetch_app()
    scale_down()

    start_time = time.time()
    target = 0
    while True:
        time.sleep(1)
        time_delta = int(time.time() - start_time)

        try:
            app = fetch_app_status()

            if app["spec"]["scaling"]["instances"] == len(app["instances"]) and len(fetch_deployments()) == 0:
                target = target + step
                scale_to(target, time_delta)

            print_task_summary(app, time_delta)
            # if not shutting_down:
                # next 3 lines use intertools / matplotlib which isn't set for pods
                # process_results(app)
                # plot(time_delta)
                # dump_app(app, time_delta)
        except Exception as err:
            print(err)


"""Scale down to 0 instances and wait for the deployment to complete.

The deployment is forced, overriding any other pending deployments.
"""


def scale_down():
    time_delta = int(time.time() - start_time)

    deploymentId = scale_to(0, time_delta, True)

    deployments = fetch_deployments()
    app = fetch_app_status()

    time.sleep(1)

    app = fetch_app_status()
    while app["spec"]["scaling"]["instances"] > len(app["instances"]) and len(fetch_deployments()) == 0:
        time_delta = int(time.time() - start_time)
        print_task_summary(app, time_delta)

        time.sleep(1)
        app = fetch_app_status()


def handler(signum, frame):
    global shutting_down

    # let the next ctrl + c kill the test.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    shutting_down = True
    scale_down()
    exit(0)


signal.signal(signal.SIGINT, handler)

if not os.path.exists(base_dir):
    os.makedirs(base_dir)

main_loop()
