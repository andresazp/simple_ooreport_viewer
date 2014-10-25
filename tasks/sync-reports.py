#!/usr/bin/env python

# 1 connect to remote server via ssh. read in all the yaml files
# 2 check if same yaml is in santisied or raw
# 3 if file is missing copy it to raw

from __future__ import print_function

import re
import os
import sys
import json
import yaml
import shutil
import tempfile

if len(sys.argv) != 4:
    print("Usage: %s <raw_directory> <sanitised_directory> <remote_servers_file>" % sys.argv[0])
    sys.exit(1)

raw_directory = sys.argv[1]
sanitised_directory = sys.argv[2]
remote_servers_file = sys.argv[3]

if not os.path.isdir(raw_directory):
    print(raw_directory + " does not exist")
    sys.exit(1)

if not os.path.isdir(sanitised_directory):
    print(sanitised_directory + " does not exist")
    sys.exit(1)

if not os.path.isfile(remote_servers_file):
    print(remote_servers_file + " does not exist")
    sys.exit(1)

with open(remote_servers_file) as f:
        remote_servers = [line.strip() for line in f]

def list_report_files(directory):
    for dirpath, dirname, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".yamloo"):
                yield os.path.join(dirpath, filename)

class Report(object):
    def __init__(self, path):
        self.fh = open(path)
        self._report = yaml.safe_load_all(self.fh)
        self.report_path = path
        self.header = self._report.next()

        self.asn = self.header['probe_asn']
        self.start_time = self.header['start_time']
        self.test_name = self.header['test_name']
        self.input_hashes = self.header['input_hashes']

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            if self.asn != other.asn:
                return False
            if self.start_time != other.start_time:
                return False
            if self.test_name != other.test_name:
                return False
            if self.input_hashes != other.input_hashes:
                return False

            return True
        else:
            return True

    def __ne__(self, other):
            return not self.__eq__(other)

    def dump_header(self):
        print(str(self.asn)+" "+str(self.start_time)+" "+str(self.test_name)+\
                " "+ str(self.input_hashes))

    def close(self):
        self.fh.close()

report_list = []
report_counter = 0

# checks if new reports are available remotely and returns copies
# them to a temporary if this is the case.
# the name of the directory is returned by this method
def get_report_list_via_rsync(remote):
    rsync_cmd = "rsync -avz -e ssh "

    temp_dir = tempfile.mkdtemp()

    print("")
    print("Checking for reports remotely on " + remote)

    if os.system(rsync_cmd + remote + " " +  temp_dir):
        print("An error occured while checking the remote server: "+remote)

    if os.listdir(temp_dir) == []:
        print("No yaml files found on remote server")
        shutil.rmtree(temp_dir)
        return None

    print("Some yaml files were found on the server to: "+temp_dir+ " and copied")
    return temp_dir

def read_reports_from_dir(dir):
    reports = []
    for report_file in list_report_files(dir):
            match = re.search("^" + re.escape(dir) + "(.*)",
                      report_file)

            # read report file
            report = Report(report_file)
            e = report.header
            e['report_file'] = match.group(1)

            reports.append(report)
            report.close()

    return reports

# read in all local reports from different directories
def readin_local_reports(directories):
    print("Reading in local reports from: "+str(directories))
    reports = []

    for dir in directories:
        # merge arrays
        reports = reports + read_reports_from_dir(dir)

    return reports

def process(remote_servers):

    local_reports = readin_local_reports([raw_directory, sanitised_directory])

    count_reports = 0

    for server in remote_servers:

        # copies reports from remote server to temporary directory
        temp_dir = get_report_list_via_rsync(server)

        remote_reports = read_reports_from_dir(temp_dir)

        for report in remote_reports:

            if report in local_reports:
                pass
            else:
                print("Copying report into into raw directory: "+\
                        report.report_path + " " + raw_directory)

                report_file = os.path.split(report.report_path)[-1]
                newname = os.path.join(raw_directory, report_file)
                os.rename(report.report_path, newname)
                count_reports += 1

        print("Found "+str(count_reports)+" reports on "+ server + " that "+\
                "were not locally present and copied them to: "+raw_directory)

        shutil.rmtree(temp_dir)

process(remote_servers)
