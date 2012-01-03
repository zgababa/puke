#!/usr/bin/env python
# -*- coding: utf8 -*-

import urllib2
import hashlib

from puke.Console import *
from puke.FileSystem import *

class Cache:

	@staticmethod
	def fetchHttp(url):
		id = hashlib.sha256(url).hexdigest()

		if Cache.check(id):
			return Cache.getPath(id)
		
		try:
			handler = urllib2.build_opener()
			payload = handler.open(url).read()
		except Exception as error:
			console.fail('HTTP fail %s (%s)' % (url, error))
			return False

		return Cache.write(id, payload, url)


	@staticmethod
	def write(id, payload, info = None):

		writefile(join(".pukecache", "%s" % id), payload)

		if info:
			writefile(join(".pukecache", "%s.meta" % id), info)

		return Cache.getPath(id)
		
	@staticmethod
	def read(id):
		if not Cache.check(id):
			return None
		
		return readfile(join(".pukecache", "%s" % id))

	@staticmethod
	def check(id):
		return exists(join(".pukecache", "%s" % id))

	@staticmethod
	def getPath(id):
		return join(".pukecache", "%s" % id)

	@staticmethod
	def getInfo(id):
		if not exists(join(".pukecache","%s.meta" % id)):
			return ""
		
		return readfile(join(".pukecache", "%s.meta" % id))


	@staticmethod
	def clean():
		try:
			remove(".pukecache")
			return True
		except:
			return False