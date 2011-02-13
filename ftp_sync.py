#!/usr/bin/python
# -*- coding: utf-8 -*-
from ftplib import FTP, error_perm
import glob
import os
import os.path
import re
import fnmatch
import time
import getpass

import yaml

import logging
import console_logging
import yaml_config

logger = None
yaml_reader = None

def main():
  global logger, reader
  
  init_logger()
  
  yaml_reader = yaml_config.ConfigReader('config.yml')

  # connect to the FTP server
  ftp = FTP(yaml_reader.get('ftp:host'))
  if yaml_reader.exist('ftp:password') and yaml_reader.get('ftp:password') != None:
    password = yaml_reader.get('ftp:password')
  else:
    password = getpass.getpass("Enter your FTP password : ")

  ftp.login(yaml_reader.get('ftp:user'), password)
  
  # Get working directory
  working_dir = os.getcwd()
  
  # Browse directories to synchronize et sync it over FTP
  
  for i, directories in enumerate(yaml_reader.get('directories')):
    local_dir = directories.get('local')
    remote_dir = directories.get('remote')
    ignore = directories.get('ignore')
    remote_ignore = directories.get('remote_ignore')
    
    ftp_sync = FtpSync(ftp, local_dir, remote_dir, ignore, remote_ignore, logger, yaml_reader)
    ftp_sync.synchronize()

  # close the connection to the FTP server
  ftp.quit()

def init_logger():
  global logger
  
  logging.setLoggerClass(console_logging.Logger)
  
  logger = logging.getLogger('ftp_sync')
  
  handler = logging.StreamHandler()
  handler.setLevel(logging.INFO)
  
  formatter = console_logging.ColorFormatter('%(asctime)s %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  
  logger.addHandler(handler)
  logger.setLevel(logging.INFO)


class FtpSync():
  def __init__(self, ftp, local_dir, remote_dir, ignore_rules, remote_ignore_rules, logger, yaml_reader):
    
    if ignore_rules != None and type(ignore_rules) is not list:
      raise Exception("ignore_rules parameter must be a list, a tuple or None. %s (%s) found" % (type(ignore_rules), str(ignore_rules)))
    
    if remote_ignore_rules != None and type(remote_ignore_rules) is not list:
      raise Exception("remote_ignore_rules parameter must be a list, a tuple or None. %s (%s) found" % (type(remote_ignore_rules), str(ignore_rules)))
    
    self.base_local_dir = local_dir
    self.base_remote_dir = remote_dir
    self.local_dir = local_dir
    self.remote_dir = remote_dir
    self.ignore_rules = ignore_rules
    self.remote_ignore_rules = remote_ignore_rules
    self.logger = logger
    self.ftp = ftp
    self.config = yaml_reader
  
  def setLogger(logger):
    self.logger = logger
  
  
  def synchronize(self):
    self._synchronize(self.local_dir, self.remote_dir)
  
  
  def _synchronize(self, local_dir, remote_dir):
    
    # Go to local dir
    os.chdir(local_dir)
    
    # Get local files list
    local_files = self._get_local_files()
      
    # Go to remote directory
    self.ftp.cwd(remote_dir)
    
    # Get remote files list
    remote_files = self._get_remote_files()
    
    
    
    self.logger.info('Synchronization of "%s" (%d) with "%s" (%d)' % 
      (os.getcwd(), len(local_files), remote_dir, len(remote_files)))
    
    # list of directories to sync after all files of the current directory are synchronized
    dirs_to_sync = []
    
    ##
    ## send files that are in local and not on the FTP server
    ##
    for i, local_file in enumerate(local_files):
      # if we ignore the current file, go to the next loop iteration
      if self.file_must_be_ignored(self.base_local_dir, local_dir, local_file, self.ignore_rules):
        file_type = 'file'
        if os.path.isdir(local_file):
          file_type = 'directory'
        self.logger.warning('Ignoring %s "%s/%s"' % (file_type, os.getcwd(), local_file))
        continue
    
      remote_file = self._search_local_file_in_remote_files(local_file, remote_files)
      if remote_file == None:
        if os.path.islink(local_file): # file is a symlink
          None
        elif os.path.isdir(local_file): # file is a directory
          self.logger.info('Creating remote directory "%s/%s"' % (remote_dir, local_file))
          try:
            self.ftp.mkd(local_file)
            dirs_to_sync.append(local_file)
          except error_perm, e:
            self.logger.error('Can\'t create the directory "%s/%s" : %s' % (remote_dir, local_file, str(e)))
        else: # file is a regular file
          self._upload_file(local_file, remote_dir)
      else:
        if os.path.islink(local_file): # file is a symlink
          real_file = os.path.abspath(os.path.join(os.path.dirname(local_file), os.readlink(local_file)))
          self.logger.warning('"%s/%s" is a Link to %s' % (local_dir, local_file, real_file))
          #dirs_to_sync.append(local_file)
          None
        elif os.path.isdir(local_file): # file is a directory
          #if remote_file.get('time') < time.localtime(os.path.getmtime(local_file)):
          dirs_to_sync.append(local_file)
          #else:
              #self.logger.ok('Ftp directory "%s/%s" is up-to-date' % (remote_dir, remote_file.get('filename')))
        else: # file is a regular file
          if remote_file.get('size') != os.path.getsize(local_file) or remote_file.get('time') < time.localtime(os.path.getmtime(local_file)):
            self._upload_file(local_file, remote_dir)
    
    ##
    ## delete files that are on the FTP server and not on local
    ##
    if self.config.get('strict'):
      for i, remote_file in enumerate(remote_files):
        in_local = remote_file.get('filename') in local_files
        must_ignore = self.file_must_be_ignored(self.base_remote_dir, remote_dir, remote_file.get('filename'), self.remote_ignore_rules)
        if not in_local and not must_ignore:
          delete = False
          if self.config.get('confirm_delete'):
            response = raw_input('Delete "%s/%s" from the FTP ? [n] ' % (remote_dir, remote_file.get('filename')))
            delete = (response == 'y')

          if delete:
            try:
              if remote_file.get('permissions')[0] == 'd':
                self._delete_ftp_directory(remote_file.get('filename'))
              else:
                self.ftp.delete(remote_file.get('filename'))
              self.logger.ok('"%s/%s" deleted' % (remote_dir, remote_file.get('filename')))
            except error_perm, e:
              self.logger.error('Can\'t delete "%s/%s" : %s' % (remote_dir, remote_file.get('filename') , str(e)))
    
    ##
    ## Trick that ensures that the date of last modification of the
    ## remote directory is updated
    ##
    #t = str(int(time.time()))
    #self.ftp.mkd(t)
    #self.ftp.rmd(t)

    ##
    ## Recursive synchronization
    ##
    pwd = os.getcwd()
    for i, dirname in enumerate(dirs_to_sync):
      local_dir2 = os.path.join(os.getcwd(), dirname)
      remote_dir2 = os.path.join(self.ftp.pwd(), dirname)
      self._synchronize(local_dir2, remote_dir2)
    
    # Go up remote
    self.ftp.cwd('..')
    
    # Go up local
    os.chdir('..')
  
  
  def _get_local_files(self):
    return glob.glob(self.config.get('filter')) 
  
  def _delete_ftp_directory(self, directory):
    cwd = self.ftp.pwd()
    self.ftp.cwd(directory)
    
    remote_files = self._get_remote_files()
    for i, remote_file in enumerate(remote_files):
      if remote_file.get('permissions')[0] == 'd':
        self._delete_ftp_directory(remote_file.get('filename'))
      else:
        self.ftp.delete(remote_file.get('filename'))
        self.logger.ok('file "%s/%s" deleted' % (cwd, remote_file.get('filename')))
      
    self.ftp.cwd(cwd)
    self.ftp.rmd(directory)
    self.logger.ok('Directory "%s/%s" delete' % (cwd, directory))

  def _get_remote_files(self):
    remote_files_lines = []
    self.ftp.dir(remote_files_lines.append)
    remote_files = []
    for i, line in enumerate(remote_files_lines):
      values = self._parse_line(line)
      if values.get('filename') not in ('.', '..'):
        remote_files.append(values)
    return remote_files
  

  def _search_local_file_in_remote_files(self, local_file, remote_files):
    # check if current local file is on the ftp
    for j, remote_file in enumerate(remote_files):
      if remote_file['filename'] == local_file:
        return remote_file
    return None
  
  
  def _upload_file(self, local_file, remote_dir):
    remote_filename = local_file
    cwd = os.getcwd()
    try:
      file = open(local_file, 'rb')
      self.ftp.storbinary("STOR %s" % (local_file), file)
      file.close()
      self.logger.info('"%s/%s" uploaded into "%s/%s"' % (cwd, local_file, self.ftp.pwd(), remote_dir))
    except error_perm, e:
      self.logger.error('Can\'t upload "%s/%s" into "%s" : %s' % (cwd, local_file, remote_dir, str(e)))
      file.close()
  

  def _parse_line(self, line):
    
    format = self.config.get('dir_ftp_line_parser:format') % self.config.get('dir_ftp_line_parser:fields')
    m = re.search(format, line)
    if m:
      infos = m.groupdict()
      if infos['year'] == None:
        infos['year'] = time.strftime("%Y")
      else:
        infos['hour'] = '0'
        infos['minute'] = '0'

      remote_time_str = "%s/%s/%s %s:%s" % (infos['day'], infos['month'], infos['year'], infos['hour'], infos['minute'])
      infos['time'] = time.strptime(remote_time_str, "%d/%b/%Y %H:%M")

      infos['size'] = int(infos['size'])

      return infos
    return None
  

  def file_must_be_ignored(self, base_dir, dir, filename, ignore_rules):
    if ignore_rules == None:
      return False
    for j, ignore_rule in enumerate(ignore_rules):
      #print "ignore rule : "+ignore
      if re.search("(\[|\]|\*|\?)", ignore_rule):
        if os.sep in ignore_rule:
          #print "is path fnmatch"
          if fnmatch.fnmatch(os.path.join(os.getcwd(), filename), os.path.join(base_dir, ignore_rule)):
            return True
        else: 
          #print "base fnmatch("+filename+", "+ignore+")"
          if fnmatch.fnmatch(filename, ignore_rule):
            return True
      else:
        if os.sep in ignore_rule:
          #print "Compare '%s' with '%s'" % (os.path.join(base_dir, ignore_rule), os.path.join(os.getcwd(), filename))
          if os.path.join(base_dir, ignore_rule) == os.path.join(os.getcwd(), filename):
            return True
        else:
          if filename == ignore_rule:
            return True
    return False
  

if __name__ == "__main__":
  main()