# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import absolute_import

import datetime
import re
from nose.tools import eq_, ok_
from elmo.test import TestCase
from django.core.urlresolvers import reverse
import json
from l10nstats.models import Run
from elmo_commons.tests.mixins import EmbedsTestCaseMixin
from life.models import Tree, Forest, Locale
from shipping.models import Application, AppVersion
import shipping.views
import shipping.views.app
import shipping.views.release
import shipping.views.status


class ShippingTestCaseBase(TestCase, EmbedsTestCaseMixin):

    def _create_appver_tree(self):
        app = Application.objects.create(
          name='firefox',
          code='fx'
        )
        l10n = Forest.objects.create(
          name='l10n-central',
          url='http://hg.mozilla.org/l10n-central/',
        )
        tree = Tree.objects.create(
          code='fx',
          l10n=l10n,
        )
        appver = AppVersion.objects.create(
          app=app,
          version='1',
          code='fx1',
          codename='foxy'
        )
        appver.trees.through.objects.create(tree=tree,
                                            appversion=appver,
                                            start=None,
                                            end=None)

        return appver, tree


class ShippingTestCase(ShippingTestCaseBase):

    def test_basic_render_index_page(self):
        """render the shipping index page"""
        url = reverse(shipping.views.index)
        response = self.client.get(url)
        eq_(response.status_code, 200)
        self.assert_all_embeds(response.content)

    def test_basic_render_app_changes(self):
        """render shipping.views.app.changes"""
        url = reverse(shipping.views.app.changes,
                      args=['junk'])
        response = self.client.get(url)
        eq_(response.status_code, 404)

        appver, __ = self._create_appver_tree()
        url = reverse(shipping.views.app.changes,
                      args=[appver.code])
        response = self.client.get(url)
        eq_(response.status_code, 200)
        self.assert_all_embeds(response.content)
        ok_('<title>Locale changes for %s' % appver in response.content)
        ok_('<h1>Locale changes for %s' % appver in response.content)

    def test_dashboard_bad_urls(self):
        """test that bad GET parameters raise 404 errors not 500s"""
        url = reverse(shipping.views.dashboard)
        # Fail
        response = self.client.get(url, dict(av="junk"))
        eq_(response.status_code, 404)

        # to succeed we need sample fixtures
        appver, __ = self._create_appver_tree()

        # Succeed
        response = self.client.get(url, dict(av=appver.code))
        eq_(response.status_code, 200)

    def test_l10n_changesets_bad_urls(self):
        """test that bad GET parameters raise 404 errors not 500s"""
        url = reverse('shipping-l10n_changesets')
        # Fail
        response = self.client.get(url)
        # no av specified
        eq_(response.status_code, 400)

        response = self.client.get(url, dict(av="junk"))
        eq_(response.status_code, 400)

        # to succeed we need sample fixtures
        appver, __ = self._create_appver_tree()
        response = self.client.get(url, dict(av=appver.code))
        eq_(response.status_code, 200)

    def test_shipped_locales_bad_urls(self):
        """test that bad GET parameters raise 404 errors not 500s"""
        url = reverse('shipping-shipped_locales')
        # Fail
        response = self.client.get(url)
        eq_(response.status_code, 400)

        response = self.client.get(url, dict(ms="junk"))
        eq_(response.status_code, 400)
        response = self.client.get(url, dict(av="junk"))
        eq_(response.status_code, 400)

        # to succeed we need sample fixtures
        appver, __ = self._create_appver_tree()
        response = self.client.get(url, dict(av=appver.code))
        eq_(response.status_code, 200)

    def test_status_json_basic(self):
        url = reverse('shipping-status_json')
        response = self.client.get(url)
        eq_(response.status_code, 200)
        struct = json.loads(response.content)
        eq_(struct['items'], [])

        appver, tree = self._create_appver_tree()
        locale, __ = Locale.objects.get_or_create(
          code='en-US',
          name='English',
        )
        run = Run.objects.create(
          tree=tree,
          locale=locale,
        )
        assert Run.objects.all()
        run.activate()
        assert Run.objects.filter(active__isnull=False)
        response = self.client.get(url)
        struct = json.loads(response.content)
        ok_(struct['items'])
        ok_('Access-Control-Allow-Origin' in response)
        eq_(response['Access-Control-Allow-Origin'], '*')

    def test_status_json_by_treeless_appversion(self):
        url = reverse('shipping-status_json')
        appver, tree = self._create_appver_tree()
        # get the AppVersionThrough, and set it's duration to the past
        avt = appver.trees_over_time.get(tree=tree)
        n = datetime.datetime.utcnow()
        avt.start = n - datetime.timedelta(days=14)
        avt.end = n - datetime.timedelta(days=1)
        avt.save()
        response = self.client.get(url, {'av': appver.code})

        eq_(response.status_code, 200)
        struct = json.loads(response.content)
        eq_(struct['items'], [])

    def test_status_json_multiple_locales_multiple_trees(self):
        url = reverse('shipping-status_json')

        appver, tree = self._create_appver_tree()
        locale_en, __ = Locale.objects.get_or_create(
          code='en-US',
          name='English',
        )
        locale_ro, __ = Locale.objects.get_or_create(
          code='ro',
          name='Romanian',
        )
        locale_ta, __ = Locale.objects.get_or_create(
          code='ta',
          name='Tamil',
        )

        # 3 more trees
        tree2 = Tree.objects.create(
          code='fy',
          l10n=tree.l10n,
        )
        tree3 = Tree.objects.create(
          code='fz',
          l10n=tree.l10n,
        )
        # this tree won't correspond to a AppVersion
        tree4 = Tree.objects.create(
          code='tree-loner',
          l10n=tree.l10n,
        )
        assert Tree.objects.count() == 4

        # 4 appversions
        appver2 = AppVersion.objects.create(
          app=appver.app,
          code='FY1',
          accepts_signoffs=True
        )
        appver2.trees.through.objects.create(tree=tree2,
                                             appversion=appver2,
                                             start=None,
                                             end=None)
        appver3 = AppVersion.objects.create(
          app=appver.app,
          code='FZ1',
          accepts_signoffs=True
        )
        appver3.trees.through.objects.create(tree=tree3,
                                             appversion=appver3,
                                             start=None,
                                             end=None)
        AppVersion.objects.create(
          app=appver.app,
          code='F-LONER',
          accepts_signoffs=True
        )

        assert AppVersion.objects.count() == 4

        data = {}  # All!
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        appver4trees = [x for x in struct['items']
                        if x['type'] == 'AppVer4Tree']

        trees = sorted(x['label'] for x in appver4trees)
        # note that trees without an appversion isn't returned
        # nor are appversions that don't accept sign-offs
        eq_(trees, [tree2.code, tree3.code])
        appversions = sorted(x['appversion'] for x in appver4trees)
        # note that appversion without an appversion isn't returned
        eq_(appversions, [appver2.code, appver3.code])

        # query a specific set of trees
        data = {'tree': [tree2.code, tree3.code]}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        appver4trees = [x for x in struct['items']
                        if x['type'] == 'AppVer4Tree']
        trees = sorted(x['label'] for x in appver4trees)
        eq_(trees, [tree2.code, tree3.code])

        # query a specific set of trees, one which isn't implemented by any
        # appversion
        data = {'tree': [tree3.code, tree4.code]}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        appver4trees = [x for x in struct['items']
                        if x['type'] == 'AppVer4Tree']
        trees = sorted(x['label'] for x in appver4trees)
        # tree4 is skipped because there's no appversion for that one
        assert not Run.objects.all()
        eq_(trees, [tree3.code])

        # Now, let's add some Runs
        run = Run.objects.create(
          tree=tree,
          locale=locale_en,
        )
        run.activate()
        data = {}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        ok_(struct['items'])
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds[0]['runid'], run.pk)

        data = {'tree': tree2.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds, [])

        data = {'tree': tree.code, 'locale': locale_ta.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds, [])

        data = {'tree': tree.code, 'locale': locale_en.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds[0]['runid'], run.pk)

        # doing data={'tree': tree2.code} excludes the run I have but setting
        # a AppVersion that points to the right tree should include it
        data = {'tree': tree2.code, 'av': appver.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds[0]['runid'], run.pk)

        # but if you specify a locale it gets filtered out
        data = {'av': appver.code, 'locale': locale_ta.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds, [])

        run.locale = locale_ta
        run.save()
        data = {'av': appver.code, 'locale': locale_ta.code}
        response = self.client.get(url, data)
        struct = json.loads(response.content)
        builds = [x for x in struct['items'] if x['type'] == 'Build']
        eq_(builds[0]['runid'], run.pk)

    def test_dashboard_locales_trees_av_query_generator(self):
        """the dashboard view takes request.GET parameters, massages them and
        turn them into a query string that gets passed to the JSON view later.
        """
        url = reverse(shipping.views.dashboard)
        response = self.client.get(url, {'locale': 'xxx'})
        eq_(response.status_code, 404)
        response = self.client.get(url, {'tree': 'xxx'})
        eq_(response.status_code, 404)
        response = self.client.get(url, {'av': 'xxx'})
        eq_(response.status_code, 404)

        def get_query(content):
            json_url = reverse('shipping-status_json')
            return re.findall('href="%s\?([^"]*)"' % json_url, content)[0]

        response = self.client.get(url)
        eq_(response.status_code, 200)
        eq_(get_query(response.content), '')

        Locale.objects.get_or_create(
          code='en-US',
          name='English',
        )

        response = self.client.get(url, {'locale': 'en-US'})
        eq_(response.status_code, 200)
        eq_(get_query(response.content), 'locale=en-US')

        response = self.client.get(url, {'locale': ['en-US', 'xxx']})
        eq_(response.status_code, 404)

        Locale.objects.get_or_create(
          code='ta',
          name='Tamil',
        )
        response = self.client.get(url, {'locale': ['en-US', 'ta']})
        eq_(response.status_code, 200)
        eq_(get_query(response.content), 'locale=en-US&locale=ta')

        appver, __ = self._create_appver_tree()
        tree, = Tree.objects.all()
        response = self.client.get(url, {'tree': tree.code})
        eq_(response.status_code, 200)
        eq_(get_query(response.content), 'tree=%s' % tree.code)

        response = self.client.get(url, {'tree': [tree.code, 'xxx']})
        eq_(response.status_code, 404)

        tree2 = Tree.objects.create(
          code=tree.code + '2',
          l10n=tree.l10n
        )

        response = self.client.get(url, {'tree': [tree.code, tree2.code]})
        eq_(response.status_code, 200)
        eq_(get_query(response.content),
            'tree=%s&tree=%s' % (tree.code, tree2.code))

        response = self.client.get(url, {'av': appver.code})
        eq_(response.status_code, 200)
        eq_(get_query(response.content), 'av=%s' % appver.code)

        appver2 = AppVersion.objects.create(
          app=appver.app,
          version='2',
          code='fx2',
          codename='foxier'
        )
        response = self.client.get(url, {'av': [appver.code, appver2.code]})
        eq_(response.status_code, 200)
        eq_(get_query(response.content),
            'av=%s&av=%s' % (appver.code, appver2.code))

        # combine them all
        data = {
          'locale': ['en-US', 'ta'],
          'av': [appver.code],
          'tree': [tree2.code, tree.code]
        }
        response = self.client.get(url, data)
        eq_(response.status_code, 200)
        query = get_query(response.content)
        for key, values in data.items():
            for value in values:
                ok_('%s=%s' % (key, value) in query)

    def test_dashboard_with_wrong_args(self):
        """dashboard() view takes arguments 'locale' and 'tree' and if these
        aren't correct that view should raise a 404"""
        url = reverse(shipping.views.dashboard)
        response = self.client.get(url, {'locale': 'xxx'})
        eq_(response.status_code, 404)

        locale, __ = Locale.objects.get_or_create(
          code='en-US',
          name='English',
        )

        locale, __ = Locale.objects.get_or_create(
          code='jp',
          name='Japanese',
        )

        response = self.client.get(url, {'locale': ['en-US', 'xxx']})
        eq_(response.status_code, 404)

        response = self.client.get(url, {'locale': ['en-US', 'jp']})
        eq_(response.status_code, 200)

        # test the tree argument now
        response = self.client.get(url, {'tree': 'xxx'})
        eq_(response.status_code, 404)

        self._create_appver_tree()
        assert Tree.objects.all().exists()
        tree, = Tree.objects.all()

        response = self.client.get(url, {'tree': ['xxx', tree.code]})
        eq_(response.status_code, 404)

        response = self.client.get(url, {'tree': [tree.code]})
        eq_(response.status_code, 200)


class DriversTest(ShippingTestCaseBase):
    def test_drivers(self):
        appver, tree = self._create_appver_tree()
        l10n_beta = Forest.objects.create(
          name='releases/l10n/mozilla-beta',
          url='http://hg.mozilla.org/releases/l10n/mozilla-beta/',
        )
        beta = Tree.objects.create(
          code='fennec_beta',
          l10n=l10n_beta,
        )
        appver = AppVersion.objects.create(
          app=appver.app,
          version='2',
          code='fennec2',
        )
        appver.trees.through.objects.create(tree=beta,
                                            appversion=appver,
                                            start=None,
                                            end=None)
        locale, __ = Locale.objects.get_or_create(
          code='en-US',
          name='English',
        )
        run = Run.objects.create(tree=tree, locale=locale)
        run.activate()
        run = Run.objects.create(tree=beta, locale=locale)
        run.activate()
        url = reverse('shipping-drivers')
        response = self.client.get(url)
        eq_(response.status_code, 200)
        apps_and_versions = response.context['apps_and_versions']
        eq_(apps_and_versions.keys(), [appver.app])
        avts = apps_and_versions.values()[0]
        # Fennec first
        ok_(hasattr(avts[0], 'json_changesets'))
        eq_(avts[0].tree, beta)
        # Firefox next
        ok_(not hasattr(avts[1], 'json_changesets'))
        eq_(avts[1].tree, tree)
