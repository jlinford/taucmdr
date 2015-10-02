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
"""``tau trial create`` subcommand."""

from tau import util
from tau.error import ConfigurationError
from tau.cli import arguments
from tau.cli.cli_view import CreateCommand
from tau.model.trial import Trial
from tau.model.project import Project


class TrialCreateCommand(CreateCommand):
    """``tau trial create`` subcommand."""

    @staticmethod
    def is_compatible(cmd):
        """Check if this subcommand can work with the given command.
        
        Args:
            cmd (str): A command from the command line, e.g. sys.argv[1].
            
        Returns:
            bool: True if this subcommand is compatible with `cmd`.
        """
        return bool(util.which(cmd))

    def construct_parser(self):
        usage = "%s <command> [arguments]" % self.command
        parser = arguments.get_parser(prog=self.command, usage=usage, description=self.summary)
        parser.add_argument('cmd',
                            help="Command, e.g. './a.out' or 'mpirun ./a.out'",
                            metavar='<command>')
        parser.add_argument('cmd_args', 
                            help="Command arguments",
                            metavar='[arguments]',
                            nargs=arguments.REMAINDER)
        return parser

    def main(self, argv):
        args = self.parser.parse_args(args=argv)
        self.logger.debug('Arguments: %s', args)

        proj_ctrl = Project.controller()
        proj = proj_ctrl.selected()
        if not proj:
            from tau.cli.commands.select import COMMAND as select_command
            raise ConfigurationError("No project selected.", "Try `%s`" % select_command.command)
        expr = proj.populate('selected')
        return expr.managed_run(args.cmd, args.cmd_args)


COMMAND = TrialCreateCommand(Trial, __name__, summary_fmt="Run an application under a new experiment trial.")
