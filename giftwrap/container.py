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

import re
import json
import docker

from giftwrap import log

LOG = log.get_logger()


class Container(object):

    def __init__(self, name, version, path, include_src=True):
        self.name = name
        self.version = version
        self.path = path
        self.include_src = include_src
        self.dockertag = self.name + ":" + self.version

    def build(self):

        c = docker.Client(base_url='unix://var/run/docker.sock',
                          version='1.14',
                          timeout=10)

        build_result = c.build(path=self.path, tag=self.dockertag,
                               quiet=False, fileobj=None, nocache=False,
                               rm=True, stream=False, timeout=None,
                               custom_context=False, encoding=None)

        img_id, logs = self._parse_result(build_result)
        if not img_id:
            LOG.info("build logs: \n %s", logs)
            raise
        else:
            return img_id, self.dockertag

    # I borrowed this from docker/stackbrew, should cull it down
    # to be more sane.
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
            return None, lines
