import io

from functions import *

def updateHomepagetoInvent(pkg, salsaSubgroup, upstreamGroup):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    msg = f"Update Homepage link to point to new invent.kde.org"
    url = f"https://invent.kde.org/{upstreamGroup}/{pkg.upstreamName}"
    control = pkg.path/"debian/control"

    pkg.git.remotes.origin.set_url(f"qt-kde-team:{salsaSubgroup}/{pkg.name}.git")

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        for block in pkg.controlParagraphs():
            if block.get("Source"):
                if block['Homepage'] != url:
                    print(f"Homepage does not match new Homepage: \
                        {url} != {block['Homepage']}, \
                        updating..")
                    block['Homepage'] = url
                    changed = True
                block.dump(tmpfile)
                continue
            tmpfile.write(b'\n')
            block.dump(tmpfile)

        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)

    if changed:
        wrap_and_sort( pkg, "debian/control")
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                        "debian/control",
                        ])
        pkg.git.index.commit(msg)
    else:
        print(f"Homepage is current")


def updateCopyrightSourcetoInvent(pkg, salsaSubgroup, upstreamGroup):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    msg = f'Update field Source in debian/copyright to invent.kde.org move.'
    url = f"https://invent.kde.org/{upstreamGroup}/{pkg.upstreamName}"
    copyright_file = pkg.path/"debian/copyright"

    pkg.git.remotes.origin.set_url(f"qt-kde-team:{salsaSubgroup}/{pkg.name}.git")

    changed = False
    with tempfile.NamedTemporaryFile() as tmpfile:
        with io.open(copyright_file, 'r+', encoding='utf-8') as f:
            c = copyright.Copyright(f)
            for block in c:
                if hasattr(block, 'source'):
                    try:
                        if block.source != url:
                            print(f'Copyright.Header Source: {block.source} != {url}, /n updating..')
                            block.source = url
                            print(f'Source updated: {block.source}')
                            changed = True
                    except AttributeError:
                        break
                    print(block.source)
                tmpfile.write(b'\n')
                block.dump(tmpfile)

            tmpfile.flush()
            shutil.copyfile(tmpfile.name, copyright_file)

    if changed:
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/copyright"
                           ])
        print(f"changed: {pkg.name} ")
        pkg.git.index.commit(msg)
    else:
        print(f"Source is current")

def updateUpstreamContact(pkg, salsaSubgroup):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    msg = f"Set/Update field Upstream-Contact in debian/copyright."
    copyright_file = pkg.path/"debian/copyright"
    contact = f"plasma-devel@kde.org",
    pkg.git.remotes.origin.set_url(f"qt-kde-team:{salsaSubgroup}/{pkg.name}.git")
    changed = False
    with tempfile.NamedTemporaryFile() as tmpfile:
        with io.open(copyright_file, 'r+', encoding='utf-8') as f:
            c = copyright.Copyright(f)

            for block in c:
                print(block)
                if hasattr(block, 'upstream_contact'):
                    try:
                        if block.upstream_contact != contact:
                            print(f"Copyright.upstream_contact: {block.upstream_contact} != {contact}")
                            block.upstream_contact = contact
                            print(f"Upstream contact updated: {block.upstream_contact}")
                            changed = True
                    except AttributeError:
                        break
                tmpfile.write(b'\n')
                block.dump(tmpfile)
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, copyright_file)

    if changed:
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/copyright"
                           ])
        print(f"changed: {pkg.name} ")
        pkg.git.index.commit(msg)
    else:
         print(f"Upstream-Contact is current")


def cleanupMetadataObsoleteFields(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    metadata = pkg.path/"debian/upstream/metadata"

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        with metadata.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                block.changed  = False
                if "Name" in block:
                    del block['Name']
                if "Contact" in block:
                    del block['Contact']
                if block.changed:
                    changed = True
                block.dump(tmpfile)

                if changed:
                    tmpfile.flush()

                    shutil.copyfile(tmpfile.name, metadata)

            if changed:
                wrap_and_sort(pkg, "debian/upstream/metadata")
                addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
                pkg.git.index.add(["debian/changelog",
                        "debian/upstream/metadata",
                        ])
                pkg.git.index.commit(msg)

def addMissingBugMetadatafields(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    metadata = pkg.path/"debian/upstream/metadata"

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        with metadata.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                block.changed  = False
                if not "Bug-Database" in block:
                    block['Bug-Database'] = 'Bug-Database: https://bugs.kde.org/buglist.cgi?product=kuserfeedback&component=general'
                if not "Bug-Submit" in block:
                    block['Bug-Submit'] = 'Bug-Submit: https://bugs.kde.org/enter_bug.cgi?product=kuserfeedback'
                if not block.get("Name"):
                    tmpfile.write(b'\n')
                if block.changed:
                    changed = True
                block.dump(tmpfile)

        if changed:
            tmpfile.flush()

        shutil.copyfile(tmpfile.name, metadata)

    if changed:
        wrap_and_sort(pkg, "debian/upstream/metadata")
        msg = f"Add Bug-* entries to metadata file."
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                        "debian/upstream/metadata",
                        ])
        pkg.git.index.commit(msg)
