# -*- coding: utf-8 -*-
# Created by restran on 2016/10/13
from __future__ import unicode_literals, absolute_import

import os
import sys
import time
from collections import deque
import logging
from tornado.httpclient import HTTPRequest, HTTPError
from future.moves.urllib.parse import urlunparse, urlparse
from tornado import httpclient, gen, ioloop

# 把项目的目录加入的环境变量中，这样才可以导入 common.base
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from common.base import read_dict

logger = logging.getLogger(__name__)

target_base_url = 'http://127.0.0.1:8080/index.php'
dict_list = ['dir', 'php', 'jsp', 'asp', 'aspx', 'mdb']


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
    def __init__(self, url):
        self.site_lang = ''
        self.raw_base_url = url
        self.base_url = url
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
        if response.code in [200, 301, 302, 405]:
            logger.warning('[Y] %s' % url)

    def init_dict(self):
        if self.first_item != '':
            self.first_queue.extend(self.make_bak_file_list(self.first_item))

        self.dict_data['dir'] = read_dict('dictionary/dir.txt')
        if self.site_lang != '':
            self.dict_data[self.site_lang] = read_dict('dictionary/%s.txt' % self.site_lang)
        else:
            tmp_dict_list = [t for t in dict_list if t != 'dir']
            for t in tmp_dict_list:
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
        executor = AsyncHTTPExecutor(self.base_url, self.on_queue_empty, self.first_queue)
        yield executor.run(self.on_response)


@gen.coroutine
def main():
    global target_base_url
    print(sys.argv)
    if len(sys.argv) > 1:
        target_base_url = sys.argv[1]
    logger.info(target_base_url)
    ws = WebScanner(target_base_url)
    yield ws.run()


if __name__ == '__main__':
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(main)
