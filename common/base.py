# -*- coding: utf-8 -*-
# Created by restran on 2016/10/10
from __future__ import unicode_literals, absolute_import
# noinspection PyCompatibility
from concurrent import futures
from future.moves.queue import Queue
import time
import logging
import logging.config
import os
import sys

# 当前目录所在路径
BASE_PATH = os.path.abspath(os.path.dirname(__file__))

# 日志所在目录
LOG_PATH = BASE_PATH
# 可以给日志对象设置日志级别，低于该级别的日志消息将会被忽略
# CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
LOGGING_LEVEL = 'INFO'
LOGGING_HANDLERS = ['console']

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'file': {
            'level': 'DEBUG',
            # 'class': 'logging.FileHandler',
            'class': 'logging.handlers.RotatingFileHandler',
            # 如果没有使用并发的日志处理类，在多实例的情况下日志会出现缺失
            # 当达到10MB时分割日志
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 1,
            # If delay is true,
            # then file opening is deferred until the first call to emit().
            'delay': True,
            'filename': os.path.join(LOG_PATH, 'script.log'),
            'formatter': 'verbose'
        }
    },
    'loggers': {
        '': {
            'handlers': LOGGING_HANDLERS,
            'level': LOGGING_LEVEL,
        }
    }
})

logger = logging.getLogger(__name__)


def group(lst, n):
    """
    http://code.activestate.com/recipes/303060-group-a-list-into-sequential-n-tuples/
    Group a list into sequential n-tuples
    :param lst:
    :param n:
    :return:
    """
    for i in range(0, len(lst), n):
        val = lst[i:i + n]
        if len(val) == n:
            yield tuple(val)


def read_dict(file_name):
    """
    读取字典文件
    :param file_name:
    :return:
    """
    with open(file_name, 'r') as f:
        data = f.read().split('\n')
        data = [t for t in data if t != '']

    return data


def ip_range(start_ip, end_ip):
    ip_list = []
    start = list(map(int, start_ip.split(".")))
    end = list(map(int, end_ip.split(".")))
    tmp = start
    ip_list.append(start_ip)
    while tmp != end:
        start[3] += 1
        for i in (3, 2, 1):
            if tmp[i] == 256:
                tmp[i] = 0
                tmp[i - 1] += 1
        ip_list.append(".".join(map(str, tmp)))

    return ip_list


class TaskExecutor(object):
    """
    使用线程的执行器，可以并发执行任务
    """

    def __init__(self, task_list, max_workers=20):
        self.max_workers = max_workers
        self.task_list = task_list
        self.task_queue = Queue()
        for t in task_list:
            self.task_queue.put(t)

    def get_next_task(self, max_num):
        output = []
        count = 0
        while not self.task_queue.empty() and count < max_num:
            t = self.task_queue.get()
            output.append(t)
            count += 1

        return output

    def run(self, fn_task, *args, **kwargs):
        logger.info('executor start')
        start_time = time.time()
        with futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            next_tasks = self.get_next_task(self.max_workers)
            future_to_task = {
                executor.submit(fn_task, task, *args, **kwargs): task
                for task in next_tasks
                }
            should_shut_down = False
            while not should_shut_down and len(future_to_task.items()) > 0:
                tmp_future_to_task = {}

                for future in futures.as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        should_shut_down = future.result()
                    except Exception as exc:
                        logger.info('%s generated an exception: %s' % (task, exc))
                    else:
                        if should_shut_down:
                            break

                        new_task = self.get_next_task(1)
                        if len(new_task) > 0:
                            task = new_task[0]
                            tmp_future_to_task[executor.submit(fn_task, task, *args, **kwargs)] = task

                future_to_task = tmp_future_to_task
        end_time = time.time()
        logger.info('executor done, %.3fs' % (end_time - start_time))
