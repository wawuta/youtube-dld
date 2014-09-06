#!/usr/bin/env python
import hashlib
import subprocess

template = file('index.html.in', 'r').read()
version = subprocess.Popen(['./youtube-dld.py', '--version'], stdout =subprocess.PIPE).communicate()[0].strip()
data = file('youtube-dld.py', 'rb').read()
md5sum=hashlib.md5(data).hexdigest()
sha1sum=hashlib.sha1(data).hexdigest()
sha256sum=hashlib.sha256(data).hexdigest()
template = template.replace('@PROGRAM_VERSION@', version)
template = template.replace('@PROGRAM_MD5SUM@', md5sum)
template = template.replace('@PROGRAM_SHA1SUM@', sha1sum)
template = template.replace('@PROGRAM_SHA256SUM@', sha256sum)
file('index.html', 'w').write(template)
