from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns(
    'mediathread_main.views',
    #urls prefix at root AND 'yourspace/' 
    url(r'^$',
        'class_listing',
        name='class-listing'),
    
    url(r'^portal$',
        'class_portal',
        name='class-portal'),
                           
    url(r'^all/asset/$',
        'all_records',
        name='all-records'),
    
    url(r'^(?P<user_name>\w[^/]*)/$',
        'your_space',
        name='your-space'),


    url(r'^(?P<user_name>\w[^/]*)/asset/(?P<asset_id>\d+)/$',
        'remove_record',
        name='my-asset-notes'
        ),

    url(r'^(?P<user_name>\w[^/]*)/asset/$',
        'your_records',
        name='your-space-records'),

)                       