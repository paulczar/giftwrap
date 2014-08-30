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
import docker
import errno
import shutil
import re
import json

from giftwrap import log
from giftwrap.gerrit import GerritReview
from giftwrap.openstack_git_repo import OpenstackGitRepo
from giftwrap.package import Package
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

    def _parse_result(self, build_result):
        build_success_re = r'^Successfully built ([a-f0-9]+)\n$'
        if isinstance(build_result, tuple):
            img_id, logs = build_result
            return img_id, logs
        else:
            lines = [line for line in build_result]
            try:
                parsed_lines = [json.loads(e).get('stream', '') for e in lines]
            except ValueError:
                # sometimes all the data is sent on a single line ????
                #
                # ValueError: Extra data: line 1 column 87 - line 1 column
                # 33268 (char 86 - 33267)
                line = lines[0]
                # This ONLY works because every line is formatted as
                # {"stream": STRING}
                parsed_lines = [
                    json.loads(obj).get('stream', '') for obj in
                    re.findall('{\s*"stream"\s*:\s*"[^"]*"\s*}', line)
                ]

            for line in parsed_lines:
                LOG.debug(parsed_lines)
                match = re.match(build_success_re, line)
                if match:
                    return match.group(1), parsed_lines
            return None, parsed_lines

    def build(self):
        """ this is where all the magic happens """

        try:
            spec = self._spec
            for project in self._spec.projects:

                dockerpath = tempfile.mkdtemp()

                LOG.info("Beginning to build '%s' in '%s'", project.name, dockerpath)

                LOG.info("Fetching source code for '%s'", project.name)
                repo = OpenstackGitRepo(project.giturl, project.gitref)
                repo.clone(dockerpath)
                review = GerritReview(repo.change_id, project.git_path)

                LOG.info("Writing 'Dockerfile' to in '%s'", dockerpath)
                dockerfile = os.path.join(dockerpath, 'Dockerfile')
                with open(dockerfile, "w") as w:
                    w.write("""\
FROM python:2
RUN apt-get -yqq update && apt-get -yqq install git wget curl
ADD . /opt/"""+ project.name +"""
WORKDIR /opt/"""+ project.name +"""
RUN python setup.py install

""")

                dockertag = project.name + ":" + project.version

                c = docker.Client(base_url='unix://var/run/docker.sock',
                    version='1.14',
                    timeout=10)

                LOG.info("Building docker image '%s'", dockertag )

                build_result = c.build(path=dockerpath, tag=dockertag, quiet=False, fileobj=None, nocache=False,
                    rm=True, stream=False, timeout=None,
                    custom_context=False, encoding=None)

                img_id, logs = self._parse_result(build_result)
                if not img_id:
                    raise
                else:
                    LOG.info("built docker image '%s'", dockertag )

                try:
                    shutil.rmtree(dockerpath)
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise

        except Exception as e:
            LOG.exception("Oops. Something went wrong. Error was:\n%s", e)
            sys.exit(-1)