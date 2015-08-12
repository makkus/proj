Pyroji
======

Pyroji is a helper script to manage files and information related to projects. Everything is stored within a folder structure and uploaded to a Seafile server (for now, other backends possible in the future).

It's main purpose is to make it possible to quickly record files and comments about a project into a common space, without having to do a lot of ssh magic and such. At the moment I use Seafile (http://seafile.com) as a storage backend because it has a nice web-API, as well as functional desktop clients that enable syncing of project folders to ones' workstation.

The overall workflow is like this (using a VM project as example):

* Create VM
* install pyroji
* 'init' pyroji
* work on setting up the VM, while doing that issue commands like
- 'pyroji add' (to add a files or folders)
- 'pyroji note' (to make a note regarding the setup process)
- 'pyroji add_command' (to record a command that was used in the setup process)
* the notes can be used to create more in-depth documentation later on, or might be sufficient for documentation purposes
* if further work is required, the library can be synced to ones local workstation, which makes editing the *notes.md* file easier or the creation of a more in depth doc file (for example)
* files related to a project can easily be shared with users, also Seafile can be used as an 'upload-only' space where users can upload required files related to a project.


Pyroji uses code from python-seafile (https://github.com/haiwen/python-seafile), but for now everything is contained in one .py file, with as little as possible dependencies so deployment on weird systems might be easier.


# Pip requirements

- argparse
- requests

Note: if you get error messages about SSL, pin version of requests to 2.5.3: pip install requests==2.5.3

# Install

    (sudo) pip install https://github.com/makkus/pyroji/archive/master.zip


# Usage

Create a user account on your seafile server (default: https://seafile.cer.auckland.ac.nz) and a group called 'Projects' if it doesn't exist yet (hardcoded for now). Become member of that group.

Note: don't use the Shibboleth option to create an account, since those accounts can't use the web-API.

Then, on the machine where you want to use *pyroji*, execute:

    pyroji init

    Seafile url [https://seafile.cer.auckland.ac.nz]: 
	Please enter your username: makkus@gmail.com
	Password: 
	Project name: <your_unique_project_name>
	Default folder for uploads and notes []: <leave blank for root folder, or maybe hostname or other identifier>


This will write a file '*.pyroji.conf*' into your home directory. When the first command is called now, a library will be created on the remote server (if it doesn't exist yet), with the name of the project. When uploading a file, or adding a note into a subfolder (or the default folder), those will be created automatically.

# Commands

Probably a good idea to alias those in your shell rc.

## help

    pyroji -h

## init

Init a machine with default credentials and folders

	pyroji init

## add

Add or update a local file or folder to the remote library.

    pyroji add

By default, the path configured in *'~/.pyroji.conf'* is used as the remote root for the upload(s), this can be overwritten with the '*--folder*' flag (must be specified before the '*add*' command). For projects with several hosts, it makes sense to have one folder per host.
It is possible to preserve the parent folder structure of uploaded files and folders with the '*--subfolders*' flag (specified after the '*add*' command).

## note

Add a note to the project documentation file.

    pyroji note "<a note>"
	# cat the input of a file into a note
	cat <note_file> | pyroji note
	# this will prompt for input
	pyroji note
	# this will write into a note file called 'project.md' in the root of the library
	pyroji --folder="" note --filename "project.md" <a note>

The default note file is called *'notes.md'*, and is located in the default folder that is configured for this machine (again, can be overwritten with *'--folder'* flag). To change the name, use the *'--filename'* commandline option.

## add_command

This is similar to the *note* command (the same defaults and options are available), but will add the text indented with 4 white spaces, so it will be displayed as code in a markdown file. To add a command before the command, use the *'--comment'* commandline option.

    # add a command
    pyroji add_command -c "List a directory" ls -lah
	# add a command from shell history
	pyroji add_command -c "Some random optional comment"

Note: adding a command from shell history will only work if the shell writes the history file after every command ('shopt -s histappend; PROMPT_COMMAND="history -a;$PROMPT_COMMAND"' in bash, for example). When using sudo, use it to go into a shell like so: 'sudo -E bash', or make sure to not use sudo for the pyroji command, since the history won't be populated in that case.

# TODOs

- write tests
- add ignore option for file uploads
- create template folders (including files) for new projects
- enable multiple project defaults (like python environments), and create a command to easily switch between them (i.e. *pyroji project <projectname>*)
- enable downloading of files
