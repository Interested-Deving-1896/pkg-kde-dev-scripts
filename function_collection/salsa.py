from workdir import Workdir
import gitlab
import os
import pathlib
import re
import yaml

curdir = pathlib.Path(__file__)
LOGCACHE = curdir.with_name("salsa-cache")/"jobs"
WORKDIR = Workdir(curdir.with_name("salsa-cache"))

with open(curdir.with_name('config.yml')) as f:
    CONFIG = yaml.safe_load(f)

gl = gitlab.Gitlab('https://salsa.debian.org', private_token=CONFIG['salsa_token'])

KDEGROUPID = 2807

class SalsaPackage:
    def __init__(self, pkg):
        self.pkg = pkg
        self.workdir = WORKDIR
        self.logcache = LOGCACHE

    @property
    def name(self):
        return self.pkg.path.name

    @property
    def _status(self):
        return self.workdir.get(f"status/{self.name}", {})

    @property
    def _project(self):
        return self.workdir.get(f"projects/{self.name}", None)

    @property
    def buildlog_path(self):
        return pathlib.Path(self.logcache/f"{self._status['job']['id']}/logs")

    @property
    def lintian_path(self):
        return pathlib.Path(self.logcache/f"{self._status['lintian']['id']}/lintian")

    def getProject(self):
        if not self._project:
            group = gl.groups.get(KDEGROUPID)
            for p in group.projects.list(search=self.name):
                if p.name == self.name:
                    self.workdir.set(f"projects/{self.name}", p.attributes)
                    break

        return gl.projects.get(self._project['id'], lazy=True)

    def getLintian(self):
        m = re.search(r"\$ lintian (?!--version)[^\n]*?\n(.*)\n[^\n]*\n[^\n]*?\$ lintian2junit.py", self.lintian_path.read_text(),re.S)
        return m.group(1).splitlines()

    def getBuildStatus(self):
        status = self._status
        project = self.getProject()
        _ = project.pipelines.list(ref=self.pkg.git.active_branch.name, sort="desc", page=1, per_page=1)
        if not _:
            return None
        pipeline = _[0]
        if pipeline.id == status.get('pipeline', None):
            if status['status'] and status['status'] != "running":
                return status['status']
        ret_status = "unknown"
        for j in pipeline.jobs.list(all=True):
            if j.name == "build":
                data = {"pipeline": pipeline.id,
                        "job": {"id":j.id,
                                "status": j.status}
                        }
                job = project.jobs.get(j.id, lazy=True)
                path = pathlib.Path(self.logcache/f"{j.id}/logs")
                job_status = status.get('job',{}).get('status', None)
                if not path.exists() or job_status == "running":
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(job.trace())

                log = path.read_text()

                if not log.strip():
                    path.write_bytes(job.trace())
                    log = path.read_text()

                if j.status == "running":
                    data['status'] = j.status
                elif re.search(f"^dpkg-buildpackage: info: source version {re.escape(str(self.pkg.version)+'+salsaci')}",log, re.M):
                    b_status = status.get('job',{}).get('status', None)
                    data['status'] = j.status
                elif j.status == "running":
                    data['status'] = j.status
                else:
                    data['status'] = None
                self.workdir.set(f"status/{self.name}", data)

                ret_status = data['status']
        return ret_status

    def getLintianPath(self):
        self.getBuildStatus()

        status_data = self._status
        lintian = status_data.get('lintian',{}).get('status', None)

        if lintian and lintian != "running":
            path = self.lintian_path
            if path.read_text():
                return path

        project = self.getProject()
        pipeline_id = status_data.get('pipeline',{})
        pipeline = project.pipelines.get(pipeline_id)
        ret = None
        for j in pipeline.jobs.list():
            if j.name == "lintian":
                job = project.jobs.get(j.id)
                path = pathlib.Path(self.logcache/f"{j.id}/lintian")
                job_status = status_data.get('lintian',{}).get('status', None)
                if not path.exists() or job_status == "running" or not path.read_text():
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(job.trace())
                status_data['lintian'] = {'id': j.id, 'status': job.status}
                self.workdir.set(f"status/{self.name}", status_data)

                ret = path
        return ret
