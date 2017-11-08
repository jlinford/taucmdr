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

Functions used for unit tests of edit.py.
"""


from taucmdr import tests
from taucmdr.cli.commands.application import edit

class EditTest(tests.TestCase):
    """Tests for :any:`application.edit`."""

    def test_noargs(self):
        self.reset_project_storage()
        stdout, stderr = self.assertNotCommandReturnValue(0, edit.COMMAND, [])
        self.assertIn('too few arguments', stderr)
        self.assertFalse(stdout)

    def test_edit(self):
        self.reset_project_storage()
        argv = ['app1', '--new-name', 'app2']
        stdout, stderr = self.assertCommandReturnValue(0, edit.COMMAND, argv)
        self.assertIn('Updated application', stdout)
        self.assertFalse(stderr)

    def test_wrongname(self):
        self.reset_project_storage()
        argv = ['app2', '--new-name', 'app3']
        _, stderr = self.assertNotCommandReturnValue(0, edit.COMMAND, argv)
        self.assertIn('application edit <application_name> [arguments]', stderr)
        self.assertIn('application edit: error: No project-level application with name', stderr)
        
    def test_wrongarg(self):
        self.reset_project_storage()
        argv = ['app1', '--use-mpi', 'T']
        _, stderr = self.assertNotCommandReturnValue(0, edit.COMMAND, argv)
        self.assertIn('application edit <application_name> [arguments]', stderr)
        self.assertIn('application edit: error: unrecognized arguments', stderr)

    def test_discourage_staticapp_selectfile(self):
        self.reset_project_storage()
        argv = ['app1', '--linkage', 'static']
        _, stderr = self.assertCommandReturnValue(0, edit.COMMAND, argv)
        print stderr
        print _
        self.assertFalse(stderr)
        # argv = ['app1', '--select-file', 'static']
        # stdout, stderr = self.assertCommandReturnValue(0, edit.COMMAND, argv)
