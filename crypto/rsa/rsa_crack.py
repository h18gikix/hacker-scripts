# -*- coding: utf-8 -*-
# Created by restran on 2016/9/20
from __future__ import unicode_literals, absolute_import
import primefac
from Crypto.Util.number import inverse
from Crypto.PublicKey import RSA


def prime_factor(n):
    """
    找出两个素因子p和q，p*q=n
    :param n:
    :return:
    """
    # 这里返回的是所有的质因子
    try:
        r = primefac.primefac(100)
        found, p, q = False, 0, 0
        for i, x in enumerate(r):
            if i >= 2:
                return False, 0, 0
            elif i == 0:
                p = x
            elif i == 1:
                q = x
                found = True

        print('p: %s, q: %s' % (p, q))
        return found, p, q
    except:
        pass

    return False, 0, 0


def encrypt(plain, n, e):
    cipher = pow(plain, e, n)
    print(cipher)
    return plain


def decrypt(cipher, n, d):
    plain = pow(int(cipher), d, n)
    print(plain)
    return plain


def crack(n, e, encrypted_data):
    print('n: %s' % n)
    print('e: %s' % e)
    success, p, q = prime_factor(n)
    if success:
        d = inverse(e, (p - 1) * (q - 1))
        print('d: %s' % d)
        rsa = RSA.construct((n, e, d))
        plain = rsa.decrypt(encrypted_data)
        print(plain)


def main():
    # rsa.pub 是公钥
    with open('rsa.pub', 'rb') as f:
        rsa = RSA.importKey(f.read())
        # enc 是密文
        with open('enc', 'rb') as f2:
            # 直接获取到n和e
            # p, q, d 的获取方式也一样
            crack(rsa.key.n, rsa.key.e, f2.read())


if __name__ == '__main__':
    main()
