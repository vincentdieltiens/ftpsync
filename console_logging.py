# -*- coding: utf-8 -*-

import logging

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

class ColorFormatter(logging.Formatter):
	def __init__(self, msg):
		self.colors = {
			'WARNING': YELLOW,
			'INFO': WHITE,
			'DEBUG': BLUE,
			'CRITICAL': YELLOW,
			'ERROR': RED,
			'OK': GREEN
		}
		logging.Formatter.__init__(self, msg)
	
	def format(self, record):
		levelname = record.levelname
		col = ""
		if levelname in self.colors:
			col_code = (30 + self.colors[levelname]);
			record.levelname = "\033[1m%s\033[0;%sm" % (levelname, col_code)
			col = "\033[0;%dm" % (col_code)
		return "%s%s%s" % (col, logging.Formatter.format(self, record), "\033[0m")
		
class Logger(logging.Logger):
	def __init__(self, name):
		logging.Logger.__init__(self, name, logging.DEBUG)
		logging.addLevelName(60, 'OK')
		
	def ok(self, msg):
		self.log(60, msg)

#logging.setLoggerClass(ColoredLogger)