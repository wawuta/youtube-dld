#!/usr/bin/env python
# -*- coding: utf-8 -*-

import htmlentitydefs
import httplib
import math
import netrc
import os
import os.path
import re
import socket
import string
import sys
import time
import urllib
import urllib2

std_headers = {
    'User-Agent': 'UserAgent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9) Gecko/2008052906 Firefox/3.0',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
    'Accept': 'text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
    'Accept-Language': 'en-us,en;q=0.5',
}

simple_title_chars = string.ascii_letters.decode('ascii') + string.digits.decode('ascii')

class FileDownloader(object):
    ''' File Downloader class.

    File downloader objects are the ones responsible of downloading the
    actual video file and writing it to disk if the user has requested
    it, among some other tasks. In most cases there should be one per
    program. As, given a video URL, the downloader doesn't know how to
    extract all the needed information, task that InfoExtractors do, it
    has to pass the URL to one of them.

    For this, file downloader objects have a method that allows
    InfoExtractors to be registered in a given order. When it is passed
    a URL, the file downloader handles it to the first InfoExtractor it
    finds that reports being able to handle it. The InfoExtractor returns
    all the information to the FileDownloader and the latter downloads the
    file or does whatever it's instructed to do.

    File downloaders accept a lot of parameters. In order not to saturate
    the object constructor with arguments, it receives a dictionary of
    options instead. These options are available through the get_params()
    method for the InfoExtractors to use. The FileDownloader also registers
    itself as the downloader in charge for the InfoExtractors that are
    added to it, so this is a "mutual registration".

    Available options:

    username:   Username for authentication purposes.
    password:   Password for authentication purposes.
    usenetrc:   Use netrc for authentication instead.
    quiet:      Do not print messages to stdout.
    simulate:   Do not download the video files
    format:     Video format code.
    outtmpl:    Template for output names.

    '''

    _params = None
    _ies = []

    def __init__(self, params):
        self._ies = []
        self.set_params(params)

    @staticmethod
    def pmkdir(filename):
        """Create directory components in filename. Similar to Unix "mkdir -p"."""
        components = filename.split(os.sep)
        aggregate = [os.sep.join(components[0:x]) for x in xrange(1, len(components))]
        for dir in aggregate:
            if not os.path.exists(dir):
                os.mkdir(dir)

    @staticmethod
    def format_bytes(bytes):
        if bytes is None:
            return 'N/A'
        if bytes == 0:
            exponent = 0
        else:
            exponent = long(math.log(float(bytes), 1024.0))
        suffix = 'bkMGTPEZY'[exponent]
        converted = float(bytes) / float(1024**exponent)
        return '%.2f%s' % (converted, suffix)

    @staticmethod
    def calc_percent(byte_counter, data_len):
        if data_len is None:
            return '---.-%'
        return '%6s' % ('%3.1f%%' % (float(byte_counter) / float(data_len) * 100.0))

    @staticmethod
    def calc_eta(start, now, total, current):
        if total is None:
            return '--:--'
        dif = now - start
        if current == 0 or dif < 0.001:
            return '--:--'
        rate = float(current) / dif
        eta = long((float(total)- float(current)) / rate)
        (eta_mins, eta_secs) = divmod(eta, 60)
        if eta_mins > 99:
            return '--:--'
        return '%02d:%02d' % (eta_mins, eta_secs)

    @staticmethod
    def calc_speed(start, now, bytes):
        dif = now - start
        if bytes == 0 or dif < 0.001:
            return '%10s' % '---b/s'
        return '%10s' % ( '%s/s' % FileDownloader.format_bytes(float(bytes) / dif))

    @staticmethod
    def best_block_size(elapsed_time, bytes):
        new_min = max(bytes / 2.0, 1.0)
        new_max = min(max(bytes * 2.0, 1.0), 4194304)
        if elapsed_time < 0.001:
            return int(new_max)
        rate = bytes / elapsed_time
        if rate > new_max:
            return int(new_max)
        if rate < new_min:
            return int(new_min)
        return int(rate)

    def set_params(self, params):
        '''Sets parameters.'''
        if type(params) != dict:
            raise ValueError('params: dictionary expected')
        self._params = params

    def get_params(self):
        '''get parameters.'''
        return self._params

    def add_info_extractor(self, ie):
        '''Add an infoExtractor object to the end of the list.'''
        self._ies.append(ie)
        ie.set_downloader(self)

    def to_stdout(self, message, skip_eol=False):
        '''Print message to stdout if not in quiet mode.'''
        if not self._params.get('quiet', False):
            sys.stdout.write('%s%s' % (message, ['\n', ''][skip_eol]))
            sys.stdout.flush()


    def to_stderr(self, message):
        '''Print message to stderr.'''
        sys.stderr.write('%s\n' % message)

    def download(self, url_list):
        '''Download a given list of URLs.'''
        for url in url_list:
            suitable_found = False
            for ie in self._ies:
                if not ie.suitable(url):
                    continue
                # Suitable InfoExtractor found
                suitable_found = True
                results = [x for x in ie.extract(url) if x is not None]

                if (len(url_list) > 1 or len(results) > 1) and re.search(r'%\(.+?\)s', self._params['outtempl']) is None:
                    sys.exit('ERROR: fixed output name but more than one file to download')


                if self._params.get('simulate', False):
                    continue

                for result in results:
                    if result is None:
                        continue
                    try:
                        filename = self._params['outtmpl'] % result
                    except (KeyError), err:
                        self.to_stderr('ERROR: invalid output template: %s' % str(err))
                        continue
                    try:
                        self.pmkdir(filename)
                    except (OSError, IOError), err:
                        self.to_stderr('ERROR: unable to create directories: %s\n' % str(err))
                        continue
                    try:
                        outstream = open(filename, 'wb')
                    except (OSError, IOError), err:
                        self.to_stderr('ERROR: unable to open for writing: %s\n' % str(err))
                        continue
                    try:
                        self._do_download(outstream, result['url'])
                        outstream.close()
                    except (OSError, IOError), err:
                        self.to_stderr('ERROR: unable to write video data: %s\n' % str(err))
                        continue
                    except (urllib2.URLError, httplib.HTTPException, socket.error), err:
                        self.to_stderr('ERROR: unable to download video data: f%s\n' % str(err))
                        continue
                break
            if not suitable_found:
                self.to_stderr('ERROR: no suitable InfoExtractor: %s\n' % url)

    def _do_download(self, stream, url):
        request = urllib2.Request(url, None, std_headers)
        data = urllib2.urlopen(request)
        data_len = data.info().get('Content-length', None)
        data_len_str = self.format_bytes(data_len)
        byte_counter = 0
        block_size = 1024
        start = time.time()
        while True:
            percent_str = self.calc_percent(byte_counter, data_len)
            eta_str = self.calc_eta(start, time.time(), data_len, byte_counter)
            speed_str = self.calc_speed(start, time.time(), byte_counter)

            self.to_stdout('\r[download] %s of %s at %s ETA %s' %
                (percent_str, data_len_str, speed_str, eta_str), skip_eol=True)


            before = time.time()
            data_block = data.read(block_size)
            after = time.time()
            data_block_len = len(data_block)
            if data_block_len == 0:
                break
            byte_counter += data_block_len
            stream.write(data_block)
            block_size = self.best_block_size(after - before, data_block_len)

        self.to_stdout('')
        if data_len is not None and str(byte_counter) != data_len:
            raise ValueError('Content too short: %s/%s bytes' % (byte_counter, data_len))

class InfoExtractor(object):
    '''Information Extractor class.

    Information extractors are the classes that, given a URL, extract
    information from the video (or videos) the URL refers to. This
    information includes the real video URL, the video title and simplified
    title, author and others. It is returned in a list of dictionaries when
    calling its extract() method. It is a list because a URL can refer to
    more than one video (think of playlists). The dictionaries must include
    the following fields:

    id:        Video identifier.
    url:        Final video URL.
    uploader:    Nickname of the video uploader.
    title:        Literal title.
    stitle:        Simplified title.
    ext:        Video filename extension.

    Subclasses of this one should re-define the _real_initialize() and
    _real_extract() methods, as well as the suitable() static method.
    Probably, they should also be instantiated and added to the main
    downloader.
    '''

    _ready = False
    _downloader = None

    def __init__(self, downloader = None):
        '''Constructor. Receives an optional downloader.'''
        self._ready = False
        self.set_downloader(downloader)

    @staticmethod
    def suitable(url):
        '''Receives a URL and returns True if suitable for this IE.'''
        return True

    def initialize(self):
        '''Initializes an instance (login, etc).'''
        if not self._ready:
            self._real_initialize()
            self._ready = True

    def extract(self, url):
        '''Extracts URL information and returns it in list of dicts.'''
        self.initialize()
        return self._real_extract(url)

    def set_downloader(self, downloader):
        '''Sets the downloader for this IE.'''
        self._downloader = downloader

    def to_stdout(self, message):
        if self._downloader is None or not self._downloader.get_params().get('quiet', False):
            print message

    def to_stderr(self, message):
        sys.stderr.write('%s\n' % message)

    def _real_initialize(self):
        '''Real initialization process. Redefine in subclasses.'''
        pass
    def _real_extract(self, url):
        '''Real extraction process. Redefine in subclasses.'''
        pass

class YoutubeIE(InfoExtractor):
    '''Infomation extractor for youtube.com.'''

    _LOGIN_URL = 'http://www.youtube.com/login?next=/'
    _AGE_URL = 'http://www.youtube.com/verify_age?next_url=/'
    _METRC_MACHINE = 'youtube'

    def _real_initialize(self):
        if self._downloader is None:
            return

        username = None
        password = None
        downloader_params = self._downloader.get_params()

        # Attempt to use provided username and password or .netrc data
        if downloader_params.get('username', None) is not None:
            username = downloader_params['username']
            password = downloader_params['password']
        elif downloader_params.get('usenetrc', False):
            try:
                info = netrc.netrc().authenticators(self._NETRC_MACHINE)
                if info is not None:
                    username = info[0]
                    password = info[2]
                else:
                    raise netrc.NetrcParseError('No authenticators for %s' % self._NETRC_MACHINE)
            except (IOError, netrc.NetrcParseError), err:
                self.to_stderr('WARNING: parsing .netrc: %s' % str(err))
                return

        if username is None:
            return

        #log in
        login_form = {'current_form':   'loginForm',
                      'next':           '/',
                      'action_login':   'log In',
                      'username':       username,
                      'password':       password,}
        request = urllib2.Request(self._LOGIN_URL, urllib.urlencode(login_form), std_headers)
        try:
            self.to_stdout('[youtube] Loggging in')
            login_results = urllib2.urlopen(request).read()
            if re.search(r'(?i)<form[^>]* name="loginForm"', login_results) is not None:
                self.to_stderr('WARNING: Unable to log in: bad username or password')
                return
        except (urllib2.URLError, httplib.HTTPException, socket.error), err:
            self.to_stderr('WARNING: Unable to log in: %s' % str(err))
            return

        # confirm age
        age_form = {
            'next_url':         '/',
            'action_confirm':   'confirm',
            }
        request = urllib2.Request(self._AGE_URL, urllib.urlencode(age_form), std_headers)
        try:
            self.to_stdout('[youtube] Confirming age')
            age_results = urllib2.urlopen(request).read()
        except (urllib2.URLError, httplib.HTTPException, socket.error), err:
            sys.exit('ERROR: Unable to confirm age: %s' % str(err))

    def _real_extract(self, url):
        #Extract video id form URL
        mobj = re.match(r'^((?:http://)?(?:\w+\.)?youtube\.com/(?:(?:v/)|(?:(?:watch(?:\.php)?)?\?(?:.+&)?v=)))?([0-9A-Za-z_-]+)(?(1).+)?$', url)
        if mobj is None:
            self.to_stderr('ERROR: Invalid URL: %s' % url)
            return [None]
        video_id = mobj.group(2)

        #Downloader parameters
        format_param = None
        if self._downloader is not None:
            params = self._downloader.get_params()
            format_param = params.get('format', None)

        #Extension
        video_extension = {18: 'mp4'}.get(format_param, 'flv')

        # Normalize URL, including format
        normalized_url = 'http://www.youtube.com/watch?v=%s' % video_id
        if format_param is not None:
            normalized_url = '%s&fmt=%s' % (normalized_url, format_param)
        request = urllib2.Request(normalized_url, None, std_headers)
        try:
            self.to_stdout('[youtube] %s: Downloading video webpage' % video_id)
            video_webpage = urllib2.urlopen(request).read()
        except (urllib2.URLError, httplib.HTTPException, socket.error), err:
            sys.exit('ERROR: Ubable to download video: %s' % str(err))
        self.to_stdout('[youtube] %s: Extracting video information' % video_id)

        # "t" param
        mobj = re.search(r', "t": "([^"]+)"', video_webpage)
        if mobj is None:
            self.to_stderr('ERROR: Unable to extract "t" parameter')
            return [None]
        video_real_url = 'http://www.youtube.com/get_video?video_id=%s&t=%s' %(video_id, mobj.group(1))
        if format_param is not None:
            video_real_url = '%s&fmt=%s' % (video_real_url, format_param)
        self.to_stdout('[youtube] %s: URL: %s' % (video_id, video_real_url))

        # uploader
        mobj = re.search(r'More From: ([^<]*)<', video_webpage)
        if mobj is None:
            self.to_stderr('ERROR: Unable to extract uploader nickname')
            return [None]
        video_uploader = mobj.group(1)

        # title
        mobj = re.search(r'(?im)<title>YouTube - ([^<]*)</title>', video_webpage)
        if mobj is None:
            self.to_stderr('ERROR: Unable to extract video title')
            return [None]
        video_title = mobj.group(1).decode('utf-8')
        video_title = re.sub(u'&(.+?);', lambda x: unichr(htmlentitydefs.name2codepoint[x.group(1)]), video_title)

        #simplified title
        simple_title = re.sub(u'([^%s]+)' % simple_title_chars, u'_', video_title)
        simple_title = simple_title.strip(u'_')

        # Return information
        return [{
                    'id':         video_id,
                    'url':        video_real_url,
                    'uploader':   video_uploader,
                    'title':      video_title,
                    'stitle':     simple_title,
                    'ext':        video_extension,
                    }]

if __name__ == '__main__':
    try:
        http_proxy = 'http://127.0.0.1:48102'
        https_proxy = 'https://127.0.0.1:48102'
        #General configureation
        urllib2.install_opener(urllib2.build_opener(urllib2.ProxyHandler({'http':   http_proxy,
                                                                          'https':  https_proxy,})))
        #urllib2.install_opener(urllib2.build_opener(urllib2.HTTPCookieProcessor()))

        #information extractors
        youtube_ie = YoutubeIE()

        #File downloader
        fd = FileDownloader({'usenetrc':    False,
                             'username':    'wawuta',
                             'password':    'qwerty112',
                             'quiet':       False,
                             'simulate':    True,
                             'format':      None,
                             'outtmpl':     '%(id)s.%(ext)s'})
        fd.add_info_extractor(youtube_ie)
        fd.download(['http://www.youtube.com/watch?v=IJyn3pRcy_Q',
                     'http://www.youtube.com/watch?v=DZRXe1wtC-M',])

    except KeyboardInterrupt:
        sys.exit('\nERROR: Interrupted by user')
















