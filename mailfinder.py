#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from email.parser import Parser
from email.header import decode_header
import sqlite3
import argparse
import ConfigParser

mail_dir = '.'
dbpath = 'mailboxindex.db'

###############################################################
dbcreate = """
CREATE TABLE IF NOT EXISTS mailbox(file_name TEXT PRIMARY KEY, mail_from TEXT, mail_to TEXT, mail_subject TEXT);
"""
dbinsert = "INSERT OR IGNORE INTO mailbox VALUES (?, ?, ?, ?);"
dbselect_all = "SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox;"
dbselect_files = "SELECT file_name FROM mailbox;"
dbselect_filename = "SELECT file_name FROM mailbox WHERE file_name=(?);"
dbdelete_file = "DELETE FROM mailbox WHERE file_name=(?);"

dbselect_like = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_from LIKE ('%' || :filter || '%') OR mail_to LIKE ('%' || :filter || '%');"""
dbselect_to = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_to LIKE ('%' || :filter || '%');"""
dbselect_from = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_from LIKE ('%' || :filter || '%')"""
dbselect_subj = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_subject LIKE ('%' || :filter || '%')"""
dbselect_any = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_to LIKE ('%' || :filter || '%') OR mail_from LIKE ('%' || :filter || '%') OR mail_subject LIKE ('%' || :filter || '%')"""

re_file = re.compile(r'^[0-9]+\.[A-Za-z0-9]+\..*')
re_head = re.compile(r'=\?\S+\?=')

def echo(s):
    if args.verbose:
        print s


def print_row(row_array):
    print 'File: %s' % row_array[0]
    print 'From: %s' % row_array[1]
    print 'To: %s' % row_array[2]
    print 'Subject: %s' % row_array[3]


def print_csv(row_array):
    print "'{}','{}','{}','{}'".format(row_array[1], row_array[2], row_array[3], row_array[0])


def get_decoded_header(headers, section):
    res = ''
    try:
        decoded = decode_header(headers[section])
        for d in decoded:
            if d[1]:
                try:
                    res += d[0].decode(d[1])
                except UnicodeDecodeError as e:
                    if args.verbose:
                        print 'Exception: %s' % e
                        print "Error decode: ", d[0]
                        print '%s: %s' % (section, headers[section])
            else:
                res += d[0]
    except Exception as e:
        print(type(e))
        # print(e.args)
        print('Exception: %s' % e)
        print '%s: %s' % (section, headers[section])
        # raise e
    return res.replace('\n', '')


def parsefile(file_name):
    mail_to = ''
    mail_from = ''
    mail_subject = ''
    try:
        headers = Parser().parse(open(file_name, 'r'))
        mail_to = get_decoded_header(headers, 'to')
        mail_from = get_decoded_header(headers, 'from')
        mail_subject = get_decoded_header(headers, 'subject')
        echo('ADD TO DATABASE')
        echo('File: %s' % file_name)
        echo('From: %s' % mail_to)
        echo('To: %s' % mail_from)
        echo('Subject: %s' % mail_subject)
        echo('=============')
        params = (file_name, mail_from, mail_to, mail_subject)
        cn.execute(dbinsert, params)
    except Exception as e:
        print(type(e))
        print(e.args)
        print('Exception: %s' % e)
        print('File: %s' % file_name)
        print('From: %s' % mail_to)
        print('To: %s' % mail_from)
        print('Subject: %s' % mail_subject)


def updatedb():
    for root, subdirs, files in os.walk(mail_dir):
        for file_name in os.listdir(root):
            file_path = os.path.join(root, file_name)
            if os.path.isdir(file_path):
                pass
            else:
                if re_file.match(file_name):
                    file_abspath = os.path.abspath(file_path)
                    if not cn.execute(dbselect_filename, (file_abspath,)).fetchone():
                        parsefile(file_abspath)
                        if args.progress and not args.verbose:
                            print '.',
    if args.progress and not args.verbose:
        print '.'
    for row_file in cn.execute(dbselect_files):
        if not os.path.isfile(row_file[0]):
            if args.verbose:
                echo('Delete File: %s' % row_file[0])
            cn.execute(dbdelete_file, (row_file[0],))
            if args.progress and not args.verbose:
                print '.',
    cn.commit()
    if args.progress and not args.verbose:
        print '.'


def print_data(data, csv=False, verbose=False):
    if csv:
        print "'from','to','subject','path'"
        for res in data:
            print "'{}','{}','{}','{}'".format(res[1], res[2], res[3], res[0])
    else:
        print('==============================')
        for res in data:
            print 'From: %s' % res[1]
            print 'To: %s' % res[2]
            print 'Subject: %s' % res[3]
            if verbose:
                print 'File: %s' % res[0]
            print('==============================')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="output verbosity", action="store_true")
    parser.add_argument("-u", "--updatedb", help="update database", action="store_true")
    parser.add_argument("-n", "--newdb", help="new database", action="store_true")
    parser.add_argument("-p", "--progress", help="show progress", action="store_true")
    parser.add_argument("-a", "--showall", help="show all", action="store_true")
    parser.add_argument("-c", "--csv", help="show all in csv format", action="store_true")
    parser.add_argument("-s", "--search", help="find mail from or to")
    parser.add_argument("-j", "--subject", dest='mail_subj', help="find mail by subject")
    parser.add_argument("-f", "--from", dest='mail_from', help="find mail by from")
    parser.add_argument("-t", "--to", dest='mail_to', help="find mail by to")
    parser.add_argument("-m", "--maildir", help="Mailbox directory")

    args = parser.parse_args()

    config = ConfigParser.ConfigParser()
    config.read(['/etc/mailfinder.cfg', os.path.expanduser('~/.mailfinder.cfg'), 'mailfinder.cfg'])
    if config.has_section('main'):
        if config.has_option('main', 'maildir'):
            mail_dir = config.get('main', 'maildir')
        if config.has_option('main', 'dbpath'):
            dbpath = config.get('main', 'dbpath')

    if args.maildir:
        mail_dir = args.maildir

    if args.verbose:
        print "Verbosity turned on"
        print 'Database: %s' % dbpath
        print 'Maildir: %s' % mail_dir

    cn = sqlite3.connect(dbpath)
    cn.text_factory = str
    cn.executescript(dbcreate)

    if args.newdb:
        echo("Drop data in database and update")
        cn.execute("DROP TABLE IF EXISTS mailbox;")
        cn.executescript(dbcreate)
        updatedb()

    if args.updatedb:
        echo("Update database")
        updatedb()
    elif args.showall:
        print_data(cn.execute(dbselect_all), args.csv, args.verbose)
    elif args.search:
        echo("Filter all: %s" % args.search)
        print_data(cn.execute(dbselect_any, (args.search,)), args.csv, args.verbose)
    elif args.mail_from:
        echo("Filter from: %s" % args.mail_from)
        print_data(cn.execute(dbselect_from, (args.mail_from,)), args.csv, args.verbose)
    elif args.mail_to:
        echo("Filter to: %s" % args.mail_to)
        print_data(cn.execute(dbselect_to, (args.mail_to,)), args.csv, args.verbose)
    elif args.mail_subj:
        echo("Filter subject: %s" % args.mail_subj)
        print_data(cn.execute(dbselect_subj, (args.mail_subj,)), args.csv, args.verbose)
    else:
        parser.print_help()
    cn.close()
