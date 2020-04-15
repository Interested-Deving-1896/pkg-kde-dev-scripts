from workdir import Workdir
import gitlab
import os
import pathlib
import re
import yaml

curdir = pathlib.Path(__file__)
logcache = curdir.with_name("salsa-cache")/"jobs"
workdir = Workdir(curdir.with_name("salsa-cache"))

with open(curdir.with_name('config.yml')) as f:
    CONFIG = yaml.safe_load(f)

gl = gitlab.Gitlab('https://salsa.debian.org', private_token=CONFIG['salsa_token'])

KDEGROUPID = 2807

def getProject(name):
    project = workdir.get(f"projects/{name}", None)

    if not project:
        group = gl.groups.get(KDEGROUPID)
        for p in group.projects.list(search=name):
            if p.name == name:
                project = p.attributes
                break
        workdir.set(f"projects/{name}",project)

    return gl.projects.get(project['id'], lazy=True)

def getBuildStatus(pkg):
    name = pkg.path.name
    status = workdir.get(f"status/{name}", {})
    project = getProject(name)
    _ = project.pipelines.list(ref=pkg.git.active_branch.name, sort="desc", page=1, per_page=1)
    if not _:
        return None
    pipeline = _[0]
    if pipeline.id == status.get('pipeline', None):
        if status['status'] and status['status'] != "running":
            return status['status']
    for j in pipeline.jobs.list():
        if j.name == "build":
            data = {"pipeline": pipeline.id,
                    "job": {"id":j.id,
                            "status": j.status}
                    }
            job = project.jobs.get(j.id, lazy=True)
            path = pathlib.Path(logcache/f"{j.id}/logs")
            job_status = status.get('job',{}).get('status', None)
            if not path.exists() or job_status == "running":
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(job.trace())

            log = path.read_text()
            if j.status == "running":
                data['status'] = j.status
            elif re.search(f"^\+ tee -a.*{re.escape(pkg.dscPath.stem+'+salsaci_amd64.build')}",log, re.M):
                data['status'] = j.status
            elif j.status == "running":
                data['status'] = j.status
            else:
                data['status'] = None
            workdir.set(f"status/{name}", data)

            return data['status']
    return "unknown"

def getBuildlog(pkg):
    getBuildStatus(pkg)

    name = pkg.path.name
    status_data = workdir.get(f"status/{name}")
    job = status_data.get('job')
    return pathlib.Path(logcache/f"{job['id']}/logs")

def getLintianPath(pkg):
    getBuildStatus(pkg)

    name = pkg.path.name
    status_data = workdir.get(f"status/{name}", {})
    lintian = status_data.get('lintian',{}).get('status', None)
    if lintian and lintian != "running":
        return pathlib.Path(logcache/f"{status_data['lintian']['id']}/lintian")

    project = getProject(name)
    pipeline_id = status_data.get('pipeline',{})
    pipeline = project.pipelines.get(pipeline_id)
    for j in pipeline.jobs.list():
        if j.name == "lintian":
            job = project.jobs.get(j.id)
            path = pathlib.Path(logcache/f"{j.id}/lintian")
            job_status = status_data.get('lintian',{}).get('status', None)
            if not path.exists() or job_status == "running":
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(job.trace())
            status_data['lintian'] = {'id': j.id, 'status': job.status}
            workdir.set(f"status/{name}", status_data)

            return path

def getLintian(pkg):
    path = getLintianPath(pkg)

    m = re.search(r"\$ lintian [^\n]*?\nwarning: the authors of lintian do not recommend running it with root privileges!\n(.*)\n[^\n]*?lintian2j", path.read_text(),re.S)
    return m.group(1).splitlines()
