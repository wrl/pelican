# -*- coding: utf-8 -*-
from __future__ import with_statement

import os
import locale
import logging

from codecs import open
from feedgenerator import Atom1Feed, Rss201rev2Feed
from jinja2 import Markup
from pelican.paginator import Paginator
from pelican.utils import get_relative_path, set_date_tzinfo

logger = logging.getLogger(__name__)


class Writer(object):

    def __init__(self, output_path, settings=None):
        self.output_path = output_path
        self.reminder = dict()
        self.settings = settings or {}

    def _create_new_feed(self, feed_type, context):
        feed_class = Rss201rev2Feed if feed_type == 'rss' else Atom1Feed
        sitename = Markup(context['SITENAME']).striptags()
        feed = feed_class(
            title=sitename,
            link=(self.site_url + '/'),
            feed_url=self.feed_url,
            description=context.get('SITESUBTITLE', ''))
        return feed

    def _add_item_to_the_feed(self, feed, item):

        title = Markup(item.title).striptags()
        feed.add_item(
            title=title,
            link='%s/%s' % (self.site_url, item.url),
            unique_id='tag:%s,%s:%s' % (self.site_url.replace('http://', ''),
                                        item.date.date(), item.url),
            description=item.get_content(self.site_url),
            categories=item.tags if hasattr(item, 'tags') else None,
            author_name=getattr(item, 'author', ''),
            pubdate=set_date_tzinfo(item.date,
                self.settings.get('TIMEZONE', None)))

    def write_feed(self, elements, context, filename=None, feed_type='atom'):
        """Generate a feed with the list of articles provided

        Return the feed. If no output_path or filename is specified, just
        return the feed object.

        :param elements: the articles to put on the feed.
        :param context: the context to get the feed metadata.
        :param filename: the filename to output.
        :param feed_type: the feed type to use (atom or rss)
        """
        old_locale = locale.setlocale(locale.LC_ALL)
        locale.setlocale(locale.LC_ALL, 'C')
        try:
            self.site_url = context.get('SITEURL', get_relative_path(filename))
            self.feed_domain = context.get('FEED_DOMAIN')
            self.feed_url = '%s/%s' % (self.feed_domain, filename)

            feed = self._create_new_feed(feed_type, context)

            max_items = len(elements)
            if self.settings['FEED_MAX_ITEMS']:
                max_items = min(self.settings['FEED_MAX_ITEMS'], max_items)
            for i in xrange(max_items):
                self._add_item_to_the_feed(feed, elements[i])

            if filename:
                complete_path = os.path.join(self.output_path, filename)
                try:
                    os.makedirs(os.path.dirname(complete_path))
                except Exception:
                    pass
                fp = open(complete_path, 'w')
                feed.write(fp, 'utf-8')
                logger.info('writing %s' % complete_path)

                fp.close()
            return feed
        finally:
            locale.setlocale(locale.LC_ALL, old_locale)

    def write_file(self, name, template, context, relative_urls=True,
        paginated=None, **kwargs):
        """Render the template and write the file.

        :param name: name of the file to output
        :param template: template to use to generate the content
        :param context: dict to pass to the templates.
        :param relative_urls: use relative urls or absolutes ones
        :param paginated: dict of article list to paginate - must have the
            same length (same list in different orders)
        :param **kwargs: additional variables to pass to the templates
        """

        if name is False:
            return
        elif not name:
            # other stuff, just return for now
            return

        def _write_file(template, localcontext, output_path, name):
            """Render the template write the file."""
            old_locale = locale.setlocale(locale.LC_ALL)
            locale.setlocale(locale.LC_ALL, 'C')
            try:
                output = template.render(localcontext)
            finally:
                locale.setlocale(locale.LC_ALL, old_locale)
            filename = os.sep.join((output_path, name))
            try:
                os.makedirs(os.path.dirname(filename))
            except Exception:
                pass
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output)
            logger.info(u'writing %s' % filename)

        localcontext = context.copy()
        if relative_urls:
            relative_path = get_relative_path(name)
            context['localsiteurl'] = relative_path
            localcontext['SITEURL'] = relative_path

        localcontext['output_file'] = name
        localcontext.update(kwargs)

        # check paginated
        paginated = paginated or {}
        if paginated:
            # pagination needed, init paginators
            paginators = {}
            for key in paginated.iterkeys():
                object_list = paginated[key]

                if self.settings.get('DEFAULT_PAGINATION'):
                    paginators[key] = Paginator(object_list,
                        self.settings.get('DEFAULT_PAGINATION'),
                        self.settings.get('DEFAULT_ORPHANS'))
                else:
                    paginators[key] = Paginator(object_list, len(object_list))

            # generated pages, and write
            name_root, ext = os.path.splitext(name)
            for page_num in range(paginators.values()[0].num_pages):
                paginated_localcontext = localcontext.copy()
                for key in paginators.iterkeys():
                    paginator = paginators[key]
                    page = paginator.page(page_num + 1)
                    paginated_localcontext.update(
                            {'%s_paginator' % key: paginator,
                             '%s_page' % key: page})
                if page_num > 0:
                    paginated_name = '%s%s%s' % (
                        name_root, page_num + 1, ext)
                else:
                    paginated_name = name

                _write_file(template, paginated_localcontext, self.output_path,
                    paginated_name)
        else:
            # no pagination
            _write_file(template, localcontext, self.output_path, name)
