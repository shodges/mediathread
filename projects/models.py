from django.db import models
from django.db.models.loading import get_model
from django.db.models import Q

import re

from django.contrib.auth.models import User, Group
from courseaffils.models import Course
from modelversions import version_model

from threadedcomments.models import ThreadedComment
from django.contrib.contenttypes.models import ContentType
from structuredcollaboration.models import Collaboration

PUBLISH_OPTIONS = (('Assignment','Assignment for Class'),
                   ('PrivateEditorsAreOwners','Private - Only Author(s) Can View'),
                   ('InstructorShared','Submitted to Instructor'),
                   ('CourseProtected','Published to Whole Class'),
                   ('PublicEditorsAreOwners','Published to World (w/ Public Link)'),
                   )

SHORT_NAME = {
    "Assignment":'Assignment',
    "PrivateEditorsAreOwners":'Private',
    "InstructorShared":'Submitted',
    "CourseProtected":'Class',
    "PublicEditorsAreOwners":'World',
    "PrivateStudentAndFaculty":"with Instructors", 
    }

# Add keys from PUBLISH_OPTIONS if they should
# be filtered out of the choices for non-faculty
PUBLISH_OPTIONS_FACULTY_ONLY = ('Assignment',
                                )
class Project(models.Model):

    title = models.CharField(max_length=1024)

    course = models.ForeignKey(Course)

    #this is actually the LAST UPDATER for version-control purposes
    author = models.ForeignKey(User)

    #should be limited to course members
    #maybe just in the form:
    #http://collingrady.wordpress.com/2008/07/24/useful-form-tricks-in-django/
    participants = models.ManyToManyField(User,
                                          null=True,
                                          blank=True,
                                          related_name = 'projects',
                                          verbose_name = 'Authors',
                                          )

    only_save_if_changed = True
    only_save_version_if_changed_fields_to_ignore = ['modified','author']


    body = models.TextField(blank=True)

    #available to someone other than the authors 
    # -- at least, the instructor, if not the whole class
    submitted = models.BooleanField(default=False)

    #DEPRECATED: do not use this field
    feedback = models.TextField(blank=True, null=True)

    modified = models.DateTimeField('date modified', editable=False, auto_now=True)


    @models.permalink
    def get_workspace_url(self):
        return ('project-workspace', (), {
                'project_id': self.pk,
                })

    @models.permalink
    def get_absolute_url(self):
        return ('project-view', (), {
                'project_id': self.pk,
                })

    def subobjects(self, request, type):
        col = self.collaboration()
        if not col:
            return []
        children = col.children.filter(content_type=type)
        viewable_children = []
        for child in children:
            if child.permission_to("read", request) and child.content_object:
                viewable_children.append(child.content_object)
        return viewable_children
        
    def discussions(self, request):
        discussion_type = ContentType.objects.get_for_model(ThreadedComment)
        return self.subobjects(request, discussion_type)

    def responses_by(self, request, user):
        responses = self.responses(request)
        return [response for response in responses
                if response and user in response.content_object.participants.all()]

    def responses(self, request):
        project_type = ContentType.objects.get_for_model(Project)
        return self.subobjects(request, project_type)

    def is_assignment(self, request):
        if hasattr(self,'is_assignment_cached'):
            return self.is_assignment_cached
        col = self.collaboration()
        if not col:
            return False
        self.is_assignment_cached = col.permission_to("add_child", request)
        return self.is_assignment_cached

    def assignment(self):
        """
        Returns the Project object that this Project is a response to,
        or None if this Project is not a response to any other.
        """
        # TODO: this doesn't check content types in any way.
        # It assumes that obj->collab->parent->obj is-a Project.
        col = self.collaboration()
        if not col:
            return
        parent = col.get_parent()
        if not parent:
            return
        return parent.content_object

    def feedback_discussion(self):
        "returns the ThreadedComment object for Professor feedback (assuming it's private)"
        col = self.collaboration()
        if not col:
            return
        comm_type = ContentType.objects.get_for_model(ThreadedComment)

        feedback = col.children.filter(content_type=comm_type)
        if feedback:
            return feedback[0].content_object
            

    def save(self, *args, **kw):
        models.Model.save(self)
        self.participants.add(self.author)
        self.collaboration(sync_group=True)


    def public_url(self,col=None):
        if col is None:
            col = self.collaboration()
        if col and col._policy.policy_name=='PublicEditorsAreOwners':
            return col.get_absolute_url()
        

    def status(self):
        """
        The project's status, one of "draft submitted complete".split()
        """
        o = dict(PUBLISH_OPTIONS)

        col = self.collaboration()
        if col:
            status = SHORT_NAME.get(col._policy.policy_name, col._policy.policy_name)
            public_url = self.public_url(col)
            if public_url:
                status += ' (<a href="%s">public url</a>)' % public_url
            return status
        elif self.submitted:
            return u"Submitted"
        else:
            return u"Private"

    @classmethod
    def get_user_projects(cls,user,course):
        #TODO: change to members of project-related group
        return cls.objects.filter(Q(author=user, course=course)
                                  |Q(participants=user, course=course)
                                  ).distinct()

    def is_participant(self,user_or_request):
        user = getattr(user_or_request,'user',user_or_request)
        return (user == self.author
                or user in self.participants.all())

    def citations(self):
        """
        citation references to sherdnotes
        """
        SherdNote = models.get_model('djangosherd','SherdNote')
        return SherdNote.objects.references_in_string(self.body)
            
    @property
    def content_object(self):
        """Support similar property as Comment model"""
        return self

    def attribution_list(self):
        participants = list(self.participants.all())
        if self.author not in participants:
            participants.insert(0,self.author)
        return participants

    def attribution(self, participants=None):
        participants = self.attribution_list()
        return ', '.join([p.get_full_name() or p.username
                for p in participants])

    def __unicode__(self):
        return u'%s <%r> by %s' % (self.title, self.pk, self.attribution())

    def class_visible(self):
        col = self.collaboration()
        if not col:
            # legacy
            return self.submitted
    
        return (col._policy.policy_name != 'PrivateEditorsAreOwners'
                and col._policy.policy_name != 'InstructorShared')
        
    def visible(self,request):
        col = self.collaboration()
        if col:
            return col.permission_to('read',request)
        else:
            return self.submitted
    
    def collaboration(self,request=None,sync_group=False):
        col = None
        policy = None
        if request and request.method == "POST":
            policy = request.POST.get('publish','PrivateEditorsAreOwners')

        try:
            col = Collaboration.get_associated_collab(self)
        except Collaboration.DoesNotExist:
            if policy is None:
                policy = "PrivateEditorsAreOwners"
            if request is not None:
                col = Collaboration.objects.create(user=self.author,
                                                   title=self.title,
                                                   content_object=self,
                                                   context=request.collaboration_context,
                                                   policy=policy,
                                                   )
        if col is None: # iff collab did not exist and request is None
            return

        if sync_group:
            part = self.participants.all()
            if len(part) > 1 or (col.group_id and col.group.user_set.count() > 1) \
                    or (self.author not in part and len(part) > 0):
                colgrp = col.have_group()
                already_grp = set(colgrp.user_set.all())
                for p in part:
                    if p in already_grp:
                        already_grp.discard(p)
                    else:
                        colgrp.user_set.add(p)
                for oldp in already_grp:
                    colgrp.user_set.remove(oldp)
            if request and request.method == "POST" and \
                    (col.policy != policy or col.title != self.title):
                col.title = self.title
                col.policy = policy
                col.save()

        return col

    def content_metrics(self):
        "Do some rough heuristics on how much each author contributed"
        last_content = ''
        author_contributions = {}
        for v in self.versions:
            change = len(v.body) - len(last_content)
            author_contributions.setdefault(v.author,[0,0])
            if change > 0: #track adds
                author_contributions[v.author][0] += change
            elif change < 0: #track deletes
                author_contributions[v.author][1] -= change
            last_content = v.body
        return author_contributions

    @property
    def dir(self):
        return dir(self)
        
        
        
ProjectVersion = version_model(Project)
