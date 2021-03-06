from django.conf.urls.defaults import *
from django.conf import settings
import os.path

media_root = os.path.join(os.path.dirname(__file__),"media")

urlpatterns = patterns(
    'assetmgr.views',
    # urls available from /asset/
    url(r'^$', 'container_view',
        name='asset-container'),

    #NOTE: explore and explore/redirect are re-referenced in ../urls.py
    url(r'^explore/?$', 'archive_explore', name='asset-archiveexplore'),
    url(r'^explore/redirect/?$', 'archive_redirect', name='asset-archiveredirect'),

    url(r'^json/(?P<asset_id>\d+)/$', 
        'asset_json', name="asset-json"),

    url(r'^(?P<asset_id>\d+)/$', 
        'asset_workspace', name="asset-view"),

    url(r'^(?P<asset_id>\d+)/annotations/$',
        'annotationcontainerview',
        name="annotations-container"),
    url(r'^(?P<asset_id>\d+)/annotations/(?P<annot_id>\d+)/$',
        'annotationview',
        name="annotation-form"),
    )
