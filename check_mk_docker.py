#!/usr/bin/env python
"""
   check_mk_docker  : check_mk local plugin which will probe and report back on docker and its containers.
                
   Version      Author          Date        Description      
     0.1        Nigel Heaney    08-11-2015  Initial version
                                            
    
"""
import os
import time
import re


class dockermon():
    def __init__(self):
        self.checkmemwarn=80                                #Mem warning threshold %
        self.checkmemcritical=90            
        self.checkcpuwarn=95                                #cpu warning threshold %
        self.checkcpucritical=99
        self.checkdatastorewarn=80                          #Meta/Data store threshold
        self.checkdatastorecritical=90                      #Meta/Data store threshold
        self.checkmetastorewarn=80                          #Meta/Data store threshold
        self.checkmetastorecritical=90                      #Meta/Data store threshold
        
        self.ShowFriendlyNames="yes"                        #This option requires docker 1.8.2 and above to work. If using older version then set to no here or in config file.
        self.dockerformatoption=' --format "{{.Names}}"'    #This allows customised formatting to be sent to docker commands
        
        self.monitorlist=[]                                 #List on container names which we want to monitor as being up
        self.DisplayAllContainers=False                     #Set this to true if you want each container listed with cpu,memory utilisation etc.  
        self.running_containers=''
        
        self.debug=0		
        self.dockerbin=''
        self.dockerpid=''
        self.dockerpidfile=''
        
    def MonitorDaemon(self):
        '''Monitor the Docker daemon is running
           
        '''
        return_status=0
        status = '0'
        checkname = 'Docker_Service'
        perfdata="service_uptime="
        uptime="0"
        description=''
        #Locate the docker binary, exit if absent. Silent exit to prevent issues with check_mk and inventory process.
        dockerlocations = [ '/usr/bin/docker' ] #list an entry for each os type
        for p in dockerlocations:
            if os.path.isfile(p):
                self.dockerbin=p
                break
        if self.dockerbin == '':
          self.PrintDebug("Docker not found")
          sys.exit(2) 

        #Check the process is up and running.
        dockerpidlocations = [ '/run/docker.pid', '/var/run/docker.pid' ]
        self.dockerpid = ''
        for p in dockerpidlocations:
          if os.path.isfile(p):
            try:
              f=open(p, 'r')
              self.dockerpid=int(f.readline())
              self.dockerpidfile=p
            except:
              #no pid so assume its down or never started
              status = 2
              description = "Service Down - Problem reading pid file "
              self.PrintDebug(description)
        if self.dockerpid == '':
          #No pid found
          status = 2
          description = "Service Down or No PID file found"
          self.PrintDebug(description)

        else:
          #Test if the process is alive
          try:
            os.kill(int(self.dockerpid), 0)
          except OSError:
            status = 2
            description = "Docker service is not running"
            self.PrintDebug(description)
          else:
            status = 0
            description = "Docker service is running"
            self.PrintDebug(description)
            #calculate the uptime of the service
            uptime=str(int(time.time() - os.stat(self.dockerpidfile).st_mtime))
            return_status=1
        self.PrintOutput(status,checkname,perfdata + uptime,description)
        return return_status

    def MonitorNumInstances(self):
        '''Monitor number of running containers.
           
        '''
        count=0
        status=0
        checkname="Docker_Containers"
        perfdata="Running_Instances="
        description=" Docker container(s) are running"

        for l in self.running_containers.split('\n'):
            if "CONTAINER ID" in l: continue        #ignore the header 
            if l == '': continue                    #ignore empty lines 
            if self.debug: print "DEBUG: " + l
            count+=1
        count=str(count)
        self.PrintOutput(status,checkname,perfdata + count,count + description)

    def MonitorMetrics(self):
        '''Monitor cpu,memory and network for total and list each container if requested
           
        '''
        count=0
        status=0
        checkname="Docker Metrics"
        perfdata="-"
        description=" Docker container(s) are running"

        nodelist = []
        nlist = ""
        cstats = []
        totalcpu = totalmemused = name = cpu = mem = memunits = net = ''
        totalcpu = totalmem = totalmemused = 0.0
        warnlevel=""
        critlevel=""
        memtotal=1
        #gather list of nodes
        for l in self.running_containers.split('\n'):
            if "CONTAINER ID" in l: continue        #ignore the header 
            if l == '': continue                    #ignore empty lines
            self.PrintDebug(l)
            nodelist.append(re.split(',',re.sub('  +',',',l))[0])
            count+=1
        if count == 0:
            #no containers so quit
            return
        for n in nodelist: nlist += str(n) + " "
        #retreive usage stats for each node and store in an array. We will then compute the total utilisation
        container_stats=os.popen(self.dockerbin + " stats --no-stream=true " + nlist ).read()
        for l in container_stats.split('\n'):
            if "CONTAINER" in l: continue           #ignore the header 
            if l == '': continue                    #ignore empty lines
            self.PrintDebug(l)
            #split the stats
            l = re.sub(' / ','/',l)    #bug: docker is inconsistent between versions and sometimes there are spaces.
            containterstats = re.split(',',re.sub('  +',',',l))
            name = containterstats[0]
            cpu = containterstats[1]
            memunits = containterstats[2]
            mem = containterstats[3]
            #net = containterstats[0]

            #calculate mem units
            temp1, temp2 = re.split('/',memunits)
            temp3, temp4 = re.split(' ',temp1)
            memused = int(self.ConvertMetric(value=temp3, metric=temp4))
            temp3, temp4 = re.split(' ',temp2)
            memtotal = int(self.ConvertMetric(value=temp3, metric=temp4))
            #Bug fix, sometimes docker can incorrectly report total memory as zero and causes script to fail. Solution is to add 1 byte so we never divide by zero.
            #This is insignificant statistically :)
            memtotal += 1
           
            cpu = float(re.sub('%','',cpu))
            mem = float(re.sub('%','',mem))

            warnlevel = str(int((memtotal/100.0) * float(self.checkmemwarn)))
            critlevel = str(int((memtotal/100.0) * float(self.checkmemcritical)))
            self.PrintDebug("Memused:" + str(memused))
            self.PrintDebug("Memtotal:" + str(memtotal))

            #if set to list each container stats then alert here
            if self.DisplayAllContainers.lower() == "true":
                #cpu%
                status=0
                checkname="Container_CPU_" + name
                perfdata="CPU_Usage%=" + str(cpu) + ";" + str(self.checkcpuwarn) + ";" + str(self.checkcpucritical) + ";;"
                description="Container currently utilising " + str(cpu) + "% of cpu" 
                #Lets compare results with thresholds and categorise
                if cpu >= self.checkcpuwarn: status=1
                if cpu >= self.checkcpucritical: status=2
                self.PrintOutput(status,checkname,perfdata,description)
                
                #realmem
                status=0
                checkname="Container_Memory_" + name
                perfdata="Memory_Usage=" + str(memused) +  ";" + warnlevel + ";" + critlevel + ";0;" + str(memtotal)
                description="Container currently utilising " + str(memused) + " of " + str(memtotal)
                #determine is thresholds have been crossed
                percentmemused = (100.0/memtotal) * memused
                description = description + " = " + "{0:.2f}".format(percentmemused) + "% utilised"
                if percentmemused >= float(self.checkmemwarn): status=1
                if percentmemused >= float(self.checkmemcritical): status=2
                self.PrintOutput(status,checkname,perfdata,description)

            totalcpu += cpu
            totalmem += mem
            totalmemused += memused
            #ignore for now, container['netin'] = netin
            #ignore for now, container['netout'] = netout
            totalmemused=int(totalmemused)
        
        #Total cpu%
        status=0
        checkname="Docker_CPU_Total"
        perfdata="CPU_Usage%=" + str(totalcpu) + ";" + str(self.checkcpuwarn) + ";" + str(self.checkcpucritical) + ";;"
        description="Docker containers currently utilising " + str(totalcpu) + "% of cpu"
        #Lets compare results with thresholds and categorise
        if totalcpu >= float(self.checkcpuwarn): status=1
        if totalcpu >= float(self.checkcpucritical): status=2
        self.PrintOutput(status,checkname,perfdata,description)

        #BUG - We will extract the total memory that docker can see
        tempmemtotal=os.popen(self.dockerbin + " info  2> /dev/null | grep 'Total Memory'").read().split(": ")[1]
        temp1, temp2 = re.split(' ',tempmemtotal)
        memtotal = int(self.ConvertMetric(value=temp1, metric=temp2))

        #Total realmem
        status=0
        checkname="Docker_Memory_Total"
        perfdata="Memory_Usage=" + str(totalmemused) + ";" + warnlevel + ";" + critlevel + ";0;" + str(memtotal+1)
        description="Total memory usage is " + str(totalmemused) + " of " + str(memtotal)
        #determine is thresholds have been crossed
        percentmemused = (100.0/memtotal) * totalmemused
        description = description + " or " + "{0:.2f}".format(percentmemused) + "%"
        if percentmemused >= float(self.checkmemwarn): status=1
        if percentmemused >= float(self.checkmemcritical): status=2
        self.PrintOutput(status,checkname,perfdata,description)
        
    def MonitorFileSystems(self):
        '''Monitor the containers filesystem usage.
           
        '''
        pass
                
    def MonitorIsContainerUp(self):
        '''Monitor for specific containers and alert if down. This list is derived from the config file or if you
           explciitely define a list within this script or you import as a module and customise there.
        '''
        status=0
        checkname="Container_"

        #Use the monitorlist to iterate and check. If its empty then there is nothing to do so we exit silently
        if self.monitorlist == []:
            #nothing to do so give up.
            self.PrintDebug("No container names defined in config file")
            return

        for c in self.monitorlist:
            status=2
            description = "Container is DOWN!"
            perfdata="Status=0"
            for l in self.running_containers.split('\n'):
                if "CONTAINER ID" in l: continue        #ignore the header 
                if l == '': continue                    #ignore empty lines 
                if c in l:
                    #continer is up
                    status=0
                    description = "Container is UP!"
                    perfdata="Status=1"
                    
                if status == 0: break
            self.PrintOutput(status,checkname + c,perfdata, description)
                
    def MonitorMetaDataStores(self):
        '''Monitor the Datastore and Metastore usage - This is critical due to the fact that docker is allocating thin storage (normally 10gb at a time) and can easily be over provisioned :(
           
        '''
        count=0
        status=0
        checkname="Docker_DataStores"
        perfdata="-"
        description=""
        dataused = ""
        datausedpercent = 0
        dataavailable = ""
        metaused = ""
        metausedpercent = 0
        metaavailable = ""
        temp1 = ""
        temp2 = ""
        
        #Harvest docker info and stripout the information we want
        dockerinfo=os.popen(self.dockerbin + " info 2> /dev/null" ).readlines()
        for l in dockerinfo:
            if 'Data Space Used: ' in l : dataused = re.sub('^ Data Space Used: ','',l)
            if 'Data Space Available: ' in l : dataavailable = re.sub('^ Data Space Available: ','',l)
            if 'Metadata Space Used: ' in l : metaused = re.sub('^ Metadata Space Used: ','',l)
            if 'Metadata Space Available: ' in l : metaavailable = re.sub('^ Metadata Space Available: ','',l)
        
	#Fix: might not be using DM so no meta/data percentages will be shown. Instead of erroring we will now silently exit the method to protect OMD.
        if dataused == "" or dataavailable == "" or metaused == "" or metaavailable == "":
            #Either something is wrong or not using lvm as st orage backend (overlay etc) so quit checking this.
            return
        else:
            #Datastore usage - extract, convert and calculate
            temp1, temp2 = re.split(' ', dataused)
            self.PrintDebug("(T1,T2) = " + temp1 + "," + temp2)
            dataused = int(self.ConvertMetric(value=temp1, metric=temp2))
            temp1, temp2 = re.split(' ', dataavailable)
            self.PrintDebug("(T1,T2) = " + temp1 + "," + temp2)
            dataavailable = int(self.ConvertMetric(value=temp1, metric=temp2))
            datausedpercent = 100 / float(dataused + dataavailable) * dataused
            if datausedpercent >= self.checkdatastorewarn: 
                #Warning threshold has been met
                status=1
            if datausedpercent >= self.checkdatastorecritical: 
                #Crit threshold has been met
                status=2
            #tidy up output values
            datausedpercent = "{0:.2f}".format(datausedpercent)
            description="Datastore is at " + datausedpercent + "%, "
            
            #Metastore usage - extract, convert and calculate
            temp1, temp2 = re.split(' ', metaused)
            metaused = int(self.ConvertMetric(value=temp1, metric=temp2))
            temp1, temp2 = re.split(' ', metaavailable)
            metaavailable = int(self.ConvertMetric(value=temp1, metric=temp2))
            metausedpercent = 100 / float(metaused + metaavailable) * metaused
            if metausedpercent >= self.checkmetastorewarn: 
                #Warning threshold has been met
                if status != 2: status=1
            if metausedpercent >= self.checkmetastorecritical: 
                #Crit threshold has been met
                status=2
            
            #tidy up and format output
            metausedpercent = "{0:.2f}".format(metausedpercent)
            description += "Metastore is at " + metausedpercent + "%"
            perfdata = "datastore=" + str(datausedpercent) + ";" + str(self.checkdatastorewarn) + ';' + str(self.checkdatastorecritical) + ';0;100' + "|metastore=" + metausedpercent + ";" + str(self.checkmetastorewarn) + ';' + str(self.checkmetastorecritical) + ';0;100'
            datausedpercent = int(((dataused + dataavailable)/100) * dataused)
            
            self.PrintOutput(status,checkname,perfdata,description)
            
    def PrintOutput(self,status=0, checkname='', perfdata='-', description=''):
        '''Print correctly formatted output for check_mk
           
        '''
        print "{0} {1} {2} {3}".format(status, checkname, perfdata, description)

    def PrintDebug(self,message=''):
        '''If debug is enabled, then print the message to stdout (this should only be used from the commandline to assist with erroneous data analysis)
        '''
        if self.debug == 1:
          print "DEBUG: {0}".format(message)

    def ConvertMetric(self,value='0', metric='B'):
        '''normalise a value based on the metric supplied
        '''
        #determine what metric is being used and convert to bytes (approximate value only)
        metric = metric.rstrip()
        if metric in ['TB', 'TiB']: 
            multiplier = 1024 * 1024 * 1024 * 1024
        elif metric in ['GB', 'GiB']:
            multiplier = 1024 * 1024 * 1024
        elif metric in ['MB', 'MiB']:
            multiplier = 1024 * 1024
        elif metric in ['KB', 'KiB']:
            multiplier = 1024
        else:
            multiplier = 1
            
        return (float(value) * multiplier)

    def LoadConfig(self,configfile="/etc/check_mk/dockermon.conf"):
        '''Load a config file which will allow parameters to be stored outside of the script and will contain list of containers to watch, thresholds etc.
           If this file is missing then it will generate a default config which can then be customised by admins
        '''
        #Check if config exists, if not create one and exit silently unless debug is enabled
        if os.path.isfile(configfile):
            conffile=open(configfile, 'r')
            conf=conffile.readlines()
            conffile.close()
            for l in conf:
                if re.search('^#', l): continue         #comments
                if l == '': continue                    #ignore empty lines
                #Thresholds
                if 'checkmemwarn=' in l: self.checkmemwarn=re.sub('^.*=','',l.rstrip())
                if 'checkmemcritical=' in l: self.checkmemcritical=re.sub('^.*=','',l.rstrip())
                if 'checkcpuwarn=' in l: self.checkcpuwarn=re.sub('^.*=','',l.rstrip())
                if 'checkcpucritical=' in l: self.checkcpucritical=re.sub('^.*=','',l.rstrip())
                #datastore thresholds
                if 'checkdatastorewarn=' in l: self.checkdatastorewarn=re.sub('^.*=','',l.rstrip())
                if 'checkdatastorecritical=' in l: self.checkdatastorewarn=re.sub('^.*=','',l.rstrip())
                if 'checkmetastorewarn=' in l: self.checkmetastorewarn=re.sub('^.*=','',l.rstrip())
                if 'checkmetastorecritical=' in l: self.checkmetastorewarn=re.sub('^.*=','',l.rstrip())
                #List each container in addition to totals
                if 'DisplayAllContainers=' in l: self.DisplayAllContainers=re.sub('^.*=','',l.rstrip())
                #enable debug logging - only to be used for analysis, omd will not like this!
                if 'Debug=' in l: self.DisplayAllContainers=re.sub('^.*=','',l.rstrip())
                #Check if Friendly names should be used
                if 'ShowFriendlyNames=' in l: self.ShowFriendlyNames=re.sub('^.*=','',l.rstrip())
                #Container lists
                if 'monitor=' in l: self.monitorlist.append(re.sub('^.*=','',l.rstrip()))

            if self.ShowFriendlyNames.lower()=="no":  self.dockerformatoption=""
            self.PrintDebug("checkmemwarn=" + str(self.checkmemwarn))
            self.PrintDebug("checkmemcrit=" + str(self.checkmemcritical))
            self.PrintDebug("checkcpuwarn=" + str(self.checkcpuwarn))
            self.PrintDebug("checkcpucrit=" + str(self.checkcpucritical))
            self.PrintDebug('checkdatastorewarn=' + str(self.checkdatastorewarn))
            self.PrintDebug('checkdatastorecritical=' + str(self.checkdatastorewarn))
            self.PrintDebug('checkmetastorewarn=' + str(self.checkmetastorewarn))
            self.PrintDebug('checkmetastorecritical=' + str(self.checkmetastorewarn))
            self.PrintDebug('DisplayAllContainers=' + str(self.DisplayAllContainers))
            self.PrintDebug("Monitor List=" + str(self.monitorlist))
            self.PrintDebug("ShowFriendlyNames=" + str(self.ShowFriendlyNames))
        else:
            self.GenerateConfig()
            exit(1)
            
    def GenerateConfig(self,configfile="/etc/check_mk/dockermon.conf"):
        '''Generate a default config file which can be customised by an admin.

        '''
        conffile=open(configfile, 'w')
        conffile.write('#\n')
        conffile.write('# DockerMon Coniguration file\n')
        conffile.write('# This file can be used to provide some customisation to the monitoring script.  If for whatever reason you\n')
        conffile.write('# need a clean version or this becomes corrupted then simply delete this file and new version will be generated.\n#\n\n')
        conffile.write('#Debug - 0 off OR 1 on - do not enable this and leave it, omd will have problems reading debug :O\n')
        conffile.write('Debug=0\n')
        conffile.write('ShowFriendlyNames=yes\n')
        conffile.write('DisplayAllContainers=False\n\n')
        conffile.write('#Thresolholds\n')
        conffile.write('checkmemwarn=80\n')
        conffile.write('checkmemcritical=90\n')
        conffile.write('checkcpuwarn=95\n')
        conffile.write('checkcpucritical=99\n')
        conffile.write('checkdatastorewarn=80\n')
        conffile.write('checkdatastorecritical=90\n')
        conffile.write('checkmetastorewarn=80\n')
        conffile.write('checkmetastorecritical=90\n')
        conffile.write('\n\n#Monitor Containers\n')
        conffile.write('#List any container which you want track that they are running.  You can reference by uid or use the friendly container name.\n#Examples:\n')
        conffile.write('#monitor=1d1792684b10\n')
        conffile.write('#monitor=Mycontainer\n')
        conffile.close()
        os.chmod(configfile, 0755)        

    def RunningContainerList(self):
        '''Generate a list of running containers which will be used by other functions.
           
        '''
        self.running_containers=os.popen(self.dockerbin + " ps" + self.dockerformatoption).read()

if __name__ == "__main__":
    p=dockermon()
    if p.MonitorDaemon():
        p.debug=0
        p.DisplayAllContainers=False
        p.LoadConfig()
        p.RunningContainerList()
        p.MonitorNumInstances()
        p.MonitorMetrics()
        p.MonitorIsContainerUp()
        p.MonitorMetaDataStores()
