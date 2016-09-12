# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, ParaTools, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# (1) Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
# (2) Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
# (3) Neither the name of ParaTools, Inc. nor the names of its contributors may
#     be used to endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
"""Software installation management."""

import os
import sys
import shutil
import hashlib
import multiprocessing
from lockfile import LockFile, NotLocked
from tau import logger, util
from tau.error import ConfigurationError
from tau.cf.storage.levels import ORDERED_LEVELS
from tau.cf.storage.levels import highest_writable_storage 
from tau.cf.software import SoftwarePackageError
from tau.cf.target import Architecture, OperatingSystem

LOGGER = logger.get_logger(__name__)


def parallel_make_flags(nprocs=None):
    """Flags to enable parallel compilation with `make`.
    
    Args:
        ncores (int): Number of parallel processes to use.  
                      Default is one less than the number of CPU cores.
                      
    Returns:
        list: Command line arguments to pass to `make`.
    """
    if not nprocs:
        nprocs = max(1, multiprocessing.cpu_count() - 1)
    return ['-j', str(nprocs)]


class Installation(object):
    """Encapsulates a software package installation.
    
    Attributes:
        name (str): Human readable name of the software package, e.g. 'TAU'.
        src (str): Path to a directory where the software has already been installed, 
                   or path to a source archive file or directory, or the special keyword 'download'.
        target_arch (str): Target architecture name.
        target_os (str): Target operating system name.
        compilers (InstalledCompilerSet): Compilers to use if software must be compiled.
        verify_commands (list): List of commands that are present in a valid installation.
        verify_libraries (list): List of libraries that are present in a valid installation.
        verify_headers (list): List of header files that are present in a valid installation.
        src_prefix (str): Directory containing package source code.
        is_installed (bool): True if all required commands and files were found, False otherwise.
    """

    def __init__(self, name, title, prefix, sources, target_arch, target_os, compilers, 
                 repos, commands, libraries, headers):
        """Initializes the installation object.
        
        To set up a new installation, pass `src` as a URL, file path, or the special keyword 'download'.
        Attributes `src` and `src_prefix` will be set to the appropriate paths.
        
        To set up an interface to an existing installation, pass ``src=/path/to/existing/installation``. 
        Attributes `src` and `src_prefix` will be set to None.
        
        Args:
            name (str): The package name, lowercase, alphanumeric with underscores.  All packages have a
                        corresponding ``tau.cf.software.<name>_installation`` module. 
            title (str): Human readable name of the software package, e.g. 'TAU Performance System' or 'Score-P'.
            prefix (str): Installation prefix within a storage container.
            sources (dict): Packages sources as strings indexed by package names as strings.  A source may be a 
                            path to a directory where the software has already been installed, or a path to a source
                            archive file, or the special keyword 'download'.
            target_arch (Architecture): Target architecture.
            target_os (OperatingSystem): Target operating system.
            compilers (InstalledCompilerSet): Compilers to use if software must be compiled.
            repos (dict): Dictionary of URLs for source code archives indexed by architecture and OS.  
                          The None key specifies the default (i.e. universal) source.
            commands (dict): Dictionary of commands, indexed by architecture and OS, that must be installed.
            libraries (dict): Dictionary of libraries, indexed by architecture and OS, that must be installed.
            headers (dict): Dictionary of headers, indexed by architecture and OS, that must be installed.
        """
        # pylint: disable=too-many-arguments
        assert isinstance(target_arch, Architecture)
        assert isinstance(target_os, OperatingSystem)
        self.dependencies = {}
        self.name = name
        self.title = title
        self.target_arch = target_arch
        self.target_os = target_os
        self.compilers = compilers
        self.verify_commands = self._lookup_target_os_list(commands)
        self.verify_libraries = self._lookup_target_os_list(libraries)
        self.verify_headers = self._lookup_target_os_list(headers)
        self.src_prefix = None
        self.is_installed = False
        src = sources[name]
        if os.path.isdir(src):
            self.src = None
            self._change_install_prefix(src)
            self.verify()
        else:
            self.src = src if src.lower() != 'download' else self._lookup_target_os_list(repos)
            md5sum = hashlib.md5()
            md5sum.update(self.src)
            uid = md5sum.hexdigest()
            # Search the storage hierarchy for an existing installation
            for storage in reversed(ORDERED_LEVELS):
                self._change_install_prefix(os.path.join(storage.prefix, prefix, name, uid))
                try:
                    self.verify()
                except SoftwarePackageError as err:
                    LOGGER.debug(err)
                    continue
                else:
                    break
            else:
                # No existing installation found, install at highest writable storage level
                self._change_install_prefix(os.path.join(highest_writable_storage().prefix, prefix, name, uid))
        LOGGER.debug("%s installation prefix is %s", self.name, self.install_prefix)
    
    def _change_install_prefix(self, value):
        self.install_prefix = value
        self.include_path = os.path.join(value, 'include')
        self.bin_path = os.path.join(value, 'bin')
        self.lib_path = os.path.join(value, 'lib')
        self._lockfile = LockFile(os.path.join(value, '.tau_lock'))

    def _lookup_target_os_list(self, dct):
        if not dct:
            return []
        default = dct[None]
        try:
            arch_dct = dct[self.target_arch]
        except KeyError:
            return default
        else:
            return arch_dct.get(self.target_os, arch_dct.get(None, default))
        
    def __enter__(self):
        """Lock the software installation for use by this process only."""
        if self.src:
            util.mkdirp(self.install_prefix)
            self._lockfile.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Unlock the software installation."""
        try:
            self._lockfile.release()
        except NotLocked:
            pass
        return False

    def _prepare_src(self, build_prefix, reuse):
        """Prepares source code for installation.
        
        Acquires package source code archive file via download or file copy,
        unpacks the archive, and verifies that required paths exist.
        Sets `self.src_prefix` to the directory containing the package source files.
        
        Args:
            build_prefix (str): If not None then download and build package at ``build_prefix``.
                                The archive file will also be saved in the normal location for reuse.
            reuse (bool): If True, attempt to reuse old archives and source files.

        Raises:
            ConfigurationError: The source code couldn't be copied or downloaded.
        """
        if not self.src:
            raise ConfigurationError("No source code provided for %s" % self.title)
        archive_name = os.path.basename(self.src)
        if reuse:
            # Search storage for source archive.
            for storage in reversed(ORDERED_LEVELS):
                archive_prefix = os.path.join(storage.prefix, "src")
                if not build_prefix:
                    build_prefix = archive_prefix
                archive = os.path.join(archive_prefix, archive_name)
                if os.path.exists(archive):
                    LOGGER.info("Using %s source archive '%s'", self.title, archive)
                    if build_prefix != archive_prefix:
                        LOGGER.debug("Copying '%s' ==> '%s'", archive_name, build_prefix)
                        shutil.copy(archive, os.path.join(build_prefix, archive_name))
                    break
        else:
            # Acquire a new copy of the source archive.
            archive_prefix = os.path.join(highest_writable_storage().prefix, "src")
            if not build_prefix:
                build_prefix = archive_prefix
            archive = os.path.join(build_prefix, archive_name)
            try:
                util.download(self.src, archive)
            except IOError:
                raise ConfigurationError("Cannot acquire source archive '%s'" % self.src,
                                         "Check that the file or directory is accessable")
            if build_prefix != archive_prefix:
                LOGGER.debug("Copying '%s' ==> '%s'", archive_name, archive_prefix)
                util.mkdirp(archive_prefix)
                shutil.copy(archive, os.path.join(archive_prefix, archive_name))
        try:
            topdir = util.archive_toplevel(archive)
        except IOError as err:
            LOGGER.debug("Cannot read %s archive file '%s': %s", self.title, archive, err)
            if reuse:
                LOGGER.debug("Downloading a fresh copy of '%s'", self.src)
                return self._prepare_src(build_prefix, reuse=False)
            else:
                raise ConfigurationError("Cannot read %s archive file '%s': %s" % (self.title, archive, err))
        src_prefix = os.path.join(build_prefix, topdir)
        if reuse and os.path.isdir(src_prefix):
            LOGGER.info("Reusing %s source files found at '%s'", self.title, src_prefix)
        else:
            util.rmtree(src_prefix, ignore_errors=True)
            try:
                src_prefix = util.extract_archive(archive, build_prefix)
            except IOError as err:
                raise ConfigurationError("Cannot extract source archive '%s': %s" % (archive, err),
                                         "Check that the file or directory is accessable")
        self.src_prefix = src_prefix

    def verify(self):
        """Check if the installation at :any:`installation_prefix` is valid.
        
        A valid installation provides all expected files and commands.
        Subclasses may wish to perform additional checks.
        
        Raises:
          SoftwarePackageError: Describs why the installation is invalid.
        """
        for pkg in self.dependencies.itervalues():
            pkg.verify()
        LOGGER.debug("Checking %s installation at '%s' targeting %s %s", 
                     self.name, self.install_prefix, self.target_arch, self.target_os)
        if not os.path.exists(self.install_prefix):
            raise SoftwarePackageError("'%s' does not exist" % self.install_prefix)
        for cmd in self.verify_commands:
            path = os.path.join(self.bin_path, cmd)
            if not os.path.exists(path):
                raise SoftwarePackageError("'%s' is missing" % path)
            if not os.access(path, os.X_OK):
                raise SoftwarePackageError("'%s' exists but is not executable" % path)
        for lib in self.verify_libraries:
            path = os.path.join(self.lib_path, lib)
            if not util.file_accessible(path):
                # Some systems (e.g. SuSE) append the machine bitwidth to the library path
                path = os.path.join(self.lib_path+'64', lib)
                if not util.file_accessible(path):
                    raise SoftwarePackageError("'%s' is not accessible" % path)
        for header in self.verify_headers:
            path = os.path.join(self.include_path, header)
            if not util.file_accessible(path):
                raise SoftwarePackageError("'%s' is not accessible" % path)
        self.is_installed = True
        LOGGER.debug("%s installation at '%s' is valid", self.name, self.install_prefix)
        
    def add_dependency(self, name, sources, *args, **kwargs):
        """Adds a new package to the list of packages this package depends on.
        
        Args:
            name (str): The name of the package.  There must be a corresponding 
                        ``tau.cf.software.<name>_installation`` module.
            sources (dict): Packages sources as strings indexed by package names as strings.  A source may be a 
                            path to a directory where the software has already been installed, or a path to a source
                            archive file, or the special keyword 'download'.
        """
        module_name = name + '_installation'
        cls_name = util.camelcase(module_name)
        pkg = __import__('tau.cf.software.' + module_name, globals(), locals(), [cls_name], -1)
        cls = getattr(pkg, cls_name)
        self.dependencies[name] = cls(sources, self.target_arch, self.target_os, self.compilers, *args, **kwargs)

    
    def install(self, force_reinstall):
        """Installs the software package.
        
        Raises:
            NotImplementedError: This method must be overridden by a subclass.
        """
        raise NotImplementedError
    
    def compiletime_config(self, opts=None, env=None):
        """Configure compilation environment to use this software package. 

        Returns command line options and environment variables required by this
        software package **when it is used to compile other software packages**.
        The default behavior, to be overridden by subclasses as needed, is to 
        prepend ``self.bin_path`` to the PATH environment variable.
        
        Args:
            opts (list): Optional list of command line options.
            env (dict): Optional dictionary of environment variables.
            
        Returns: 
            tuple: opts, env updated for the new environment.
        """
        opts = list(opts) if opts else []
        env = dict(env) if env else dict(os.environ)
        if os.path.isdir(self.bin_path):
            try:
                env['PATH'] = os.pathsep.join([self.bin_path, env['PATH']])
            except KeyError:
                env['PATH'] = self.bin_path
        return list(set(opts)), env

    def runtime_config(self, opts=None, env=None):
        """Configure runtime environment to use this software package.
        
        Returns command line options and environment variables required by this 
        software package **when other software packages depending on it execute**.
        The default behavior, to be overridden by subclasses as needed, is to 
        prepend ``self.bin_path`` to the PATH environment variable and 
        ``self.lib_path`` to the system library path (e.g. LD_LIBRARY_PATH).
        
        Args:
            opts (list): Optional list of command line options.
            env (dict): Optional dictionary of environment variables.
            
        Returns: 
            tuple: opts, env updated for the new environment.
        """
        opts = list(opts) if opts else []
        env = dict(env) if env else dict(os.environ)
        if os.path.isdir(self.bin_path):
            try:
                env['PATH'] = os.pathsep.join([self.bin_path, env['PATH']])
            except KeyError:
                env['PATH'] = self.bin_path
        if os.path.isdir(self.lib_path):
            if sys.platform == 'darwin':
                library_path = 'DYLD_LIBRARY_PATH'
            else:
                library_path = 'LD_LIBRARY_PATH'   
            try:
                env[library_path] = os.pathsep.join([self.lib_path, env[library_path]])
            except KeyError:
                env[library_path] = self.lib_path
        return list(set(opts)), env


class AutotoolsInstallation(Installation):
    """Base class for installations that follow the GNU Autotools installation process.
    
    The GNU Autotools installation process is::
        ./configure [options]
        make [flags] all [options] 
        make [flags] install [options]
    """
    
    def configure(self, flags, env):
        """Invoke `configure`.
        
        Changes to `env` are propagated to subsequent steps, i.e. `make`.
        Changes to `flags` are not propogated to subsequent steps.
        
        Args:
            flags (list): Command line flags to pass to `configure`.
            env (dict): Environment variables to set before invoking `configure`.
            
        Raises:
            SoftwarePackageError: Configuration failed.
        """
        assert self.src_prefix
        LOGGER.debug("Configuring %s at '%s'", self.name, self.src_prefix)
        flags = list(flags)
        # Prepare configuration flags
        flags += ['--prefix=%s' % self.install_prefix]
        cmd = ['./configure'] + flags
        LOGGER.info("Configuring %s...", self.title)
        if util.create_subprocess(cmd, cwd=self.src_prefix, env=env, stdout=False):
            raise SoftwarePackageError('%s configure failed' % self.title)   
    
    def make(self, flags, env, parallel=True):
        """Invoke `make`.
        
        Changes to `env` are propagated to subsequent steps, i.e. `make install`.
        Changes to `flags` are not propogated to subsequent steps.
        
        Args:
            flags (list): Command line flags to pass to `make`.
            env (dict): Environment variables to set before invoking `make`.
            parallel (bool): If True, pass parallelization flags to `make`.
            
        Raises:
            SoftwarePackageError: Compilation failed.
        """
        assert self.src_prefix
        LOGGER.debug("Making %s at '%s'", self.name, self.src_prefix)
        flags = list(flags)
        par_flags = parallel_make_flags() if parallel else []
        cmd = ['make'] + par_flags + flags
        LOGGER.info("Compiling %s...", self.title)
        if util.create_subprocess(cmd, cwd=self.src_prefix, env=env, stdout=False):
            cmd = ['make'] + flags
            if util.create_subprocess(cmd, cwd=self.src_prefix, env=env, stdout=False):
                raise SoftwarePackageError('%s compilation failed' % self.title)

    def make_install(self, flags, env, parallel=False):
        """Invoke `make install`.
        
        Changes to `env` are propagated to subsequent steps.  Normally there 
        wouldn't be anything after `make install`, but a subclass could change that.
        Changes to `flags` are not propogated to subsequent steps.
        
        Args:
            flags (list): Command line flags to pass to `make`.
            env (dict): Environment variables to set before invoking `make`.
            parallel (bool): If True, pass parallelization flags to `make`.
            
        Raises:
            SoftwarePackageError: Configuration failed.
        """
        assert self.src_prefix
        LOGGER.debug("Installing %s at '%s' to '%s'", self.name, self.src_prefix, self.install_prefix)
        flags = list(flags)
        if parallel:
            flags += parallel_make_flags()
        cmd = ['make', 'install'] + flags
        LOGGER.info("Installing %s...", self.title)
        if util.create_subprocess(cmd, cwd=self.src_prefix, env=env, stdout=False):
            raise SoftwarePackageError('%s installation failed' % self.title)
        # Some systems use lib64 instead of lib
        if os.path.isdir(self.lib_path+'64') and not os.path.isdir(self.lib_path):
            os.symlink(self.lib_path+'64', self.lib_path)

    def install(self, force_reinstall=False):
        """Execute the typical GNU Autotools installation sequence.
        
        Modifies the system by building and installing software.
        
        Args:
            force_reinstall (bool): If True, reinstall even if the software package passes verification.
            
        Raises:
            SoftwarePackageError: Installation failed.
        """
        for pkg in self.dependencies.itervalues():
            pkg.install(force_reinstall)

        if not self.src:
            try:
                self.verify()
            except SoftwarePackageError as err:
                raise SoftwarePackageError("Invalid %s installation at '%s': %s" % 
                                           (self.title, self.install_prefix, err),
                                           "Specify source code path or URL to enable broken package reinstallation.")
        elif not force_reinstall:
            try:
                return self.verify()
            except SoftwarePackageError as err:
                LOGGER.debug(err)

        LOGGER.info("Installing %s at '%s' from '%s'", self.title, self.install_prefix, self.src)
        if os.path.isdir(self.install_prefix): 
            LOGGER.info("Cleaning %s installation prefix '%s'", self.title, self.install_prefix)
            util.rmtree(self.install_prefix, ignore_errors=True)
        
        # Try to build in shared memory, if available
        try:
            build_prefix = util.mkdtemp(dir="/dev/shm")
        except IOError as err:
            LOGGER.debug(err)
            build_prefix = None
        self._prepare_src(build_prefix, reuse=True)

        # Environment variables are shared between the subprocesses
        # created for `configure` ; `make` ; `make install`
        env = {}
        try:
            self.configure([], env)
            self.make([], env)
            self.make_install([], env)
        except Exception as err:
            LOGGER.info("%s installation failed: %s ", self.title, err)
            raise
        else:
            # Delete the decompressed source code to save space and clean up in preperation for
            # future reconfigurations.  The compressed source archive is retained.
            LOGGER.debug("Deleting '%s'", self.src_prefix)
            util.rmtree(self.src_prefix, ignore_errors=True)

        # Verify the new installation
        LOGGER.info("Verifying %s installation...", self.title)
        return self.verify()
