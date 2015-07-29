"""

A client script to help working with project-based files.

Requirements:

python:
 - argparse
 - requests (if you get error messages about SSL, pin to version 2.5.3: pip install requests==2.5.3)


"""

# from seafileapi import client, group
# from seafileapi.exceptions import DoesNotExist
import os.path
import logging
import sys
import requests
import urllib
import ConfigParser
import socket
import argparse
import getpass
from pwd import getpwnam
import io
import re
import posixpath
import time
from urllib import urlencode
from functools import wraps
import tempfile

ZERO_OBJ_ID = '0000000000000000000000000000000000000000'

PROJECT_GROUP_NAME = 'Projects'
CONF_FILENAME = 'cer_project.conf'
CONF_SYS = '/etc/'+CONF_FILENAME
CONF_HOME = os.path.expanduser('~/.'+CONF_FILENAME)
DEFAULT_SEAFILE_URL = 'https://seafile.cer.auckland.ac.nz'
HOSTS_SUBDIR = "/hosts"
NOTES_FILE = "/notes.md"
COMMAND_FILE_NAME = "command.md"

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
        init_parser = subparsers.add_parser('init', help='Initialize this host, write config to ~/.'+CONF_FILENAME +', deleting it if it already exists')
        init_parser.add_argument('--system', help='writes system-wide configuration instead of just for this user (to: /etc/'+CONF_FILENAME+')', action='store_true')
        init_parser.set_defaults(func=self.init, command='init')
        
        add_parser = subparsers.add_parser('add', help='Upload one or multiple files into the approriate hosts subdirectory of this projects library')
        add_parser.add_argument('files', metavar='file', type=unicode, nargs='+', help='the files to upload')
        add_parser.set_defaults(func=self.add, command='add')

        add_note_parser = subparsers.add_parser('note', help='Add one or multiple notes to the project')
        add_note_parser.add_argument('notes', metavar='notes', type=str, nargs='*', help='the note(s) to add')
        add_note_parser.set_defaults(func=self.note, command='note')

        add_last_command_parser = subparsers.add_parser('last_command', help='Adds the last command of the bash history to the relevant '+COMMAND_FILE_NAME+' file.')
        add_last_command_parser.set_defaults(func=self.last_command, command='last_command')

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
        if os.path.isfile(CONF_HOME):
            os.remove(CONF_HOME)

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
            hostname = args.hostname


        cnf = ConfigParser.RawConfigParser()
        cnf.add_section('Project')
        cnf.set('Project', 'name', project_name)
        cnf.add_section('Host')
        cnf.set('Host', 'name', hostname)
        cnf.add_section('Seafile')
        cnf.set('Seafile', 'url', seafile_url)

        if not args.system:
            cnf.set('Seafile', 'token', token)
            with open(CONF_HOME, 'wb') as configfile:
                cnf.write(configfile)
            
        else:
            with open(CONF_SYS, 'wb') as configfile:
                cnf.write(configfile)

            # write only to home directory, since this contains login info
            cnf = ConfigParser.RawConfigParser()
            cnf.add_section('Seafile')
            cnf.set('Seafile', 'token', token)
            with open(CONF_HOME, 'wb') as configfile:
                cnf.write(configfile)

        os.chmod(CONF_HOME, 0700)
        try:
            uid = os.environ['SUDO_UID']
        except KeyError:
            uid = os.getuid()

        os.chown(CONF_HOME, int(uid), -1)
        return

    def add(self, args):

        for f in args.files:
            if os.path.isdir(f):
                self.seafile_client.upload_folder(self.repo, '/'+self.hostname, os.path.abspath(f))
            elif os.path.isfile(f):
                self.seafile_client.upload_file(self.repo, '/'+self.hostname, os.path.abspath(f))

    def note(self, args):

        if not args.notes:
            text = sys.stdin.read()
            self.seafile_client.add_text(self.repo, NOTES_FILE, text)
        else:
            for f in args.notes:
                self.seafile_client.add_text(self.repo, NOTES_FILE, f)

    def last_command(self, args):

        bash_history = os.path.expanduser("~/.bash_history")
        last_command = os.popen("tail -1 " + bash_history).readlines()[0]

        self.seafile_client.add_text(self.repo, '/'+self.hostname+'_'+COMMAND_FILE_NAME, last_command)
        
class ClientHttpError(Exception):
    """This exception is raised if the returned http response is not as
    expected"""
    def __init__(self, code, message):
        super(ClientHttpError, self).__init__()
        self.code = code
        self.message = message

    def __str__(self):
        return 'ClientHttpError[%s: %s]' % (self.code, self.message)

class OperationError(Exception):
    """Expcetion to raise when an opeartion is failed"""
    pass

class DoesNotExist(Exception):
    """Raised when not matching resource can be found."""
    def __init__(self, msg):
        super(DoesNotExist, self).__init__()
        self.msg = msg

    def __str__(self):
        return 'DoesNotExist: %s' % self.msg

def raise_does_not_exist(msg):
    """Decorator to turn a function that get a http 404 response to a
    :exc:`DoesNotExist` exception."""
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ClientHttpError, e:
                if e.code == 404:
                    raise DoesNotExist(msg)
                else:
                    raise
        return wrapped
    return decorator

class Repo(object):
    """
    A seafile library
    """
    def __init__(self, repo_id, repo_name, repo_desc,
                 encrypted, owner, perm):
        self.id = repo_id
        self.name = repo_name
        self.desc = repo_desc
        self.encrypted = encrypted
        self.owner = owner
        self.perm = perm

    @classmethod
    def from_json(cls, repo_json):
        repo_json = utf8lize(repo_json)

        repo_id = repo_json['id']
        repo_name = repo_json['name']
        repo_desc = repo_json['desc']
        encrypted = repo_json['encrypted']
        perm = repo_json['permission']
        owner = repo_json['owner']

        return cls(repo_id, repo_name, repo_desc, encrypted, owner, perm)

class _SeafDirentBase(object):
    """Base class for :class:`SeafFile` and :class:`SeafDir`.
    It provides implementation of their common operations.
    """
    isdir = None

    def __init__(self, repo, path, object_id, size=0):
        """
        :param:`path` the full path of this entry within its repo, like
        "/documents/example.md"
        :param:`size` The size of a file. It should be zero for a dir.
        """
        self.repo = repo
        self.path = path
        self.id = object_id
        self.size = size

    @property
    def name(self):
        return posixpath.basename(self.path)


class SeafDir(_SeafDirentBase):
    isdir = True

    def __init__(self, *args, **kwargs):
        super(SeafDir, self).__init__(*args, **kwargs)
        self.entries = None
        self.entries = kwargs.pop('entries', None)

    def ls(self, force_refresh=False):
        """List the entries in this dir.
        Return a list of objects of class :class:`SeafFile` or :class:`SeafDir`.
        """
        if self.entries is None or force_refresh:
            self.load_entries()

        return self.entries



    def load_entries(self, dirents_json=None):
        if dirents_json is None:
            url = '/api2/repos/%s/dir/' % self.repo.id + querystr(p=self.path)
            dirents_json = self.client.get(url).json()

        self.entries = [self._load_dirent(entry_json) for entry_json in dirents_json]

    def _load_dirent(self, dirent_json):
        dirent_json = utf8lize(dirent_json)
        path = posixpath.join(self.path, dirent_json['name'])
        if dirent_json['type'] == 'file':
            return SeafFile(self.repo, path, dirent_json['id'], dirent_json['size'])
        else:
            return SeafDir(self.repo, path, dirent_json['id'], 0)

    @property
    def num_entries(self):
        if self.entries is None:
            self.load_entries()
        return len(self.entries) if self.entries is not None else 0
    
    def __str__(self):
        return 'SeafDir[repo=%s,path=%s,entries=%s]' % \
            (self.repo.id[:6], self.path, self.num_entries)

    __repr__ = __str__

class SeafFile(_SeafDirentBase):
    isdir = False
    def update(self, fileobj):
        """Update the content of this file"""
        pass

    def __str__(self):
        return 'SeafFile[repo=%s,path=%s,size=%s]' % \
            (self.repo.id[:6], self.path, self.size)


    __repr__ = __str__


    
class Group(object):
    def __init__(self, group_id, group_name):
        self.group_id = group_id
        self.group_name = group_name

class Seafile(object):

    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.auth_headers = {'Authorization': 'token '+token}
        # self.seafile_client = client.SeafileApiClient(self.url, token=self.token)
        self.project_group_name = PROJECT_GROUP_NAME
        self.project_group = None

    def set_project_group(self):
        self.project_group = self.get_group(self.project_group_name)

    def call_base(self, path, req_type='get', data={}, req_params={}, files={}):
        
        method = getattr(requests, req_type)
        if not path.startswith('http'):
            url = self.url+'/api2/'+path
            if req_params:
                parms = urllib.urlencode(req_params)
                url = url + '?' + parms
        else:
            url = path

        logging.info('Issuing '+req_type.upper()+' request to: '+url)
        if data:
            temp = dict(data)
            if temp.get('password', None):
                temp['password'] = 'xxxxxxxxx'
            logging.info('Data: '+str(temp))

        resp = method(url, headers=self.auth_headers, data=data, files=files)
        expected = (200,)
        if resp.status_code not in expected:
            msg = 'Expected %s, but get %s' % \
                  (' or '.join(map(str, expected)), resp.status_code)
            raise ClientHttpError(resp.status_code, msg)
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

    def call_delete(self, file_obj):
        suffix = 'dir' if file_obj.isdir else 'file'
        url = 'repos/%s/%s/' % (self.repo.id, suffix) + querystr(p=self.path)
        resp = self.call_base(url, req_type='delete')
        return resp

    def mkdir(self, dir_obj, name):
        """Create a new sub folder right under this dir.
        Return a :class:`SeafDir` object of the newly created sub folder.
        """
        path = posixpath.join(dir_obj.path, name)
        url = 'repos/%s/dir/' % dir_obj.repo.id + querystr(p=path, reloaddir='true')
        postdata = {'operation': 'mkdir'}
        resp = self.call_base(url, data=postdata, req_type='post')
        self.id = resp.headers['oid']
        return SeafDir(dir_obj.repo, path, ZERO_OBJ_ID)

    def upload(self, dir, fileobj, filename):
        """Upload a file to this folder.
        :param:dir the target folder
        :param:fileobj :class:`File` like object
        :param:filename The name of the file
        Return a :class:`SeafFile` object of the newly uploaded file.
        """
        if isinstance(fileobj, str):
            fileobj = io.BytesIO(fileobj)
        upload_url = self.call_get_upload_link(dir.repo)
        files = {
            'file': (filename, fileobj),
            'parent_dir': dir.path,
        }
        self.call_base(upload_url, files=files, req_type='post')
        return self.call_get_file(dir.repo, posixpath.join(dir.path, filename))


    def call_repo_getFile(self, repo, path):
        """Get the file object located in `path` in this repo.
        Return a :class:`SeafFile` object
        """
        assert path.startswith('/')
        url = 'repos/%s/file/detail/' % repo.id
        query = '?' + urlencode(dict(p=path))
        file_json = self.call_base(url+query).json()

        return SeafFile(repo, path, file_json['id'], file_json['size'])

    def upload_local_file(self, dir, filepath, name=None):
        """Upload a file to this folder.
        :param:dir The target directory
        :param:filepath The path to the local file
        :param:name The name of this new file. If None, the name of the local file would be used.
        Return a :class:`SeafFile` object of the newly uploaded file.
        """
        name = name or os.path.basename(filepath)
        with open(filepath, 'r') as fp:
            return self.upload(dir, fp, name)

                
    def call_get_upload_link(self, repo):
        
        url = 'repos/%s/upload-link/' % repo.id
        resp = self.call_base(url)
        return re.match(r'"(.*)"', resp.text).group(1)

    
    def call_get_file_download_link(self, fileObj):
        url = 'repos/%s/file/' % fileObj.repo.id + querystr(p=fileObj.path)
        resp = self.call_base(url)
        return re.match(r'"(.*)"', resp.text).group(1)

    def call_get_file_content(self, fileObj):
        """Get the content of the file"""
        url = self.call_get_file_download_link(fileObj)
        return self.call_base(url).content


    def add_text(self, repo, file, text):

        dir = ''
        try:
            file_obj = self.call_get_file(repo, file)
            content = self.call_get_file_content(file_obj)
        except DoesNotExist:
            content = ''

        dir = os.path.dirname(file)
        if not dir:
            dir = "/"
        filename = os.path.basename(file)

        temp = tempfile.NamedTemporaryFile()
        try:
            temp.write(content+'\n\n'+text)
            temp.seek(0)
            
            self.upload_file(repo, dir, temp.name, remote_name=filename)
        finally:
            temp.close()
        return content


    def get_group(self, group_name):
        """Returns the group object for the group with the given name."""

        response = self.call_base('groups/').json()['groups']
        matches = [g for g in response if g['name'] == self.project_group_name]
        if len(matches) == 0 or len(matches) > 1:
            return None
        else:
            g = Group(matches[0]['id'], matches[0]['name'])
            return g

    def share_repo_with_group(self, repo, group, permission):
        """Share a repo with a group"""

        data = {
            'share_type': 'group',
            'group_id': self.project_group.group_id,
            'permission': permission
        }
        return self.call_base('shared-repos/'+repo.id+'/', req_params=data, req_type='put')

    def call_list_repos(self):
        repos_json = self.call_base('repos/').json()
        return [Repo.from_json(j) for j in repos_json]

    def call_create_repo(self, name, desc, password=None):
        
        data = {'name': name, 'desc': desc}
        if password:
            data['passwd'] = password
        repo_json = self.call_base('repos/', data=data, req_type='post').json()
        return self.call_get_repo(repo_json['repo_id'])

    @raise_does_not_exist('The requested library does not exist')
    def call_get_repo(self, repo_id):
        """Get the repo which has the id `repo_id`.
        Raises :exc:`DoesNotExist` if no such repo exists.
        """
        repo_json = self.call_base('repos/' + repo_id).json()
        return Repo.from_json(repo_json)

    def call_delete_repo(self, repo):

        resp = self.call_base('repos/'+repo.id+'/', req_type='delete')
        return resp.text == "success"
        

    def get_repo(self, proj_name):
        """Returns the repo object for this project, creates a new one if none exists yet.

        Returns None if more than one repo exists with that name.
        """

        all_repos = self.call_list_repos()
        r = [r for r in all_repos if r.name == proj_name]

        if len(r) > 1:
            return None
        elif len(r) == 0:
            r = self.call_create_repo(proj_name, 'Library for project: '+proj_name)
            self.share_repo_with_group(r, self.project_group, 'rw')
            return r
        else:
            return r[0]

    def create_empty_file(self, dir_obj, name):
        """Create a new empty file in this dir.
        Return a :class:`SeafFile` object of the newly created file.
        """
        # TODO: file name validation
        path = posixpath.join(dir_obj.path, name)
        url = 'repos/%s/file/' % self.repo.id + querystr(p=path, reloaddir='true')
        postdata = {'operation': 'create'}
        resp = self.call_base(url, data=postdata, req_type='post')
        self.id = resp.headers['oid']
        self.load_entries(resp.json())
        return SeafFile(self.repo, path, ZERO_OBJ_ID, 0)

    @raise_does_not_exist('The requested dir does not exist')
    def call_get_dir(self, repo, path):
        """Get the dir object located in `path` in this repo.
        Return a :class:`SeafDir` object
        """
        
        assert path.startswith('/')
        url = 'repos/%s/dir/' % repo.id
        query = '?' + urlencode(dict(p=path))
        resp = self.call_base(url + query)
        dir_id = resp.headers['oid']
        dir_json = resp.json()
        dir = SeafDir(repo, path, dir_id)
        dir.load_entries(dir_json)
        return dir

    @raise_does_not_exist('The requested file does not exist')
    def call_get_file(self, repo, path):
        """Get the file object located in `path` in this repo.
        Return a :class:`SeafFile` object
        """
        
        assert path.startswith('/')
        url = 'repos/%s/file/detail/' % repo.id
        query = '?' + urlencode(dict(p=path))
        file_json = self.call_base(url+query).json()

        return SeafFile(repo, path, file_json['id'], file_json['size'])


    def get_directory(self, repository, path):
        """Returns the directory object for the given path, creates it (and all it's parents) if necessary."""
        try:
            if path != '/':
                # otherwise 2 directories are created
                path = path.rstrip('/')

            dir = self.call_get_dir(repository, path)
        except DoesNotExist:
            parent_child = os.path.split(path)
            parent = parent_child[0]
            child = parent_child[1]
            parent_dir = self.get_directory(repository, parent)
            return self.mkdir(parent_dir, child)

        return dir

    def get_update_link(self, repo):
        """Get the link to update a file on the repo."""

        response = self.call_base('repos/'+repo.id+'/update-link/')
        return response.text

    def upload_folder(self, repo, parent_path, folderpath, remote_name=None):
        """Upload a folder to this remote dir.
        :param:repo the repository
        :param:parent_path the parent_path where the file should be copied to
        :param:folderpath The path to the local folder
        :param:name The name of the new remote folder, if None, the name of the local folder will be used
        """
        name = remote_name or os.path.basename(folderpath)

        for dirName, subdirList, fileList in os.walk(folderpath):
            print ('Found dir: %s' % dirName)
            for fname in fileList:
                remote = dirName+'/'+fname
                print ('\tUploading: %s' % remote)
                # TODO support remote paths other then the mirrored local one
                self.upload_file(repo, parent_path, remote)
                # time.sleep(1)

    def upload_file(self, repo, parent_path, file, remote_name=file):
        """Uploads or updates the file to/on the repo.
        :param:repo the repository
        :param:parent_path the parent_path where the file should be copied to
        :param:file the local file path
        :param:remote_name the remote filename/path (ontop of parent_path)
        """

        if os.path.islink(file):
            print file+" is link, ignoring..."
            return None

        full_path = os.path.join(parent_path, remote_name)
        try:
            self.call_get_file(repo, full_path)
        except DoesNotExist:
            # print "Uploading file..."
            path = os.path.dirname(full_path)
            dir = self.get_directory(repo, path)
            return self.upload_local_file(dir, file, name=full_path)

        # in case of file exists already, we just update
        link = self.get_update_link(repo).strip('"')
        files_to_upload = {'file': open(file, 'rb'),
                           'target_file': full_path}
        # file = open(file, 'rb')
        response = self.call_base(link, files=files_to_upload, req_type='post')
        return response

# Init ======================================================
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

class ProjectConfig(object):

    def __init__(self):
        config = ConfigParser.SafeConfigParser()

        try:
            user = os.environ['SUDO_USER']
            conf_user = os.path.expanduser('~'+user+"/."+CONF_FILENAME)
            candidates = [CONF_SYS, conf_user, CONF_HOME]
        except KeyError:
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
        try:
            user = os.environ['SUDO_USER']
            conf_user = os.path.expanduser('~'+user+"/."+CONF_FILENAME)
            candidates = [conf_user, CONF_HOME]
        except KeyError:
            candidates = [CONF_HOME]
            
        config.read(candidates)

        try:
            self.token = config.get('Seafile', 'token')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            self.token = None

# helpers
def utf8lize(obj):
    if isinstance(obj, dict):
        temp = {}
        for k, v in obj.iteritems():
            temp[k] = to_utf8(v)
        return temp

    if isinstance(obj, list):
        temp = []
        for x in obj:
            temp.append(to_utf8(x))
        return temp

    if isinstance(obj, unicode):
        return obj.encode('utf-8')

    return obj

def to_utf8(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf-8')
    return obj

def querystr(**kwargs):
    return '?' + urlencode(kwargs)

def run():
    CliCommands()
