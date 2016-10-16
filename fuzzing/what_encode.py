# -*- coding: utf-8 -*-
# created by restran on 2016/09/30

"""
自动解析字符串数据是采用了怎样的编码
"""

import logging

FORMAT = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=FORMAT, datefmt=DATE_FMT, level=logging.DEBUG)
logger = logging.getLogger(__name__)

encode_method = ['hex', 'base64', 'zlib']


# TODO
# urlencode, binary

def parse_str(encode_str, decode_method, *args, **kwargs):
    try:
        decode_str = encode_str.decode(decode_method)
        logger.info('%s: %s' % (decode_method, decode_str))
        return True, decode_str
    except:
        return False, encode_str


def parse(encode_str):
    encode_str = encode_str.strip()
    should_continue = True
    tmp_encode_str, decode_str = encode_str, encode_str
    recognized_methods = []
    while should_continue:
        for m in encode_method:
            success, decode_str = parse_str(tmp_encode_str, m)
            if success:
                tmp_encode_str = decode_str
                recognized_methods.append(m)
                break
            else:
                continue
        else:
            should_continue = False

    if len(recognized_methods) > 0:
        logger.info('methods: %s' % '->'.join(recognized_methods))
        logger.info('plain  : %s' % decode_str)
    else:
        logger.info('not encode method recognized')
    return decode_str


def main():
    parse('666c61677b686578327374725f6368616c6c656e67657d')


if __name__ == '__main__':
    main()
