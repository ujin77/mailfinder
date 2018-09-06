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

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="output verbosity", action="store_true")
parser.add_argument("-u", "--updatedb", help="update database", action="store_true")
parser.add_argument("-n", "--newdb", help="new database", action="store_true")
parser.add_argument("-p", "--progress", help="show progress", action="store_true")
parser.add_argument("-a", "--showall", help="show all", action="store_true")
parser.add_argument("-s", "--search", help="find mail from or to")
parser.add_argument("-j", "--subj", dest='_subj', help="find mail by subject")
parser.add_argument("-f", "--from", dest='_from', help="find mail by from")
parser.add_argument("-t", "--to", dest='_to', help="find mail by to")
parser.add_argument("-m", "--maildir", help="Mailbox directory")

args = parser.parse_args()

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
 WHERE mail_from LIKE (:filter) OR mail_to LIKE (:filter);"""
dbselect_to = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_to LIKE (:filter);"""
dbselect_from = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_from LIKE (:filter)"""
dbselect_subj = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_subject LIKE (:filter)"""
dbselect_any = """SELECT file_name, mail_from, mail_to, mail_subject FROM mailbox
 WHERE mail_to LIKE (:filter) OR mail_from LIKE (:filter) OR mail_subject LIKE (:filter)"""

p = re.compile('^[0-9]+\.[A-Za-z0-9]+\..*')


def echo(str):
    if args.verbose:
        print str


def print_row(row):
    print 'File: %s' % row[0]
    print 'From: %s' % row[1]
    print 'To: %s' % row[2]
    print 'Subject: %s' % row[3]


def get_decoded_header(headers, section):
    res = ''
    try:
        decoded=decode_header(headers[section])
        for d in decoded:
            if d[1]:
                res += d[0].decode(d[1])
            else:
                res += d[0]
    except UnicodeDecodeError as e:
        if section == 'subject':
            return '-=SUBJECT DECODE ERROR=-'
        else:
            return headers[section]
    except Exception as e:
        print(type(e))
        print(e.args)
        print('Exception: %s' % e)
        print('Section: %s' % section)
        print('Original header: %s' % headers[section])
        # raise 'get_decoded_header'
    return res.replace('\n', '')


def parsefile(file_name):
    mail_to = ''
    mail_from = ''
    mail_subject = ''
    try:
        headers = Parser().parse(open(file_name, 'r'))
        mail_to = get_decoded_header(headers,'to')
        mail_from = get_decoded_header(headers,'from')
        mail_subject = get_decoded_header(headers,'subject')
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
                if p.match(file_name):
                    file_abspath = os.path.abspath(file_path)
                    if not cn.execute(dbselect_filename, (file_abspath,)).fetchone():
                        parsefile(file_abspath)
                        if args.progress and not args.verbose:
                            print '.',
    if args.progress and not args.verbose: print '.'
    for row in cn.execute(dbselect_files):
        if not os.path.isfile(row[0]):
            if args.verbose:
                echo('Delete File: %s' % row[0])
            cn.execute(dbdelete_file, (row[0],))
            if args.progress and not args.verbose:
                print '.',
    cn.commit()
    if args.progress and not args.verbose: print '.'


#################MAIN#######################
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
if args.showall:
    print('==============================')
    for row in cn.execute(dbselect_all):
        print_row(row)
        print('==============================')

if args.search:
    echo("Filter: %s" % args.search)
    print('==============================')
    for row in cn.execute(dbselect_any, ('%' + args.search + '%',)):
        print_row(row)
        print('==============================')
if args._from:
    echo("Filter: %s" % args._from)
    print('==============================')
    for row in cn.execute(dbselect_from, ('%' + args._from + '%',)):
        print_row(row)
        print('==============================')
if args._to:
    echo("Filter: %s" % args._to)
    print('==============================')
    for row in cn.execute(dbselect_to, ('%' + args._to + '%',)):
        print_row(row)
        print('==============================')
if args._subj:
    echo("Filter: %s" % args._subj)
    print('==============================')
    for row in cn.execute(dbselect_subj, ('%' + args._subj + '%',)):
        print_row(row)
        print('==============================')

cn.close()
