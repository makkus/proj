from seafileapi import client, group
from seafileapi.exceptions import DoesNotExist
import os.path
import logging
import sys
import requests
import urllib
import ConfigParser
import socket
import time
import argparse
import getpass
from pwd import getpwnam

PROJECT_GROUP_NAME = 'Projects'
CONF_FILENAME = 'cer_project.conf'
CONF_SYS = '/etc/'+CONF_FILENAME
CONF_HOME = os.path.expanduser('~/.'+CONF_FILENAME)
DEFAULT_SEAFILE_URL = 'https://seafile.cer.auckland.ac.nz'
HOSTS_SUBDIR = "/hosts"

url = 'https://seafile.cer.auckland.ac.nz'
token = 'ce60ebf97e2af4bcb2da167545aae4433b842b7f'

# arg parsing ===============================================
class CliCommands(object):

    def __init__(self):

        self.config = ProjectConfig()
        parser = argparse.ArgumentParser(
            description='Helper utility for project related tasks')

        parser.add_argument('--project', '-p', help='the project name, overwrites potential config files', type=str, default=self.config.project_name)
        parser.add_argument('--url', '-u', help='the url of the seafile server', type=str, default=self.config.seafile_url)
        parser.add_argument('--hostname', '-s', help='the hostname', default=self.config.host_name)
        subparsers = parser.add_subparsers(help='Subcommand to run')
        init_parser = subparsers.add_parser('init', help='Initialize this host, write config to ~/.'+CONF_FILENAME)
        init_parser.add_argument('--system', help='writes system-wide configuration instead of just for this user (to: /etc/'+CONF_FILENAME+')', action='store_true')
        init_parser.set_defaults(func=self.init, command='init')
        
        upload_parser = subparsers.add_parser('upload', help='Upload one or multiple files into the approriate hosts subdirectory of this projects library')
        upload_parser.add_argument('files', metavar='file', type=file, nargs='+', help='the files to upload')
        upload_parser.set_defaults(func=self.upload, command='upload')

        self.namespace = parser.parse_args()

        self.project_name = self.namespace.project
        self.hostname = self.namespace.hostname

        if not self.namespace.command == 'init':
            self.seafile_client = Seafile(self.namespace.url, self.config.token)
            self.seafile_client.set_project_group()
            self.repo = self.seafile_client.get_repo(self.project_name)
            self.dir = self.seafile_client.get_directory(self.repo, '/'+self.hostname)

        # call the command
        self.namespace.func(self.namespace)


    def init(self, args):

        seafile_url = None
        
        while (True):
            if args.url:
                url = args.url
            else:
                url = raw_input("Seafile url ["+DEFAULT_SEAFILE_URL+"]: ")
                if not url:
                    url = DEFAULT_SEAFILE_URL

            try:
                sf_client = Seafile(url, 'xxx')
                ping_success = sf_client.call_ping()
            except:
                print "Connection error, please try again."
                continue

            if ping_success:
                seafile_url = url
                break
            else:
                print "Could not connect to seafile service on ''"+url+", please try again."

        token = self.config.token

        while (True):
            if not token:
                username = raw_input("Please enter your username: ")
                password = getpass.getpass()

                sf_client = Seafile(seafile_url, 'xxx')
                token = sf_client.call_get_token(username, password)
                if not token:
                    continue


            # test connection
            sf_client = Seafile(seafile_url, token)
            response = sf_client.call_auth_ping()

            if not response:
                print "Authentication token didn't work, please try again."
                token = None
                continue
            else:
                break
            
        if args.project:
            project_name = args.project
        else:
            while (True):
                project_name = raw_input("Project name: ")
                if project_name:
                   break

               
        hostname = raw_input("Hostname: ["+args.hostname+"]: ")
        
        if not hostname:
            hostname = self.main_args.hostname
            
        cnf = ConfigParser.RawConfigParser()
        cnf.add_section('Project')
        cnf.set('Project', 'name', project_name)
        cnf.add_section('Host')
        cnf.set('Host', 'name', hostname)
        cnf.add_section('Seafile')
        cnf.set('Seafile', 'url', seafile_url)

        if args.system:
            cnf_file = CONF_SYS
        else:
            cnf_file = CONF_HOME
            
        with open(cnf_file, 'wb') as configfile:
            cnf.write(configfile)

        # write only to home directory, since this contains login info
        cnf = ConfigParser.RawConfigParser()
        cnf.add_section('Seafile')
        cnf.set('Seafile', 'token', token)

        if args.system:
            with open(CONF_HOME, 'wb') as configfile:
                cnf.write(configfile)
        else:
            with open(CONF_HOME, 'a') as configfile:
                cnf.write(configfile)

        os.chmod(CONF_HOME, 0700)
        try:
            uid = os.environ['SUDO_UID']
        except KeyError:
            uid = os.getuid()

        os.chown(CONF_HOME, int(uid), -1)


    def upload(self, args):

        for f in args.files:
            self.seafile_client.upload_file(self.repo, '/'+self.hostname, f.name)
        

        
class Seafile(object):

    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.auth_headers = {'Authorization': 'token '+token}
        self.seafile_client = client.SeafileApiClient(self.url, token=self.token)
        self.project_group_name = PROJECT_GROUP_NAME
        self.project_group = None
        


    def set_project_group(self):
        self.project_group = self.get_group(self.project_group_name)
        
    def call_base(self, path, req_type='get', data={}, req_params={}, url=None, files={}):

        method = getattr(requests, req_type)
        if not url:
            url = self.url+'/api2/'+path
            if req_params:
                parms = urllib.urlencode(req_params)
                url = url + '?' + parms

        logging.info('Issuing '+req_type.upper()+' request to: '+url)
        if data:
            temp = dict(data)
            if temp['password']:
                temp['password'] = 'xxxxxxxxx'
            logging.info('Data: '+str(temp))

        resp = method(url, headers=self.auth_headers, data=data, files=files)
        return resp

    def call_get_token(self, username, password):
        """Obtain the auth token."""

        data = {'username': username, 'password': password}
        response = self.call_base('auth-token/', data=data, req_type='post')
        try:
            token = response.json()['token']
        except KeyError:
            return None
        
        return token

    def call_ping(self):
        """Pings the server"""

        response = self.call_base('ping').text.strip("\"")
        return response == "pong"

    def call_auth_ping(self):
        """Pings the server, using authentication"""

        response = self.call_base('auth/ping/').text.strip("\"")
        return response == "pong"

    def get_group(self, group_name):
        """Returns the group object for the group with the given name."""

        response = self.call_base('groups/').json()['groups']
        matches = [g for g in response if g['name'] == self.project_group_name]
        if len(matches) == 0 or len(matches) > 1:
            return None
        else:
            g = group.Group(self.seafile_client, matches[0]['id'], matches[0]['name'])
            return g


    def share_repo_with_group(self, repo, group, permission):
        """Share a repo with a group"""

        data = {
            'share_type': 'group',
            'group_id': self.project_group.group_id,
            'permission': permission
        }
        return self.call_base('shared-repos/'+repo.id+'/', req_params=data, req_type='put')



    def get_repo(self, proj_name):
        """Returns the repo object for this project, creates a new one if none exists yet. 

        Returns None if more than one repo exists with that name.
        """

        all_repos = self.seafile_client.repos.list_repos()
        r = [r for r in all_repos if r.name == proj_name]

        if len(r) > 1:
            return None
        elif len(r) == 0:
            r = self.seafile_client.repos.create_repo(proj_name, 'Library for project: '+proj_name)
            self.share_repo_with_group(r, self.project_group, 'rw')
            return r
        else:
            return r[0]

    def get_directory(self, repository, path):
        """Returns the directory object for the given path, creates it (and all it's parents) if necessary."""
        try:
            if path != '/':
                # otherwise 2 directories are created
                path = path.rstrip('/')

            dir = repository.get_dir(path)
        except DoesNotExist:
            parent_child = os.path.split(path)
            parent = parent_child[0]
            child = parent_child[1]
            parent_dir = self.get_directory(repository, parent)
            return parent_dir.mkdir(child)

        return dir

    def get_update_link(self, repo):
        """Get the link to update a file on the repo."""

        response = self.call_base('repos/'+repo.id+'/update-link/')
        return response.text

    def upload_file(self, repo, parent_path, file):
        """Uploads or updates the file to/on the repo."""

        full_path = parent_path+file
        try:
            repo.get_file(full_path)
        except DoesNotExist:
            "Uploading file..."
            path = os.path.dirname(full_path)
            dir = self.get_directory(repo, path)
            return dir.upload_local_file(file)

        link = self.get_update_link(repo).strip('"')
        files_to_upload = {'file': open(file, 'rb'),
                           'target_file': full_path}
        # file = open(file, 'rb')
        response = self.call_base(None, url=link, files=files_to_upload, req_type='post')
        return response

# Init ======================================================
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

class ProjectConfig(object):

    def __init__(self):
        config = ConfigParser.SafeConfigParser()

        candidates = [CONF_SYS, CONF_HOME]
        config.read(candidates)
        try:
            self.project_name = config.get('Project', 'name')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            self.project_name = None

        try:
            self.host_name = config.get('Host', 'name')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            self.host_name = None

        if not self.host_name:
            self.host_name = socket.gethostname()

        try:
            self.seafile_url = config.get('Seafile', 'url')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            self.seafile_url = None
            
        # read config file again, this time only the one in the home dir
        config = ConfigParser.SafeConfigParser()
        read = config.read(CONF_HOME)

        try:
            self.token = config.get('Seafile', 'token')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            self.token = None
            

if __name__ == "__main__":
                
    CliCommands()


sys.exit(0)
