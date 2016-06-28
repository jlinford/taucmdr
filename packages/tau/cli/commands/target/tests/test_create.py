# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, ParaTools, Inc.
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
"""Test functions.

Functions used for unit tests of create.py.
"""

from tau import tests
from tau.cli.commands.target.create import COMMAND as create_cmd

class CreateTest(tests.TestCase):
    """Tests for :any:`target.create`."""

    def test_create(self):
        tests.reset_project_storage(project_name='proj1')
        argv = ['targ02']
        stdout, stderr = self.assertCommandReturnValue(0, create_cmd, argv)
        self.assertIn('Added target \'targ02\' to project configuration \'proj1\'', stdout)
        self.assertFalse(stderr)

    #def test_no_project(self):
    #    tests.reset_project_storage(project_name='proj1')
    #    from tau.storage.project import ProjectStorageError
    #    argv = ['test_no_project']
    #    self.assertRaises(ProjectStorageError, create_cmd.main, argv)

    def test_no_args(self):
        tests.reset_project_storage(project_name='proj1')
        _, _, stderr = self.exec_command(create_cmd, [])
        self.assertIn('error: too few arguments', stderr)

    def test_h_arg(self):
        tests.reset_project_storage(project_name='proj1')
        stdout, _ = self.assertCommandReturnValue(0, create_cmd, ['-h'])
        self.assertIn('Create target configurations.', stdout)
        self.assertIn('show this help message and exit', stdout)

    def test_help_arg(self):
        tests.reset_project_storage(project_name='proj1')
        stdout, _ = self.assertCommandReturnValue(0, create_cmd, ['--help'])
        self.assertIn('Create target configurations.', stdout)
        self.assertIn('show this help message and exit', stdout)

    def test_duplicatename(self):
        tests.reset_project_storage(project_name='proj1')
        _, _, stderr = self.exec_command(create_cmd, ['targ1'])
        self.assertIn('target create <target_name> [arguments]', stderr)
        self.assertIn('target create: error: A target with name', stderr)
        self.assertIn('already exists', stderr)
