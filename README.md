Pyroji
======

Pyroji is a helper script to manage files and information related to projects. Everything is stored within a folder structure and uploaded to a Seafile server (for now, other backends possible in the future).

Pyroji uses code from python-seafile (https://github.com/haiwen/python-seafile), but for now everything is contained in one .py file, with as little as possible dependencies so deployment on weird systems might be easier.


# Pip requirements

- argparse
- requests

Note: if you get error messages about SSL, pin version of requests to 2.5.3: pip install requests==2.5.3

# Install

    (sudo) pip install https://github.com/makkus/pyroji/archive/master.zip


# Usage

Create a user account on your seafile server (default: https://seafile.cer.auckland.ac.nz) and a group called 'Projects' (hardcoded for now).

Then, on the machine where you want to use *pyroji*, execute:

    pyroji init

    Seafile url [https://seafile.cer.auckland.ac.nz]: 
	Please enter your username: makkus@gmail.com
	Password: 
	Project name: <your_unique_project_name>
	Default folder for uploads and notes []: <leave blank for root folder, or maybe hostname or other identifier>


This will write a file '*.pyroji.conf*' into your home directory. When the first command is called now, a library will be created on the remote server (if it doesn't exist yet), with the name of the project. When uploading a file, or adding a note into a subfolder (or the default folder), those will be created automatically.

# Commands

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
	cat <note_file> | pyroji note
	pyroji note  # this will prompt for input

The default note file is called *'notes.md'*, and is located in the default folder that is configured for this machine (again, can be overwritten with *'--folder'* flag). To change the name, use the *'--filename'* commandline option.

## add_command

This is similar to the *note* command (the same defaults and options are available), but will add the text indented with 4 white spaces, so it will be displayed as code in a markdown file. To add a command before the command, use the *'--comment'* commandline option.

    pyroji add_command -c "List a directory" ls -lah

