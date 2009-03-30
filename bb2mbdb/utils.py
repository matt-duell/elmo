'''Utility and help code for buildbot-mbdb adapters.'''


from datetime import datetime

from mbdb.models import Change, Tag, File, Log
from django.conf import settings

from twisted.python import log

def timeHelper(t):
    if t is None:
        return t
    return datetime.utcfromtimestamp(t)


def modelForChange(master, change):
    try:
        dbchange = Change.objects.get(master=master, number = change.number)
        return dbchange
    except Change.DoesNotExist:
        dbchange = Change.objects.create(master=master, number = change.number,
                                         when = timeHelper(change.when))
        for prop in ('branch', 'revision', 'who', 'comments'):
            val = getattr(change, prop)
            if val:
                setattr(dbchange, prop, val)
        if hasattr(change, 'locale'):
            tag, created = Tag.objects.get_or_create(value = change.locale)
            dbchange.tags.add(tag)
        dbchange.save()
        if not change.files:
            return dbchange

        dbfiles = list(File.objects.filter(path__in = change.files))
        newfiles = set(change.files) - set(map(unicode, dbfiles))
        dbfiles += [File.objects.create(path = file) for file in newfiles]
        dbchange.files.add(*dbfiles)
        dbchange.save()
        return dbchange

def modelForLog(dbstep, logfile, basedir, isFinished = False):
    if not hasattr(logfile, 'getFilename'):
        logf = dbstep.logs.create(filename = None, html = logfile.html,
                                  name = logfile.getName(),
                                  isFinished = True)
    else:
        relfile = logfile.getFilename()[len(basedir)+1:]
        logf = dbstep.logs.create(filename = relfile, html = None,
                                  name = logfile.getName(),
                                  isFinished = isFinished)
    return logf
