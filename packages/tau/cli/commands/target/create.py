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
"""``tau target create`` subcommand."""

import os
from tau import util
from tau.error import ConfigurationError
from tau.storage.levels import STORAGE_LEVELS
from tau.cli import arguments
from tau.cli.cli_view import CreateCommand
from tau.model.target import Target
from tau.model.compiler import Compiler
from tau.cf.compiler import CompilerFamily, CompilerRole
from tau.cf.compiler.mpi import MpiCompilerFamily, MPI_CXX_ROLE, MPI_CC_ROLE, MPI_FC_ROLE
from tau.cf.compiler.installed import InstalledCompilerFamily
from tau.cf.target import host
from tau.cf.target import Architecture, OperatingSystem, TauArch 

class TargetCreateCommand(CreateCommand):
    """``tau target create`` subcommand."""
    
    def parse_compiler_flags(self, args):
        """Parses host compiler flags out of the command line arguments.
         
        Args:
            args: Argument namespace containing command line arguments
             
        Returns:
            Dictionary of installed compilers by role keyword string.
             
        Raises:
            ConfigurationError: Invalid command line arguments specified
        """
        compilers = {}
        for family_attr, family_cls in [('host_family', CompilerFamily), ('mpi_family', MpiCompilerFamily)]:
            try:
                family_arg = getattr(args, family_attr)
            except AttributeError as err:
                # User didn't specify that argument, but that's OK
                self.logger.debug(err)
                continue
            else:
                delattr(args, family_attr)
            try:
                family_comps = InstalledCompilerFamily(family_cls(family_arg))
            except KeyError:
                self.parser.error("Invalid compiler family: %s" % family_arg)
            for comp in family_comps:
                self.logger.debug("args.%s=%r", comp.info.role.keyword, comp.absolute_path)
                setattr(args, comp.info.role.keyword, comp.absolute_path)
                compilers[comp.info.role] = comp
     
        compiler_keys = set(CompilerRole.keys())
        all_keys = set(args.__dict__.keys())
        given_keys = compiler_keys & all_keys
        missing_keys = compiler_keys - given_keys
        self.logger.debug("Given compilers: %s", given_keys)
        self.logger.debug("Missing compilers: %s", missing_keys)

        # TODO: probe given compilers
        
        for key in missing_keys:
            role = CompilerRole.find(key)
            try:
                compilers[role] = host.default_compiler(role)
            except ConfigurationError as err:
                self.logger.debug(err)
    
        # Check that all required compilers were found
        for role in CompilerRole.tau_required():
            if role not in compilers:
                raise ConfigurationError("%s compiler could not be found" % role.language,
                                         "See 'compiler arguments' under `%s --help`" % COMMAND)
                
        # Probe MPI compilers to discover wrapper flags
        for args_attr, wrapped_attr in [('mpi_include_path', 'include_path'), 
                                        ('mpi_library_path', 'library_path'),
                                        ('mpi_libraries', 'libraries')]:
            if not hasattr(args, args_attr):
                probed = set()
                for role in MPI_CC_ROLE, MPI_CXX_ROLE, MPI_FC_ROLE:
                    try:
                        comp = compilers[role]
                    except KeyError:
                        self.logger.debug("Not probing %s: not found", role)
                    else:
                        #self.logger.debug("%s: %s '%s'", role, comp.info.short_descr, comp.absolute_path)
                        probed.update(getattr(comp.wrapped, wrapped_attr))
                setattr(args, args_attr, list(probed))
        return compilers
    
    def _parse_tau_makefile(self, args):
        makefile = args.tau_makefile
        del args.tau_makefile
        if not util.file_accessible(makefile):
            self.parser.error("Invalid TAU makefile: %s" % makefile)
        # Set host architecture and OS from TAU makefile
        tau_arch_name = os.path.basename(os.path.dirname(os.path.dirname(makefile)))
        try:
            tau_arch = TauArch.find(tau_arch_name)
        except KeyError:
            raise ConfigurationError("TAU Makefile '%s' targets an unrecognized TAU architecture: %s" % 
                                     (makefile, tau_arch_name))
        self.logger.info("Parsing TAU Makefile '%s' to populate command line arguments:", makefile)
        args.host_arch = tau_arch.architecture.name
        self.logger.info("  --host-arch='%s'", args.host_arch)
        args.host_os = tau_arch.operating_system.name
        self.logger.info("  --host-os='%s'", args.host_os)
        args.tau_source = os.path.abspath(os.path.join(os.path.dirname(makefile), '..', '..'))
        self.logger.info("  --tau='%s'", args.tau_source)
        with open(makefile, 'r') as fin:
            parts = (("BFDINCLUDE", "binutils_source", lambda x: os.path.dirname(x.lstrip("-I"))), 
                     ("UNWIND_INC", "libunwind_source", lambda x: os.path.dirname(x.lstrip("-I"))),
                     ("PAPIDIR", "papi_source", os.path.abspath),
                     ("PDTDIR", "pdt_source", os.path.abspath),
                     ("SCOREPDIR", "scorep_source", os.path.abspath))
            for line in fin:
                for key, attr, operator in parts:
                    if line.startswith(key + '='):
                        try:
                            prefix = line.split('=')[1].strip()
                        except KeyError:
                            self.logger.warning("%s in '%s' is invalid", key, makefile)
                            continue
                        if not prefix:
                            prefix = "None"
                        else:
                            prefix = operator(prefix)
                            if not os.path.exists(prefix):
                                self.logger.warning("'%s' referenced by TAU Makefile '%s' doesn't exist",  
                                                    prefix, makefile)
                                continue
                        setattr(args, attr, prefix)
                        self.logger.info("  --%s='%s'", attr.rstrip("_source"), prefix)

    def construct_parser(self):
        parser = super(TargetCreateCommand, self).construct_parser()
        group = parser.add_argument_group('host arguments')
        group.add_argument('--host-compilers',
                           help="select all host compilers automatically from the given family",
                           metavar='<family>',
                           dest='host_family',
                           default=host.preferred_compilers().name,
                           choices=CompilerFamily.family_names())
        group = parser.add_argument_group('Message Passing Interface (MPI) arguments')
        group.add_argument('--mpi-compilers', 
                           help="select all MPI compilers automatically from the given family",
                           metavar='<family>',
                           dest='mpi_family',
                           default=host.preferred_mpi_compilers().name,
                           choices=MpiCompilerFamily.family_names())
        parser.add_argument('--tau-makefile',
                            help="Automatically populate target software configuration from a TAU Makefile",
                            metavar='<path>',
                            default=arguments.SUPPRESS)
        return parser
    
    def main(self, argv):
        args = self.parser.parse_args(args=argv)
        self.logger.debug('Arguments: %s', args)
        store = STORAGE_LEVELS[getattr(args, arguments.STORAGE_LEVEL_FLAG)[0]]

        if hasattr(args, "tau_makefile"):
            self._parse_tau_makefile(args)
            self.logger.debug('Arguments after parsing TAU Makefile: %s', args)            

        compilers = self.parse_compiler_flags(args)
        self.logger.debug('Arguments after parsing compiler flags: %s', args)
        
        data = {attr: getattr(args, attr) for attr in self.model.attributes if hasattr(args, attr)}
        for keyword, comp in compilers.iteritems():
            self.logger.debug("%s=%s (%s)", keyword, comp.absolute_path, comp.info.short_descr)
            record = Compiler.controller(store).register(comp)
            data[comp.info.role.keyword] = record.eid
            
        return super(TargetCreateCommand, self).create_record(store, data)

COMMAND = TargetCreateCommand(Target, __name__)
