#!/usr/bin/python

import os, re
from email.parser import Parser
from email.header import decode_header
import sqlite3
import argparse
import ConfigParser

maildir = '.'
dbpath = 'mailboxindex.db'

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
parser.add_argument("-u", "--updatedb", help="update database", action="store_true")
parser.add_argument("-n", "--newdb", help="new database", action="store_true")
parser.add_argument("-a", "--showall", help="show all", action="store_true")
parser.add_argument("-p", "--progress", help="show progress", action="store_true")
parser.add_argument("-s", "--search", help="find mail from or to")
parser.add_argument("-m", "--maildir", help="Mailbox directory")

args=parser.parse_args()

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

p = re.compile('^[0-9]+\.[A-Za-z0-9]+\..*')

def echo(str):
    if args.verbose:
        print str

def decode_str(str):
    decoded=decode_header(str)
    res=''
    for d in decoded:
        if d[1]:
            res += d[0].decode(d[1])
        else:
            res += d[0]
    return(res.replace('\n', ''))

def parsefile(file_name):
    try:
        headers = Parser().parse(open(file_name, 'r'))
        mail_to = decode_str(headers['to'])
        mail_from = decode_str(headers['from'])
        mail_subject = decode_str(headers['subject'])
        echo('ADD TO DATABASE')
        echo('File: %s' % file_name)
        echo('From: %s' % mail_to)
        echo('To: %s' % mail_from)
        echo('Subject: %s' % mail_subject)
        echo('=============')
        params = (file_name, mail_from, mail_to, mail_subject)
        cn.execute(dbinsert, params)
    except Exception as e:
        print(e)
        print(file_name)

def updatedb():
    for root, subdirs, files in os.walk(maildir):
        for file in os.listdir(root):
            filePath = os.path.join(root, file)
            if os.path.isdir(filePath):
                pass
            else:
                if p.match(file):
                    file_abspath = os.path.abspath(filePath)
                    if not cn.execute(dbselect_filename, (file_abspath,)).fetchone():
                        parsefile(file_abspath)
                        if args.progress and not args.verbose:
                            print '.',
    if args.progress and not args.verbose: print '.'
    for row in cn.execute(dbselect_files):
        if not os.path.isfile(row[0]):
            if args.verbose:
                echo('Delete File: %s' % row[0])
            cn.execute(dbdelete_file,(row[0],))
            if args.progress and not args.verbose:
                print '.',
    cn.commit()
    if args.progress and not args.verbose: print '.'

config = ConfigParser.ConfigParser()
config.read(['/etc/mailfinder.cfg', os.path.expanduser('~/.mailfinder.cfg'), 'mailfinder.cfg'])
if config.has_section('main'):
    if config.has_option('main', 'maildir'):
        maildir=config.get('main', 'maildir')
    if config.has_option('main', 'dbpath'):
        dbpath = config.get('main', 'dbpath')


if args.maildir:
    maildir=args.maildir

if args.verbose:
    print "Verbosity turned on"
    print 'Database: %s' % dbpath
    print 'Maildir: %s' % maildir

cn = sqlite3.connect(dbpath)
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
        print 'File: %s' % row[0]
        print 'From: %s' % row[1]
        print 'To: %s' % row[2]
        print 'Subject: %s' % row[3]
        print('==============================')

if args.search:
    echo("Filter: %s" % args.search)
    print('==============================')
    for row in cn.execute(dbselect_from, ('%'+ args.search +'%',)):
        print 'File: %s' % row[0]
        print 'From: %s' % row[1]
        print 'To: %s' % row[2]
        print 'Subject: %s' % row[3]
        print('==============================')
cn.close()
