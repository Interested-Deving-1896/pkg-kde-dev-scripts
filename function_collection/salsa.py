from workdir import Workdir
import gitlab
import os
import pathlib
import re
import yaml

curdir = pathlib.Path(__file__)
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
        if status['status'] != "running":
            return status['status']
    for j in pipeline.jobs.list():
        if j.name == "build":
            data = {"pipeline": pipeline.id,
                    "job": {"id":j.id,
                            "status": j.status}
                    }
            job = project.jobs.get(j.id, lazy=True)
            path = pathlib.Path(f"salsa-cache/jobs/{j.id}/logs")
            job_status = status.get('job',{}).get('status', None)
            if not path.exists() or job_status == "running":
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(job.trace())

            log = path.read_text()
            if re.search(f"^\+ tee -a.*{re.escape(pkg.dscPath.stem+'+salsaci_amd64.build')}",log, re.M):
                data['status'] = j.status
            else:
                data['status'] = None
            workdir.set(f"status/{name}", data)

            return data['status']
    return "unknown"
