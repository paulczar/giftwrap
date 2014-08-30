# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2014, Craig Tracey <craigtracey@gmail.com>
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations

import os
import sys
import tempfile
import errno
import shutil

from giftwrap import log
from giftwrap.gerrit import GerritReview
from giftwrap.openstack_git_repo import OpenstackGitRepo
from giftwrap.package import Package
from giftwrap.container import Container
from giftwrap.util import execute

LOG = log.get_logger()


class Builder(object):

    def __init__(self, spec):
        self._spec = spec

    def build(self):
        """ this is where all the magic happens """

        try:
            spec = self._spec
            for project in self._spec.projects:
                LOG.info("Beginning to build '%s'", project.name)
                os.makedirs(project.install_path)

                LOG.info("Fetching source code for '%s'", project.name)
                repo = OpenstackGitRepo(project.giturl, project.gitref)
                repo.clone(project.install_path)
                review = GerritReview(repo.change_id, project.git_path)

                LOG.info("Creating the virtualenv for '%s'", project.name)
                execute(project.venv_command, project.install_path)

                LOG.info("Installing '%s' pip dependencies to the virtualenv",
                         project.name)
                execute(project.install_command %
                        review.build_pip_dependencies(string=True),
                        project.install_path)

                LOG.info("Installing '%s' to the virtualenv", project.name)
                execute(".venv/bin/python setup.py install",
                        project.install_path)

                if not spec.settings.all_in_one:
                    pkg = Package(project.package_name, project.version,
                                  project.install_path, True)
                    pkg.build()

        except Exception as e:
            LOG.exception("Oops. Something went wrong. Error was:\n%s", e)
            sys.exit(-1)


class Docker(object):

    def __init__(self, spec):
        self._spec = spec

    def build(self):
        """ this is where all the magic happens """

        try:
            spec = self._spec
            for project in self._spec.projects:

                dockerpath = tempfile.mkdtemp()

                LOG.info("Beginning to build '%s' in '%s'",
                         project.name, dockerpath)

                LOG.info("Fetching source code for '%s'", project.name)
                repo = OpenstackGitRepo(project.giturl, project.gitref)
                repo.clone(dockerpath)
                review = GerritReview(repo.change_id, project.git_path)
                deps = review.build_pip_dependencies(string=True)
                LOG.info("Writing 'Dockerfile' to '%s'", dockerpath)
                dockerfile = os.path.join(dockerpath, 'Dockerfile')
                with open(dockerfile, "w") as w:
                    w.write("""\
FROM python:2
RUN apt-get -yqq update && apt-get -yqq install git wget curl \
        libldap2-dev libsasl2-dev libssl-dev
RUN pip install virtualenv
ADD . """ + project.install_path + """
WORKDIR """ + project.install_path + """
RUN """ + project.venv_command + """
RUN """ + project.install_command % deps + """
RUN .venv/bin/python setup.py install

""")

                if not spec.settings.all_in_one:
                    LOG.info("Building Docker image for '%s'", project.name)
                    cnt = Container(project.package_name, project.version,
                                    dockerpath, True)
                    img_id, img_name = cnt.build()
                    LOG.info("Successfully built container '%s' => '%s'",
                             img_id, img_name)

                try:
                    shutil.rmtree(dockerpath)
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise

        except Exception as e:
            LOG.exception("Oops. Something went wrong. Error was:\n%s", e)
            sys.exit(-1)
