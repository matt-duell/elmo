from optparse import make_option
import os.path

from django.core.management.base import BaseCommand, CommandError
from pushes.models import *
from django.conf import settings

from mercurial.hg import repository
from mercurial.ui import ui as _ui

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-q', '--quiet', dest = 'quiet', action = 'store_true',
                    help = 'Run quietly'),
        )
    help = 'Add all files to the pushes database, needs local clones'
    args = '[repository name]*'

    def handle(self, *args, **options):
        quiet = options.get('quiet', False)
        if args:
            repos = Repository.objects.filter(name__in = args)
        else:
            repos = Repository.objects.all()
        for repo in repos:
            if not repo.changesets.count():
                continue
            if not quiet:
                print "Checking %s" % repo.name
            ui = _ui()
            repopath = os.path.join(settings.REPOSITORY_BASE,
                                    repo.name, '')
            configpath = os.path.join(repopath, '.hg', 'hgrc')
            if not os.path.isfile(configpath):
                print "You need to clone " + repo.name
                for p in repo.changesets.iterator():
                    print repo.name, cs.revision
                continue
            ui.readconfig(configpath)
            hgrepo = repository(ui, repopath)
            for p in repo.changesets.iterator():
                try:
                    ctx = hgrepo.changectx(cs.revision)
                    dbfiles = set(map(str, cs.files.all()))
                    hgfiles = set(ctx.files())
                    if dbfiles == hgfiles:
                        continue
                    for path in sorted(hgfiles - dbfiles):
                        f, created = File.objects.get_or_create(path = path)
                        cs.files.add(f)
                        if created:
                            f.save()
                    if dbfiles - hgfiles:
                        # unhook files
                        obsolete = sorted(dbfiles - hgfiles)
                        if not quiet:
                            print "removing " + " ".join(obsolete)
                        fls = cs.files.filter(path__in = obsolete)
                        cs.files.remove(*list(fls))
                    cs.save()
                except Exception, e:
                    print repo.name, e
