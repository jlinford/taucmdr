###############################################################################
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
###############################################################################

# If set to "true" then show commands as they are executed.
# Otherwise only the command's output will be shown.
VERBOSE = true

# Shell utilities
RM = rm -f
MV = mv -f
MKDIR = mkdir -p

VERSION = $(shell cat VERSION 2>&1 || ./.version.sh || echo "0.0.0")

# Get build system locations from configuration file or command line
ifneq ("$(wildcard setup.cfg)","")
  BUILDDIR = $(shell grep '^build-base =' setup.cfg | sed 's/build-base = //')
  INSTALLDIR = $(shell grep '^prefix =' setup.cfg | sed 's/prefix = //')
endif
ifeq ($(BUILDDIR),)
  BUILDDIR=build
endif
ifeq ($(INSTALLDIR),)
  INSTALLDIR=$(HOME)/taucmdr-$(VERSION)
endif

TAU = $(INSTALLDIR)/bin/tau

# Get target OS and architecture
ifeq ($(OS),)
  OS = $(shell uname -s)
endif
ifeq ($(ARCH),)
  ARCH = $(shell uname -m)
endif

ifeq ($(VERBOSE),false)
  ECHO=@
  CURL_FLAGS=-s
  WGET_FLAGS=--quiet
else
  ECHO=
  CURL_FLAGS=
  WGET_FLAGS=
endif

# Build download macro
# Usage: $(call download,source,dest)
WGET = $(shell which wget)
ifneq ($(WGET),)
  download = $(WGET) $(WGET_FLAGS) -O "$(2)" "$(1)"
else
  CURL = $(shell which curl)
  ifneq ($(CURL),)
    download = $(CURL) $(CURL_FLAGS) -L "$(1)" > "$(2)"
  else
    $(warning Either curl or wget must be in PATH to download packages)
  endif
endif

# Miniconda configuration
USE_MINICONDA = true
ifeq ($(OS),Darwin)
ifeq ($(ARCH),i386)
  USE_MINICONDA = false
endif
endif
ifeq ($(OS),Darwin)
  CONDA_OS = MacOSX
else 
  ifeq ($(OS),Linux)
    CONDA_OS = Linux
  else
    USE_MINICONDA = false
  endif
endif
ifeq ($(ARCH),x86_64)
  CONDA_ARCH = x86_64
else 
  ifeq ($(ARCH),i386)
    CONDA_ARCH = x86
  else
    ifeq ($(ARCH),ppc64le)
      CONDA_ARCH = ppc64le
    else
      USE_MINICONDA = false
    endif
  endif
endif
CONDA_VERSION = latest
CONDA_REPO = https://repo.continuum.io/miniconda
CONDA_PKG = Miniconda2-$(CONDA_VERSION)-$(CONDA_OS)-$(CONDA_ARCH).sh
CONDA_URL = $(CONDA_REPO)/$(CONDA_PKG)
CONDA_SRC = system/src/$(CONDA_PKG)
CONDA_DEST = $(INSTALLDIR)/conda
CONDA = $(CONDA_DEST)/bin/python

ifeq ($(USE_MINICONDA),true)
  PYTHON_EXE = $(CONDA)
  PYTHON_FLAGS = -EO
else
  $(warning WARNING: There are no miniconda packages for this system: $(OS), $(ARCH).)
  CONDA_SRC = 
  PYTHON_EXE = $(shell which python)
  PYTHON_FLAGS = -O
  ifeq ($(PYTHON_EXE),)
    $(error python not found in PATH.)
  else
    $(warning WARNING: Trying to use '$(PYTHON_EXE)' instead.)
  endif
endif
PYTHON = $(PYTHON_EXE) $(PYTHON_FLAGS)

.PHONY: help build install clean python_check python_download

.DEFAULT: help

help:
	@echo "-------------------------------------------------------------------------------"
	@echo "TAU Commander installation"
	@echo
	@echo "Usage: make install [INSTALLDIR=$(INSTALLDIR)]"
	@echo "-------------------------------------------------------------------------------"
	
build: python_check
	$(ECHO)$(PYTHON) setup.py build_scripts --executable "$(PYTHON)"
	$(ECHO)$(PYTHON) setup.py build

install: build
	$(ECHO)$(PYTHON) setup.py install --prefix $(INSTALLDIR)
	$(ECHO)$(INSTALLDIR)/system/configure --minimal
	@chmod -R a+rX,g+w $(INSTALLDIR)
	@echo
	@echo "-------------------------------------------------------------------------------"
	@echo "Hooray! TAU Commander is installed!" 
	@echo
	@echo "INSTALLDIR=\"$(INSTALLDIR)\""
	@echo 
	@echo "What's next?"
	@echo
	@echo "TAU Commander will automatically generate new TAU configurations for each new"
	@echo "experiment, so if you're just trying to get some performance data then go add"
	@echo "TAU Commander's \"bin\" directory to your path and maybe have a look at"
	@echo "the quick start guide at http://www.taucommander.com/guide."
	@echo
	@echo "If you'd like to pre-configure TAU for a particular experiment then go use"
	@echo "the \"INSTALLDIR/system/configure\" script to generate TAU configurations."
	@echo "This is especially a good idea if you are a system administrator installing"
	@echo "TAU Commander so that someone else can use it.  Without arguments, the"
	@echo "\"configure\" script will generate as many TAU configurations as it can."
	@echo
	@echo "In short:"
	@echo "  If you are a sysadmin then go run \"INSTALLDIR/system/configure\"."
	@echo "  Otherwise just add \"INSTALLDIR/bin\" to your PATH and get to work." 
	@echo "-------------------------------------------------------------------------------"
	@echo

python_check: $(PYTHON_EXE)
	@$(PYTHON) -c "import sys; import setuptools;" || (echo "ERROR: setuptools is required." && false)
	
python_download: $(CONDA_SRC)

$(CONDA): $(CONDA_SRC)
	$(ECHO)bash $< -b -p $(CONDA_DEST)
	$(ECHO)touch $(CONDA_DEST)/bin/*

$(CONDA_SRC):
	$(ECHO)$(MKDIR) `dirname "$(CONDA_SRC)"`
	$(call download,$(CONDA_URL),$(CONDA_SRC))

clean: 
	$(ECHO)$(RM) -r $(BUILDDIR)
