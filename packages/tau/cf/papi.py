#"""
#@file
#@author John C. Linford (jlinford@paratools.com)
#@version 1.0
#
#@brief
#
#This file is part of TAU Commander
#
#@section COPYRIGHT
#
#Copyright (c) 2015, ParaTools, Inc.
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
# (1) Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
# (2) Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
# (3) Neither the name of ParaTools, Inc. nor the names of its contributors may
#     be used to endorse or promote products derived from this software without
#     specific prior written permission.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#"""

# System modules
import os
import glob
import sys
import shutil
import platform

# TAU modules
import cf
import logger
import util
import error
import environment


LOGGER = logger.getLogger(__name__)

DEFAULT_SOURCE = {None: 'http://icl.cs.utk.edu/projects/papi/downloads/papi-5.4.1.tar.gz'}

LIBS= {None: [ 'libpapi.a' ]}


class Papi(object):
  """
  Encapsulates a PAPI installation
  """
  def __init__(self, prefix, cxx, src, arch):
    self.src = src
    if not isinstance(src,bool) and src.lower() == 'download':
      try:
        self.src = DEFAULT_SOURCE[arch]
      except KeyError:
        self.src = DEFAULT_SOURCE[None]
    self.prefix = prefix
    self.cxx = cxx
    self.arch = arch
    if os.path.isdir(src):
      self.papi_prefix = src
    else:
      compiler_prefix = str(cxx.eid) if cxx else 'unknown'
      self.papi_prefix = os.path.join(prefix, 'papi', compiler_prefix)
    self.src_prefix = os.path.join(prefix, 'src')
    self.include_path = os.path.join(self.papi_prefix, 'include')
    self.bin_path = os.path.join(self.papi_prefix, 'bin')
    self.lib_path = os.path.join(self.papi_prefix, 'lib')

  def verify(self):
    """
    Returns true if if there is a working PAPI installation at `prefix` with a
    directory named `arch` containing  `lib` directories or
    raises a ConfigurationError describing why that installation is broken.
    """
    LOGGER.debug("Checking PAPI installation at '%s' targeting arch '%s'" % (self.papi_prefix, self.arch))
    if not os.path.exists(self.papi_prefix):
      raise error.ConfigurationError("'%s' does not exist" % self.papi_prefix)
    # Check for all libraries
    try:
      libraries = LIBS[self.arch]
      LOGGER.debug("Checking %s PAPI libraries" % libraries)
    except KeyError:
      libraries = LIBS[None]
      LOGGER.debug("Checking default PAPI libraries")
    for lib in libraries:
      path = os.path.join(self.lib_path, lib)
      if not os.path.exists(path):
        raise error.ConfigurationError("'%s' is missing" % path)
#      if not os.access(path, os.X_OK):
#        raise error.ConfigurationError("'%s' exists but is not executable" % path)

    LOGGER.debug("PAPI installation at '%s' is valid" % self.papi_prefix)
    return True

  def install(self, force_reinstall=False):
    """
    TODO: Docs
    """
    LOGGER.debug("Initializing PAPI at '%s' from '%s' with arch=%s" %
                 (self.papi_prefix, self.src, self.arch))

    # Check if the installation is already initialized
    if not force_reinstall:
      try:
        return self.verify()
      except error.ConfigurationError, err:
        LOGGER.debug(err)
    LOGGER.info('Starting PAPI installation')

    # Download, unpack, or copy PAPI source code
    dst = os.path.join(self.src_prefix, os.path.basename(self.src))
    try:
      util.download(self.src, dst)
      srcdir = util.extract(dst, self.src_prefix)
    except IOError as err:
      raise error.ConfigurationError("Cannot acquire source file '%s': %s" % (self.src, err),
                                     "Check that the file is accessable")
    finally:
      try: os.remove(dst)
      except: pass

    if not self.cxx:
      compiler_flag = ''
    else:
      family_flags = {'system': '',
                      'GNU': ['CC=gcc', 'CXX=g++'],
                      'Intel': ['CC=icc','CXX=icpc']
                     }
#                      'PGI': '-pgCC'}
      try:
        compiler_flag = family_flags[self.cxx['family']]
      except KeyError:
        LOGGER.warning("PAPI has no compiler flag for '%s'.  Using defaults." % self.cxx['family'])

    try:
      # Configure
      prefix_flag = '-prefix=%s' % self.papi_prefix
      cmd = ['./configure', prefix_flag] + compiler_flag
      LOGGER.info("Configuring PAPI...")
      if util.createSubprocess(cmd, cwd=srcdir, stdout=False):
        raise error.SoftwarePackageError('PAPI configure failed')

      # Build
      cmd = ['make', '-j4']
      LOGGER.info("Compiling PAPI...")
      if util.createSubprocess(cmd, cwd=srcdir, stdout=False):
        raise error.SoftwarePackageError('PAPI compilation failed.')

      # Install
      cmd = ['make', 'install']
      LOGGER.info("Installing PAPI...")
      if util.createSubprocess(cmd, cwd=srcdir, stdout=False):
        raise error.SoftwarePackageError('PAPI installation failed before verifcation.')

    except Exception as err:
      LOGGER.info("PAPI installation failed, cleaning up %s " % err)
      shutil.rmtree(self.papi_prefix, ignore_errors=True)
    finally:
      # Always clean up PAPI source
      LOGGER.debug('Deleting %r' % srcdir)
      shutil.rmtree(srcdir, ignore_errors=True)

    # Verify the new installation
    try:
      retval = self.verify()
      LOGGER.info('PAPI installation complete')
    except Exception as err:
      # Installation failed, clean up any failed install files
      shutil.rmtree(self.papi_prefix, ignore_errors=True)
      raise error.SoftwarePackageError('PAPI installation failed verifciation: %s' % err)
    else:
      return retval

  def applyCompiletimeConfig(self, opts, env):
    """
    TODO: Docs
    """
    env['PATH'] = os.pathsep.join([self.bin_path, env.get('PATH')])

  def getRuntimeConfig(self, opts, env):
    """
    TODO: Docs
    """
    pass


