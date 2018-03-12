#!/usr/bin/env python
"""
   check_mk_dnsdist : local check_mk plugin which will monitor dnsdist and collect statistics on servers,pools,qps,
                    latency etc.

   Version      Author          Date        Description
     0.1        Nigel Heaney    06-02-2018  Initial version

"""
import os
import re
import json
import urllib2


class check_mk_dnsdist:
    def __init__(self):
        self.apiurl = 'http://localhost:8080/api/v1/servers/localhost'
        self.api_password = 'secret'
        self.headers = {"X-API-Key": self.api_password}
        self.data = {}

        self.up_threshold = 1           # number of servers up in ap pool to be considered ok
        self.debug = 0

    def call_api(self, url, header):
        """
        Call dnsdist rest API to collect data on server pools/servers and stats

        :param url    : url to access the api and path to collect the data
        :param header : dictionary of headers we need to pass to the api
        :return       : (dict) the extracted json data as dictionary
        """
        request = urllib2.Request(url, headers=header)
        return json.load(urllib2.urlopen(request))

    def collect_data(self):
        """
        Collect the data we need to process and report on the availability of the api to omd
        """
        status = 0
        checkname = 'dnsdist_api'
        description = ''
        try:
            self.data = self.call_api(self.apiurl, self.headers)
        except Exception as e:
            description = "WARN - API is not responding (" + str(e) + ")"
            status = 1
            self.print_output(status, checkname, "-", description)
            exit(1)

        # All is good so we will report api as working
        description = "OK - API is responding"
        status = 0
        self.print_output(status, checkname, "-", description)
        return 1

    def process_data(self):
        """
        Process the data and output as specific check_mk checks.

        Checks include: Pool status (if all down alert), pool query including per member, qps per pool/member,
        latency av/member.
        """
        status = 0
        checkname = ''
        description = ''
        perfdata = '-'
        temp_list = []
        pool_members = {}
        # Lets extract all the pool names in the dataset.
        for pool in self.data['servers']:
            temp_list.append(pool['pools'][0])
            pool_members[pool['pools'][0]] = []

        # Lets collate a list of servers and what pool they belong to
        for server in self.data['servers']:
            pool_members[server['pools'][0]].append(server['name'])

        # Now lets calculate qps per pool, num of queries, up status for the pool, latency and outstanding and Drops
        perf_query = ""
        perf_qps = ""
        perf_latency = ""
        perf_outstanding = ""
        perf_status = ""
        perf_status_crit = 0
        perf_status_crit_details = ""
        perf_status_warn = 0
        for pool in pool_members:
            qps = []
            queries = []
            outstanding = []
            latency = []
            up = 0
            down = 0
            for server in self.data['servers']:
                # for each server in the pool, gather stats
                if server['name'] in pool_members[pool]:
                    # Lets determine up/down status
                    if server['state'].lower() == "up":
                        up += 1
                    else:
                        down += 1

                    # collate stats
                    qps.append({server['name']: server['qps']})
                    queries.append({server['name']: server['queries']})
                    latency.append({server['name']: server['latency']})
                    outstanding.append({server['name']: server['outstanding']})

            # up/down status -
            if down > 0:
                perf_status_warn += 1
            if up == 0:
                perf_status_crit += 1
                perf_status_crit_details += str(pool) + "|"
            perf_status += str(pool) + "=" + str(up) + "|"

            # qps - output current queries per second
            totalqps = 0
            for item in qps:
                numqps = item.values()
                totalqps += int(numqps[0])
            perf_qps += str(pool) + "=" + "{0:.3f}".format(totalqps, 2) + "|"

            # queries check
            totalqueries = 0
            for item in queries:
                numq = item.values()
                totalqueries += int(numq[0])
            perf_query += str(pool) + "=" + str(totalqueries) + "|"

            # latency check
            totallatency = 0
            for item in latency:
                lat = item.values()
                # if a server is mark DOWN manually then dnsdist will set latency to Null so ig nore if we detect this
                if lat[0] is not None:
                    totallatency += float(lat[0])

            # calculate av latency for the pool total/number of members
            avg_latency = totallatency / len(latency)
            perf_latency += str(pool) + "=" + "{0:.3f}".format(avg_latency, 3) + "|"

            # outstanding - amount of pending requests
            totaloutstanding = 0
            for item in outstanding:
                out = item.values()
                totaloutstanding += int(out[0])
            perf_outstanding += str(pool) + "=" + str(totaloutstanding) + "|"

        # Output summary level stats to keeps things tidy
        # qps
        status = 0
        checkname = "dnsdist_qps"
        description = "OK - Current Queries per second (QPS) "
        self.print_output(status, checkname, perf_qps[:-1], description)

        # queries
        checkname = "dnsdist_queries"
        description = "OK - Total queries performed"
        self.print_output(status, checkname, perf_query[:-1], description)

        # latency
        checkname = "dnsdist_latency"
        description = "OK - Average Latency per pool "
        self.print_output(status, checkname, perf_latency[:-1], description)

        # outstanding
        checkname = "dnsdist_outstanding"
        description = "OK - Outstanding queries per pool "
        self.print_output(status, checkname, perf_outstanding[:-1], description)

        # Pool status
        checkname = "dnsdist_pool_status"
        # If we have crit more than 0 then have servers pools which are completely offline so create an alert
        if perf_status_crit > 0:
            description = "CRIT - " + str(perf_status_crit) + " pool(s) DOWN! (" + \
                          perf_status_crit_details.replace("|", ",")[:-1] + ")"
            status = 2
        elif perf_status_warn > 0:
            description = "WARN - " + str(perf_status_warn) + " pool(s) have servers down"
            status = 1
        else:
            description = "OK - Server pools are healthy"
        self.print_output(status, checkname, perf_status[:-1], description)

    def print_output(self, status=0, checkname='', perfdata='-', description=''):
        """
        Print correctly formatted output for check_mk
        """
        print "{0} {1} {2} {3}".format(status, checkname, perfdata, description)

    def print_debug(self, message=''):
        """
         If debug is enabled, then print the message to stdout (this should only be used from the commandline to assist
         with erroneous data analysis)
        """
        if self.debug == 1:
            print "DEBUG: {0}".format(message)

    def load_config(self, configfile="/etc/check_mk/check_mk_dnsdist.conf"):
        """
        Load a config file which will allow parameters to be stored outside of the script and will contain list of
        containers to watch, thresholds etc. If this file is missing then it will generate a default config which
        can then be customised by admins
        """

        # Check if config exists, if not create one and exit silently unless debug is enabled
        if os.path.isfile(configfile):
            conffile = open(configfile, 'r')
            conf = conffile.readlines()
            conffile.close()
            for line in conf:
                if re.search('^#', line):
                    continue  # comments
                if line == '':
                    continue  # ignore empty lines
                # parameters
                if 'debug=' in line:
                    self.debug = re.sub('^.*=', '', line.rstrip())
                if 'url=' in line:
                    self.apiurl = re.sub('^.*=', '', line.rstrip())
                if 'password=' in line:
                    self.api_password = re.sub('^.*=', '', line.rstrip())
                # More later
        else:
            self.generate_config()
            exit(1)

    def generate_config(self, configfile="/etc/check_mk/check_mk_dnsdist.conf"):
        """
        Generate a default config file which can be customised by an admin.
        """
        conffile = open(configfile, 'w')
        conffile.write('#\n')
        conffile.write('# check_mk_dnsdist configuration file\n')
        conffile.write('#\n')
        conffile.write('debug=0\n')
        conffile.write('#url="http://localhost:8080/api/v1/servers/localhost"\n')
        conffile.write('#password="aPassword"\n\n')
        conffile.close()
        os.chmod(configfile, 0755)


if __name__ == "__main__":
    check = check_mk_dnsdist()
    check.load_config()
    if check.collect_data():
        check.process_data()
