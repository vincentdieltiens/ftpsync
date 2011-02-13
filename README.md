FtpSync
=======

This is the FtpSync, an open-source tool that let you to synchronize local directories that are on your
computer with remote directories that are on a FTP server

To use it :

	git clone git@github.com:and1hotsauce/ftpsync.git
	cd ftpsync
	cp config.sample.yml config.yml

Edit the config.yml file and change the values. After, run the synchronizer

	python ftp_sync.py
	

Tested on Mac OS X 10.5.8