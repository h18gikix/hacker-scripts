# -*- coding: utf-8 -*-
# Created by restran on 2016/10/20

import os
import pyinotify
from optparse import OptionParser
from datetime import datetime
import traceback

traceback.format_exc()
parser = OptionParser()
parser.add_option("-b", "--backup_dir", dest="backup_dir", type="string",
                  help="backup dir, e.g. /home/bak")
parser.add_option("-w", "--watch_dir", dest="watch_dir", type="string",
                  help="watch dir")
parser.add_option("-d", dest="disable_backup", action="store_true",
                  default=False, help="disable backup")

watch_dir_name = ''
back_dir_name = ''
protected_file_ext_list = ['.php', '.ini']

"""
如果创建一个非 .php 结尾的文件，然后 mv 修改成 .php，不会被检测出来，
因为没有监控文件名修改的事件
"""


class Logger(object):
    DATE_FMT = "%H:%M:%S"

    @classmethod
    def get_date_str(cls):
        now = datetime.now()
        return now.strftime(cls.DATE_FMT)

    @classmethod
    def info(cls, message):
        print('[%s] INFO %s' % (cls.get_date_str(), message))

    @classmethod
    def warning(cls, message):
        print('[%s] WARNING %s' % (cls.get_date_str(), message))


logger = Logger()


class FileEventHandler(pyinotify.ProcessEvent):
    @classmethod
    def delete_file(cls, file_path):
        # 创建的文件中不属于特殊的保护文件，允许创建，例如正常上传图片
        # 但是不允许创建文件夹，因为新建文件夹中的文件没有办法被监控
        if not any(map(file_path.lower().endswith, protected_file_ext_list)) \
                and not os.path.isdir(file_path):
            logger.info('skip file %s' % file_path)
            return

        shell_code = "rm -rf '%s'" % file_path
        os.system(shell_code)
        logger.warning(shell_code)

    def on_create_event(self, event):
        monitor_dir, event_filename = get_file_name(event.pathname)
        logger.info('-----------------------------------------')
        logger.warning('CREATE event: %s' % event.pathname)
        file_exist = os.system("test -f '%s%s'" % (back_dir_name, event_filename))
        if file_exist == 0:
            # 恢复文件
            pass
        else:
            self.delete_file(event.pathname)

    def on_modify_event(self, event):
        monitor_dir, event_filename = get_file_name(event.pathname)
        logger.info('-----------------------------------------')
        logger.warning('MODIFY event: %s' % event.pathname)

        file_exist = os.system("test -f '%s%s'" % (back_dir_name, event_filename))
        if file_exist == 0:
            # 文件存在，先判断md5，md5相同表示恢复文件
            temp1 = os.popen("md5sum %s| awk '{print $1}'" % event.pathname).readlines()
            temp2 = os.popen("md5sum %s%s| awk '{print $1}'" % (back_dir_name, event_filename)).readlines()
            if temp1 == temp2:
                # 属于恢复文件，不需要处理
                pass
            else:
                # 属于被修改文件，执行恢复
                logger.warning('restore file %s' % event.pathname)
                shell_code = 'cp -a %s%s %s' % (back_dir_name, event_filename, event.pathname)
                logger.warning(shell_code)
        else:
            self.delete_file(event.pathname)

    def on_delete_event(self, event):
        monitor_dir, event_filename = get_file_name(event.pathname)
        logger.info("-----------------------------------------")
        logger.warning('DELETE event: %s' % event.pathname)
        file_exist = os.system("test -f '%s%s'" % (back_dir_name, event_filename))
        # 0 表示存在
        if file_exist == 0:
            # 恢复文件
            logger.warning('restore file %s' % event.pathname)
            shell_code = 'cp -a %s%s %s' % (back_dir_name, event_filename, event.pathname)
            os.system(shell_code)
            logger.warning(shell_code)
        else:
            pass

    def process_IN_MOVE_SELF(self, event):
        # logger.info('MOVE_SELF event: %s' % event.pathname)
        pass

    # 等价于执行删除
    def process_IN_MOVED_FROM(self, event):
        logger.info('-----------------------------------------')
        logger.info('MOVED_FROM event: %s' % event.pathname)
        self.on_delete_event(event)

    # 文件重命名，或者复制，等价于执行复制
    def process_IN_MOVED_TO(self, event):
        logger.info('-----------------------------------------')
        logger.warning('MOVED_TO event: %s' % event.pathname)
        self.on_create_event(event)

    def process_IN_ACCESS(self, event):
        # print "-----------------------------------------"
        # print "ACCESS event:", event.pathname
        # logger.info('ACCESS event: %s' % event.pathname)
        pass

    def process_IN_ATTRIB(self, event):
        # print "-----------------------------------------"
        # print "ATTRIB event:", event.pathname
        logger.info('ATTRIB event: %s' % event.pathname)
        pass

    def process_IN_CLOSE_NOWRITE(self, event):
        # print "-----------------------------------------"
        # print "CLOSE_NOWRITE event:", event.pathname
        # logger.info('CLOSE_NOWRITE event: %s' % event.pathname)
        pass

    def process_IN_CLOSE_WRITE(self, event):
        # print "-----------------------------------------"
        # print "CLOSE_WRITE event:", event.pathname
        # logger.info('CLOSE_WRITE event: %s' % event.pathname)
        pass

    def process_IN_CREATE(self, event):
        logger.info('-----------------------------------------')
        self.on_create_event(event)

    def process_IN_DELETE(self, event):
        logger.info("-----------------------------------------")
        logger.warning('DELETE event: %s' % event.pathname)
        self.on_delete_event(event)

    def process_IN_MODIFY(self, event):
        logger.info('-----------------------------------------')
        logger.warning('MODIFY event: %s' % event.pathname)
        self.on_modify_event(event)

    def process_IN_OPEN(self, event):
        # print "-----------------------------------------"
        # print "OPEN event:", event.pathname
        pass


def get_file_name(path_name):
    if path_name.startswith(watch_dir_name):
        return watch_dir_name, path_name[len(watch_dir_name):]


def backup_monitor_dir(watch_dir, backup_dir):
    logger.info('backup files')
    if os.system('test -d %s' % backup_dir) != 0:
        os.system('mkdir -p %s' % backup_dir)

    os.system('rm -rf %s/*' % backup_dir)
    logger.info('cp -a %s/* %s/' % (watch_dir, backup_dir))
    os.system('cp -a %s/* %s/' % (watch_dir, backup_dir))


def main():
    (options, args) = parser.parse_args()
    if None in [options.watch_dir, options.backup_dir]:
        parser.print_help()
        return

    # 删除最后的 /
    options.watch_dir = options.watch_dir.rstrip('/')
    options.backup_dir = options.backup_dir.rstrip('/')

    global watch_dir_name
    global back_dir_name
    watch_dir_name = options.watch_dir
    back_dir_name = options.backup_dir

    logger.info('watch dir %s' % options.watch_dir)
    logger.info('back  dir %s' % options.backup_dir)

    if not options.disable_backup:
        backup_monitor_dir(options.watch_dir, options.backup_dir)

    # watch manager
    wm = pyinotify.WatchManager()
    wm.add_watch(options.watch_dir, pyinotify.ALL_EVENTS, rec=True)
    # event handler
    eh = FileEventHandler()

    # notifier
    notifier = pyinotify.Notifier(wm, eh)
    notifier.loop()


if __name__ == '__main__':
    main()
