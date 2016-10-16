# -*- coding: utf-8 -*-
# Created by restran on 2016/10/13

"""
使用方法

默认是自动识别，如果没有识别出，则使用全部字典
python scanner.py -u http://www.github.com

指定使用什么字典去扫描
python scanner.py -u http://www.github.com -w 10 -t 3 -d php -d dir
"""

from __future__ import unicode_literals, absolute_import

import os
import sys
import time
from collections import deque
import logging
from tornado.httpclient import HTTPRequest, HTTPError
from future.moves.urllib.parse import urlunparse, urlparse
from tornado import httpclient, gen, ioloop
from optparse import OptionParser
import validators

# 把项目的目录加入的环境变量中，这样才可以导入 common.base
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.base import read_dict

logger = logging.getLogger(__name__)

parser = OptionParser()
parser.add_option("-u", "--url", dest="target_url", type="string",
                  help="target url, e.g. http://127.0.0.1:8080/index.php")
parser.add_option("-w", "--worker", dest="worker_num", type="int",
                  default=10, help="max worker num")
parser.add_option("-t", "--timeout", dest="timeout", type="int",
                  default=3, help="timeout in seconds")
parser.add_option("-d", "--dict", dest="scan_dict", default=None,
                  action="append",
                  choices=['dir', 'php', 'jsp', 'asp', 'aspx', 'mdb'],
                  help="which dict to scan, only allow dir, php, jsp, asp, aspx, mdb")

# 字典列表
DICT_LIST = ['dir', 'php', 'jsp', 'asp', 'aspx', 'mdb']


class AsyncHTTPExecutor(object):
    """
    异步HTTP请求，可以并发访问
    """

    def __init__(self, base_url, fn_on_queue_empty, first_queue, max_workers=10, timeout=3):
        self.base_url = base_url.rstrip('/')
        self.fn_on_queue_empty = fn_on_queue_empty
        self.task_queue = deque()
        self.task_queue.extend(first_queue)
        self.timeout = timeout
        self.max_workers = max_workers

    def get_next_task(self):
        try:
            item = self.task_queue.popleft()
        except IndexError:
            item = self.fn_on_queue_empty(self.task_queue)
        return item

    def make_url(self, item):
        if item.startswith('/'):
            url = '%s%s' % (self.base_url, item)
        else:
            url = '%s/%s' % (self.base_url, item)
        return url

    @gen.coroutine
    def do_request(self, item, fn_on_response):
        url = ''
        try:
            url = self.make_url(item)
            response = yield httpclient.AsyncHTTPClient().fetch(
                HTTPRequest(url=url,
                            method='HEAD',
                            body=None,
                            decompress_response=True,
                            connect_timeout=self.timeout,
                            request_timeout=self.timeout,
                            follow_redirects=False))
            fn_on_response(url, item, response, self.task_queue)
        except HTTPError as e:
            if hasattr(e, 'response') and e.response:
                fn_on_response(url, item, e.response, self.task_queue)
            else:
                logger.error('Exception: %s %s' % (e, item))
        except Exception as e:
            logger.error('Exception: %s %s' % (e, item))

    @gen.coroutine
    def fetch_url(self, fn_on_response):
        item = self.get_next_task()
        while item is not None:
            yield self.do_request(item, fn_on_response)
            item = self.get_next_task()

    @gen.coroutine
    def run(self, fn_on_response, *args, **kwargs):
        logger.info('executor start')
        start_time = time.time()
        # Start workers, then wait for the work queue to be empty.
        for i in range(self.max_workers):
            yield self.fetch_url(fn_on_response)

        end_time = time.time()
        logger.info('executor done, %.3fs' % (end_time - start_time))


class WebScanner(object):
    def __init__(self, url, max_worker=10, timeout=3, scan_dict=None):
        self.site_lang = ''
        self.raw_base_url = url
        self.base_url = url
        self.max_worker = max_worker
        self.timeout = timeout
        self.scan_dict = scan_dict
        self.first_item = ''
        self.dict_data = {}
        self.first_queue = []
        self.count = 0

    def on_queue_empty(self, queue, max_num=100):
        for t in range(max_num):
            for d in self.dict_data.keys():
                dict_d = self.dict_data[d]
                try:
                    item = dict_d.popleft()
                except IndexError:
                    del self.dict_data[d]
                    break

                queue.append(item)

    def on_response(self, url, item, response, queue):
        if response.code in [200, 304, 401, 403, 405]:
            logger.warning('[Y] %s %s' % (response.code, url))

    def init_dict(self):
        if self.scan_dict is None:
            if self.first_item != '':
                self.first_queue.extend(self.make_bak_file_list(self.first_item))

            self.dict_data['dir'] = read_dict('dictionary/dir.txt')
            if self.site_lang != '':
                self.dict_data[self.site_lang] = read_dict('dictionary/%s.txt' % self.site_lang)
            else:
                tmp_dict_list = [t for t in DICT_LIST if t != 'dir']
                for t in tmp_dict_list:
                    self.dict_data[t] = read_dict('dictionary/%s.txt' % t)
        else:
            for t in self.scan_dict:
                self.dict_data[t] = read_dict('dictionary/%s.txt' % t)

    @classmethod
    def make_bak_file_list(cls, file_name):
        """
        根据文件名称生成备份文件名称
        :param file_name:
        :return:
        """
        data = [
            '~%s.swap' % file_name,
            '%s.swap' % file_name,
            '%s.bak' % file_name,
            '%s~' % file_name,
        ]

        return data

    def prepare_url(self):
        url_parsed = urlparse(self.raw_base_url)
        items = url_parsed.path.split('/')
        if len(items) > 0:
            item = items[-1]
            items = items[:-1]
            new_path = '/'.join(items)
        else:
            item = ''
            new_path = url_parsed.path
        url = urlunparse((url_parsed.scheme, url_parsed.netloc, new_path, '', '', ''))

        if item.endswith('.php'):
            self.site_lang = 'php'
        elif item.endswith('.asp'):
            self.site_lang = 'asp'
        elif item.endswith('.aspx'):
            self.site_lang = 'aspx'

        self.base_url = url
        self.first_item = item
        logger.info('base_url: %s' % url)
        logger.info('first_item: %s' % item)

    @gen.coroutine
    def run(self):
        self.prepare_url()
        self.init_dict()
        executor = AsyncHTTPExecutor(
            self.base_url, self.on_queue_empty, self.first_queue,
            self.max_worker, self.timeout
        )
        yield executor.run(self.on_response)


@gen.coroutine
def main():
    (options, args) = parser.parse_args()
    if options.target_url is None or not validators.url(options.target_url):
        parser.print_help()
        return

    logger.info('target_url: %s' % options.target_url)
    logger.info('worker_num: %s' % options.worker_num)
    logger.info('timeout: %s' % options.timeout)
    if options.scan_dict is None:
        logger.info('scan_dict: auto')
    else:
        logger.info('scan_dict: %s' % options.scan_dict)

    ws = WebScanner(
        options.target_url, options.worker_num,
        options.timeout, options.scan_dict
    )
    yield ws.run()


if __name__ == '__main__':
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(main)
