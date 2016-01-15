#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2015        Intel Corporation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from toastergui.widgets import ToasterTable
from toastergui.querysetfilter import QuerysetFilter
from orm.models import Recipe, ProjectLayer, Layer_Version, Machine, Project
from orm.models import CustomImageRecipe, Package, Build, LogMessage, Task
from django.db.models import Q, Max, Count
from django.conf.urls import url
from django.core.urlresolvers import reverse
from django.views.generic import TemplateView
import itertools

from toastergui.tablefilter import TableFilter
from toastergui.tablefilter import TableFilterActionToggle
from toastergui.tablefilter import TableFilterActionDateRange
from toastergui.tablefilter import TableFilterActionDay

class ProjectFilters(object):
    def __init__(self, project_layers):
        self.in_project = QuerysetFilter(Q(layer_version__in=project_layers))
        self.not_in_project = QuerysetFilter(~Q(layer_version__in=project_layers))

class LayersTable(ToasterTable):
    """Table of layers in Toaster"""

    def __init__(self, *args, **kwargs):
        super(LayersTable, self).__init__(*args, **kwargs)
        self.default_orderby = "layer__name"
        self.title = "Compatible layers"

    def get_context_data(self, **kwargs):
        context = super(LayersTable, self).get_context_data(**kwargs)

        project = Project.objects.get(pk=kwargs['pid'])
        context['project'] = project

        return context

    def setup_filters(self, *args, **kwargs):
        project = Project.objects.get(pk=kwargs['pid'])
        self.project_layers = ProjectLayer.objects.filter(project=project)

        in_current_project_filter = TableFilter(
            "in_current_project",
            "Filter by project layers"
        )

        criteria = Q(projectlayer__in=self.project_layers)

        in_project_action = TableFilterActionToggle(
            "in_project",
            "Layers added to this project",
            QuerysetFilter(criteria)
        )

        not_in_project_action = TableFilterActionToggle(
            "not_in_project",
            "Layers not added to this project",
            QuerysetFilter(~criteria)
        )

        in_current_project_filter.add_action(in_project_action)
        in_current_project_filter.add_action(not_in_project_action)
        self.add_filter(in_current_project_filter)

    def setup_queryset(self, *args, **kwargs):
        prj = Project.objects.get(pk = kwargs['pid'])
        compatible_layers = prj.get_all_compatible_layer_versions()

        self.static_context_extra['current_layers'] = \
                prj.get_project_layer_versions(pk=True)

        self.queryset = compatible_layers.order_by(self.default_orderby)

    def setup_columns(self, *args, **kwargs):

        layer_link_template = '''
        <a href="{% url 'layerdetails' extra.pid data.id %}">
          {{data.layer.name}}
        </a>
        '''

        self.add_column(title="Layer",
                        hideable=False,
                        orderable=True,
                        static_data_name="layer__name",
                        static_data_template=layer_link_template)

        self.add_column(title="Summary",
                        field_name="layer__summary")

        git_url_template = '''
        <a href="{% url 'layerdetails' extra.pid data.id %}">
          <code>{{data.layer.vcs_url}}</code>
        </a>
        {% if data.get_vcs_link_url %}
        <a target="_blank" href="{{ data.get_vcs_link_url }}">
           <i class="icon-share get-info"></i>
        </a>
        {% endif %}
        '''

        self.add_column(title="Git repository URL",
                        help_text="The Git repository for the layer source code",
                        hidden=True,
                        static_data_name="layer__vcs_url",
                        static_data_template=git_url_template)

        git_dir_template = '''
        <a href="{% url 'layerdetails' extra.pid data.id %}">
         <code>{{data.dirpath}}</code>
        </a>
        {% if data.dirpath and data.get_vcs_dirpath_link_url %}
        <a target="_blank" href="{{ data.get_vcs_dirpath_link_url }}">
          <i class="icon-share get-info"></i>
        </a>
        {% endif %}'''

        self.add_column(title="Subdirectory",
                        help_text="The layer directory within the Git repository",
                        hidden=True,
                        static_data_name="git_subdir",
                        static_data_template=git_dir_template)

        revision_template =  '''
        {% load projecttags  %}
        {% with vcs_ref=data.get_vcs_reference %}
        {% if vcs_ref|is_shaid %}
        <a class="btn" data-content="<ul class='unstyled'> <li>{{vcs_ref}}</li> </ul>">
        {{vcs_ref|truncatechars:10}}
        </a>
        {% else %}
        {{vcs_ref}}
        {% endif %}
        {% endwith %}
        '''

        self.add_column(title="Revision",
                        help_text="The Git branch, tag or commit. For the layers from the OpenEmbedded layer source, the revision is always the branch compatible with the Yocto Project version you selected for this project",
                        static_data_name="revision",
                        static_data_template=revision_template)

        deps_template = '''
        {% with ods=data.dependencies.all%}
        {% if ods.count %}
            <a class="btn" title="<a href='{% url "layerdetails" extra.pid data.id %}'>{{data.layer.name}}</a> dependencies"
        data-content="<ul class='unstyled'>
        {% for i in ods%}
        <li><a href='{% url "layerdetails" extra.pid i.depends_on.pk %}'>{{i.depends_on.layer.name}}</a></li>
        {% endfor %}
        </ul>">
        {{ods.count}}
        </a>
        {% endif %}
        {% endwith %}
        '''

        self.add_column(title="Dependencies",
                        help_text="Other layers a layer depends upon",
                        static_data_name="dependencies",
                        static_data_template=deps_template)

        self.add_column(title="Add | Delete",
                        help_text="Add or delete layers to / from your project",
                        hideable=False,
                        filter_name="in_current_project",
                        static_data_name="add-del-layers",
                        static_data_template='{% include "layer_btn.html" %}')

        project = Project.objects.get(pk=kwargs['pid'])
        self.add_column(title="LayerDetailsUrl",
                        displayable = False,
                        field_name="layerdetailurl",
                        computation = lambda x: reverse('layerdetails', args=(project.id, x.id)))

        self.add_column(title="name",
                        displayable = False,
                        field_name="name",
                        computation = lambda x: x.layer.name)


class MachinesTable(ToasterTable):
    """Table of Machines in Toaster"""

    def __init__(self, *args, **kwargs):
        super(MachinesTable, self).__init__(*args, **kwargs)
        self.empty_state = "No machines maybe you need to do a build?"
        self.title = "Compatible machines"
        self.default_orderby = "name"

    def get_context_data(self, **kwargs):
        context = super(MachinesTable, self).get_context_data(**kwargs)
        context['project'] = Project.objects.get(pk=kwargs['pid'])
        return context

    def setup_filters(self, *args, **kwargs):
        project = Project.objects.get(pk=kwargs['pid'])

        project_filters = ProjectFilters(self.project_layers)

        in_current_project_filter = TableFilter(
            "in_current_project",
            "Filter by project machines"
        )

        in_project_action = TableFilterActionToggle(
            "in_project",
            "Machines provided by layers added to this project",
            project_filters.in_project
        )

        not_in_project_action = TableFilterActionToggle(
            "not_in_project",
            "Machines provided by layers not added to this project",
            project_filters.not_in_project
        )

        in_current_project_filter.add_action(in_project_action)
        in_current_project_filter.add_action(not_in_project_action)
        self.add_filter(in_current_project_filter)

    def setup_queryset(self, *args, **kwargs):
        prj = Project.objects.get(pk = kwargs['pid'])
        self.queryset = prj.get_all_compatible_machines()
        self.queryset = self.queryset.order_by(self.default_orderby)

        self.static_context_extra['current_layers'] = \
                self.project_layers = \
                prj.get_project_layer_versions(pk=True)

    def setup_columns(self, *args, **kwargs):

        self.add_column(title="Machine",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        self.add_column(title="Description",
                        field_name="description")

        layer_link_template = '''
        <a href="{% url 'layerdetails' extra.pid data.layer_version.id %}">
        {{data.layer_version.layer.name}}</a>
        '''

        self.add_column(title="Layer",
                        static_data_name="layer_version__layer__name",
                        static_data_template=layer_link_template,
                        orderable=True)

        self.add_column(title="Revision",
                        help_text="The Git branch, tag or commit. For the layers from the OpenEmbedded layer source, the revision is always the branch compatible with the Yocto Project version you selected for this project",
                        hidden=True,
                        field_name="layer_version__get_vcs_reference")

        machine_file_template = '''<code>conf/machine/{{data.name}}.conf</code>
        <a href="{{data.get_vcs_machine_file_link_url}}" target="_blank"><i class="icon-share get-info"></i></a>'''

        self.add_column(title="Machine file",
                        hidden=True,
                        static_data_name="machinefile",
                        static_data_template=machine_file_template)

        self.add_column(title="Select",
                        help_text="Sets the selected machine as the project machine. You can only have one machine per project",
                        hideable=False,
                        filter_name="in_current_project",
                        static_data_name="add-del-layers",
                        static_data_template='{% include "machine_btn.html" %}')


class LayerMachinesTable(MachinesTable):
    """ Smaller version of the Machines table for use in layer details """

    def __init__(self, *args, **kwargs):
        super(LayerMachinesTable, self).__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(LayerMachinesTable, self).get_context_data(**kwargs)
        context['layerversion'] = Layer_Version.objects.get(pk=kwargs['layerid'])
        return context


    def setup_queryset(self, *args, **kwargs):
        MachinesTable.setup_queryset(self, *args, **kwargs)

        self.queryset = self.queryset.filter(layer_version__pk=int(kwargs['layerid']))
        self.queryset = self.queryset.order_by(self.default_orderby)
        self.static_context_extra['in_prj'] = ProjectLayer.objects.filter(Q(project=kwargs['pid']) & Q(layercommit=kwargs['layerid'])).count()

    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Machine",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        self.add_column(title="Description",
                        field_name="description")

        select_btn_template = '<a href="{% url "project" extra.pid %}?setMachine={{data.name}}" class="btn btn-block select-machine-btn" {% if extra.in_prj == 0%}disabled="disabled"{%endif%}>Select machine</a>'

        self.add_column(title="Select machine",
                        static_data_name="add-del-layers",
                        static_data_template=select_btn_template)


class RecipesTable(ToasterTable):
    """Table of All Recipes in Toaster"""

    def __init__(self, *args, **kwargs):
        super(RecipesTable, self).__init__(*args, **kwargs)
        self.empty_state = "Toaster has no recipe information. To generate recipe information you can configure a layer source then run a build."

    build_col = { 'title' : "Build",
            'help_text' : "Add or delete recipes to and from your project",
            'hideable' : False,
            'filter_name' : "in_current_project",
            'static_data_name' : "add-del-layers",
            'static_data_template' : '{% include "recipe_btn.html" %}'}

    def get_context_data(self, **kwargs):
        project = Project.objects.get(pk=kwargs['pid'])
        context = super(RecipesTable, self).get_context_data(**kwargs)

        context['project'] = project

        context['projectlayers'] = map(lambda prjlayer: prjlayer.layercommit.id, ProjectLayer.objects.filter(project=context['project']))

        return context

    def setup_filters(self, *args, **kwargs):
        project_filters = ProjectFilters(self.project_layers)

        table_filter = TableFilter(
            'in_current_project',
            'Filter by project recipes'
        )

        in_project_action = TableFilterActionToggle(
            'in_project',
            'Recipes provided by layers added to this project',
            project_filters.in_project
        )

        not_in_project_action = TableFilterActionToggle(
            'not_in_project',
            'Recipes provided by layers not added to this project',
            project_filters.not_in_project
        )

        table_filter.add_action(in_project_action)
        table_filter.add_action(not_in_project_action)
        self.add_filter(table_filter)

    def setup_queryset(self, *args, **kwargs):
        prj = Project.objects.get(pk = kwargs['pid'])

        # Project layers used by the filters
        self.project_layers = prj.get_project_layer_versions(pk=True)

        # Project layers used to switch the button states
        self.static_context_extra['current_layers'] = self.project_layers

        self.queryset = prj.get_all_compatible_recipes()


    def setup_columns(self, *args, **kwargs):

        self.add_column(title="Version",
                        hidden=False,
                        field_name="version")

        self.add_column(title="Description",
                        field_name="get_description_or_summary")

        recipe_file_template = '''
        <code>{{data.file_path}}</code>
        <a href="{{data.get_vcs_recipe_file_link_url}}" target="_blank">
          <i class="icon-share get-info"></i>
        </a>
         '''

        self.add_column(title="Recipe file",
                        help_text="Path to the recipe .bb file",
                        hidden=True,
                        static_data_name="recipe-file",
                        static_data_template=recipe_file_template)

        self.add_column(title="Section",
                        help_text="The section in which recipes should be categorized",
                        hidden=True,
                        orderable=True,
                        field_name="section")

        layer_link_template = '''
        <a href="{% url 'layerdetails' extra.pid data.layer_version.id %}">
        {{data.layer_version.layer.name}}</a>
        '''

        self.add_column(title="Layer",
                        help_text="The name of the layer providing the recipe",
                        orderable=True,
                        static_data_name="layer_version__layer__name",
                        static_data_template=layer_link_template)

        self.add_column(title="License",
                        help_text="The list of source licenses for the recipe. Multiple license names separated by the pipe character indicates a choice between licenses. Multiple license names separated by the ampersand character indicates multiple licenses exist that cover different parts of the source",
                        hidden=True,
                        orderable=True,
                        field_name="license")

        self.add_column(title="Revision",
                        hidden=True,
                        field_name="layer_version__get_vcs_reference")


class LayerRecipesTable(RecipesTable):
    """ Smaller version of the Recipes table for use in layer details """

    def __init__(self, *args, **kwargs):
        super(LayerRecipesTable, self).__init__(*args, **kwargs)
        self.default_orderby = "name"

    def get_context_data(self, **kwargs):
        context = super(LayerRecipesTable, self).get_context_data(**kwargs)
        context['layerversion'] = Layer_Version.objects.get(pk=kwargs['layerid'])
        return context


    def setup_queryset(self, *args, **kwargs):
        self.queryset = \
                Recipe.objects.filter(layer_version__pk=int(kwargs['layerid']))

        self.queryset = self.queryset.order_by(self.default_orderby)
        self.static_context_extra['in_prj'] = ProjectLayer.objects.filter(Q(project=kwargs['pid']) & Q(layercommit=kwargs['layerid'])).count()

    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Recipe",
                        help_text="Information about a single piece of software, including where to download the source, configuration options, how to compile the source files and how to package the compiled output",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        self.add_column(title="Version",
                        field_name="version")

        self.add_column(title="Description",
                        field_name="get_description_or_summary")

        build_recipe_template ='<button class="btn btn-block build-recipe-btn" data-recipe-name="{{data.name}}" {%if extra.in_prj == 0 %}disabled="disabled"{%endif%}>Build recipe</button>'

        self.add_column(title="Build recipe",
                        static_data_name="add-del-layers",
                        static_data_template=build_recipe_template)

class CustomImagesTable(ToasterTable):
    """ Table to display your custom images """
    def __init__(self, *args, **kwargs):
        super(CustomImagesTable, self).__init__(*args, **kwargs)
        self.title = "Custom images"
        self.default_orderby = "name"

    def get_context_data(self, **kwargs):
        context = super(CustomImagesTable, self).get_context_data(**kwargs)
        project = Project.objects.get(pk=kwargs['pid'])
        context['project'] = project
        context['projectlayers'] = map(lambda prjlayer: prjlayer.layercommit.id, ProjectLayer.objects.filter(project=context['project']))
        return context

    def setup_queryset(self, *args, **kwargs):
        prj = Project.objects.get(pk = kwargs['pid'])
        self.queryset = CustomImageRecipe.objects.filter(project=prj)
        self.queryset = self.queryset.order_by(self.default_orderby)

    def setup_columns(self, *args, **kwargs):

        name_link_template = '''
        <a href="{% url 'customrecipe' extra.pid data.id %}">
          {{data.name}}
        </a>
        '''

        self.add_column(title="Custom image",
                        hideable=False,
                        static_data_name="name",
                        static_data_template=name_link_template)

        self.add_column(title="Recipe file",
                        static_data_name='recipe_file',
                        static_data_template='')

        approx_packages_template = '<a href="#imagedetails">{{data.packages.all|length}}</a>'
        self.add_column(title="Approx packages",
                        static_data_name='approx_packages',
                        static_data_template=approx_packages_template)


        build_btn_template = '''<button data-recipe-name="{{data.name}}"
        class="btn btn-block build-recipe-btn" style="margin-top: 5px;" >
        Build</button>'''

        self.add_column(title="Build",
                        hideable=False,
                        static_data_name='build_custom_img',
                        static_data_template=build_btn_template)

class ImageRecipesTable(RecipesTable):
    """ A subset of the recipes table which displayed just image recipes """

    def __init__(self, *args, **kwargs):
        super(ImageRecipesTable, self).__init__(*args, **kwargs)
        self.title = "Compatible image recipes"
        self.default_orderby = "name"

    def setup_queryset(self, *args, **kwargs):
        super(ImageRecipesTable, self).setup_queryset(*args, **kwargs)

        self.queryset = self.queryset.filter(is_image=True)
        self.queryset = self.queryset.order_by(self.default_orderby)


    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Image recipe",
                        help_text="When you build an image recipe, you get an "
                                  "image: a root file system you can"
                                  "deploy to a machine",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        super(ImageRecipesTable, self).setup_columns(*args, **kwargs)

        self.add_column(**RecipesTable.build_col)


class NewCustomImagesTable(ImageRecipesTable):
    """ Table which displays Images recipes which can be customised """
    def __init__(self, *args, **kwargs):
        super(NewCustomImagesTable, self).__init__(*args, **kwargs)
        self.title = "Select the image recipe you want to customise"

    def setup_queryset(self, *args, **kwargs):
        super(ImageRecipesTable, self).setup_queryset(*args, **kwargs)

        self.queryset = self.queryset.filter(is_image=True)

    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Image recipe",
                        help_text="When you build an image recipe, you get an "
                                  "image: a root file system you can"
                                  "deploy to a machine",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        super(ImageRecipesTable, self).setup_columns(*args, **kwargs)

        self.add_column(title="Customise",
                        hideable=False,
                        filter_name="in_current_project",
                        static_data_name="customise-or-add-recipe",
                        static_data_template='{% include "customise_btn.html" %}')


class SoftwareRecipesTable(RecipesTable):
    """ Displays just the software recipes """
    def __init__(self, *args, **kwargs):
        super(SoftwareRecipesTable, self).__init__(*args, **kwargs)
        self.title = "Compatible software recipes"
        self.default_orderby = "name"

    def setup_queryset(self, *args, **kwargs):
        super(SoftwareRecipesTable, self).setup_queryset(*args, **kwargs)

        self.queryset = self.queryset.filter(is_image=False)


    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Software recipe",
                        help_text="Information about a single piece of "
                        "software, including where to download the source, "
                        "configuration options, how to compile the source "
                        "files and how to package the compiled output",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        super(SoftwareRecipesTable, self).setup_columns(*args, **kwargs)

        self.add_column(**RecipesTable.build_col)


class SelectPackagesTable(ToasterTable):
    """ Table to display the packages to add and remove from an image """

    def __init__(self, *args, **kwargs):
        super(SelectPackagesTable, self).__init__(*args, **kwargs)
        self.title = "Add | Remove packages"

    def setup_queryset(self, *args, **kwargs):
        cust_recipe = CustomImageRecipe.objects.get(pk=kwargs['recipeid'])
        prj = Project.objects.get(pk = kwargs['pid'])

        current_packages = cust_recipe.packages.all()

        # Get all the packages that are in the custom image
        # Get all the packages built by builds in the current project
        # but not those ones that are already in the custom image
        self.queryset = Package.objects.filter(
                            Q(pk__in=current_packages) |
                            (Q(build__project=prj) &
                            ~Q(name__in=current_packages.values_list('name'))))

        self.queryset = self.queryset.order_by('name')

        self.static_context_extra['recipe_id'] = kwargs['recipeid']
        self.static_context_extra['current_packages'] = \
                cust_recipe.packages.values_list('pk', flat=True)

    def setup_columns(self, *args, **kwargs):
        self.add_column(title="Package",
                        hideable=False,
                        orderable=True,
                        field_name="name")

        self.add_column(title="Package Version",
                        field_name="version")

        self.add_column(title="Approx Size",
                        orderable=True,
                        static_data_name="size",
                        static_data_template="{% load projecttags %} \
                        {{data.size|filtered_filesizeformat}}")
        self.add_column(title="summary",
                        field_name="summary")

        self.add_column(title="Add | Remove",
                        help_text="Use the add and remove buttons to modify "
                        "the package content of you custom image",
                        static_data_name="add_rm_pkg_btn",
                        static_data_template='{% include "pkg_add_rm_btn.html" %}')

class ProjectsTable(ToasterTable):
    """Table of projects in Toaster"""

    def __init__(self, *args, **kwargs):
        super(ProjectsTable, self).__init__(*args, **kwargs)
        self.default_orderby = '-updated'
        self.title = 'All projects'
        self.static_context_extra['Build'] = Build

    def get_context_data(self, **kwargs):
        return super(ProjectsTable, self).get_context_data(**kwargs)

    def setup_queryset(self, *args, **kwargs):
        queryset = Project.objects.all()

        # annotate each project with its number of builds
        queryset = queryset.annotate(num_builds=Count('build'))

        # exclude the command line builds project if it has no builds
        q_default_with_builds = Q(is_default=True) & Q(num_builds__gt=0)
        queryset = queryset.filter(Q(is_default=False) |
                                   q_default_with_builds)

        # order rows
        queryset = queryset.order_by(self.default_orderby)

        self.queryset = queryset

    # columns: last activity on (updated) - DEFAULT, project (name), release, machine, number of builds, last build outcome, recipe (name),  errors, warnings, image files
    def setup_columns(self, *args, **kwargs):
        name_template = '''
        {% load project_url_tag %}
        <span data-project-field="name">
          <a href="{% project_url data %}">
            {{data.name}}
          </a>
        </span>
        '''

        last_activity_on_template = '''
        {% load project_url_tag %}
        <span data-project-field="updated">
          <a href="{% project_url data %}">
            {{data.updated | date:"d/m/y H:i"}}
          </a>
        </span>
        '''

        release_template = '''
        <span data-project-field="release">
          {% if data.release %}
            <a href="{% url 'project' data.id %}#project-details">
                {{data.release.name}}
            </a>
          {% elif data.is_default %}
            <span class="muted">Not applicable</span>
            <i class="icon-question-sign get-help hover-help"
               data-original-title="This project does not have a release set.
               It simply collects information about the builds you start from
               the command line while Toaster is running"
               style="visibility: hidden;">
            </i>
          {% else %}
            No release available
          {% endif %}
        </span>
        '''

        machine_template = '''
        <span data-project-field="machine">
          {% if data.is_default %}
            <span class="muted">Not applicable</span>
            <i class="icon-question-sign get-help hover-help"
               data-original-title="This project does not have a machine
               set. It simply collects information about the builds you
               start from the command line while Toaster is running"
               style="visibility: hidden;"></i>
          {% else %}
            <a href="{% url 'project' data.id %}#machine-distro">
              {{data.get_current_machine_name}}
            </a>
          {% endif %}
        </span>
        '''

        number_of_builds_template = '''
        {% if data.get_number_of_builds > 0 %}
          <a href="{% url 'projectbuilds' data.id %}">
            {{data.get_number_of_builds}}
          </a>
        {% else %}
          <span class="muted">0</span>
        {% endif %}
        '''

        last_build_outcome_template = '''
        {% if data.get_number_of_builds > 0 %}
          <a href="{% url 'builddashboard' data.get_last_build_id %}">
            {% if data.get_last_outcome == extra.Build.SUCCEEDED %}
              <i class="icon-ok-sign success"></i>
            {% elif data.get_last_outcome == extra.Build.FAILED %}
              <i class="icon-minus-sign error"></i>
            {% endif %}
          </a>
        {% endif %}
        '''

        recipe_template = '''
        {% if data.get_number_of_builds > 0 %}
          <a href="{% url "builddashboard" data.get_last_build_id %}">
            {{data.get_last_target}}
          </a>
        {% endif %}
        '''

        errors_template = '''
        {% if data.get_number_of_builds > 0 %}
          <a class="errors.count error"
             href="{% url "builddashboard" data.get_last_build_id %}#errors">
            {{data.get_last_errors}} error{{data.get_last_errors | pluralize}}
          </a>
        {% endif %}
        '''

        warnings_template = '''
        {% if data.get_number_of_builds > 0 %}
          <a class="warnings.count warning"
             href="{% url "builddashboard" data.get_last_build_id %}#warnings">
            {{data.get_last_warnings}} warning{{data.get_last_warnings | pluralize}}
          </a>
        {% endif %}
        '''

        image_files_template = '''
        {% if data.get_number_of_builds > 0 and data.get_last_outcome == extra.Build.SUCCEEDED %}
          <a href="{% url "builddashboard" data.get_last_build_id %}#images">
            {{data.get_last_build_extensions}}
          </a>
        {% endif %}
        '''

        self.add_column(title='Project',
                        hideable=False,
                        orderable=True,
                        static_data_name='name',
                        static_data_template=name_template)

        self.add_column(title='Last activity on',
                        help_text='Starting date and time of the \
                                   last project build. If the project has no \
                                   builds, this shows the date the project was \
                                   created.',
                        hideable=True,
                        orderable=True,
                        static_data_name='updated',
                        static_data_template=last_activity_on_template)

        self.add_column(title='Release',
                        help_text='The version of the build system used by \
                                   the project',
                        hideable=False,
                        orderable=True,
                        static_data_name='release',
                        static_data_template=release_template)

        self.add_column(title='Machine',
                        help_text='The hardware currently selected for the \
                                   project',
                        hideable=False,
                        orderable=False,
                        static_data_name='machine',
                        static_data_template=machine_template)

        self.add_column(title='Number of builds',
                        help_text='The number of builds which have been run \
                                   for the project',
                        hideable=True,
                        orderable=False,
                        static_data_name='number_of_builds',
                        static_data_template=number_of_builds_template)

        self.add_column(title='Last build outcome',
                        help_text='Indicates whether the last project build \
                                   completed successfully or failed',
                        hideable=True,
                        orderable=False,
                        static_data_name='last_build_outcome',
                        static_data_template=last_build_outcome_template)

        self.add_column(title='Recipe',
                        help_text='The last recipe which was built in this \
                                   project',
                        hideable=True,
                        orderable=False,
                        static_data_name='recipe_name',
                        static_data_template=recipe_template)

        self.add_column(title='Errors',
                        help_text='The number of errors encountered during \
                                   the last project build (if any)',
                        hideable=True,
                        orderable=False,
                        static_data_name='errors',
                        static_data_template=errors_template)

        self.add_column(title='Warnings',
                        help_text='The number of warnings encountered during \
                                   the last project build (if any)',
                        hideable=True,
                        orderable=False,
                        static_data_name='warnings',
                        static_data_template=warnings_template)

        self.add_column(title='Image files',
                        help_text='The root file system types produced by \
                                   the last project build',
                        hideable=True,
                        orderable=False,
                        static_data_name='image_files',
                        static_data_template=image_files_template)

class BuildsTable(ToasterTable):
    """Table of builds in Toaster"""

    def __init__(self, *args, **kwargs):
        super(BuildsTable, self).__init__(*args, **kwargs)
        self.default_orderby = '-completed_on'
        self.title = 'All builds'
        self.static_context_extra['Build'] = Build
        self.static_context_extra['Task'] = Task

    def get_context_data(self, **kwargs):
        context = super(BuildsTable, self).get_context_data(**kwargs)

        # for the latest builds section
        queryset = Build.objects.all()

        finished_criteria = Q(outcome=Build.SUCCEEDED) | Q(outcome=Build.FAILED)

        latest_builds = itertools.chain(
            queryset.filter(outcome=Build.IN_PROGRESS).order_by("-started_on"),
            queryset.filter(finished_criteria).order_by("-completed_on")[:3]
        )

        context['mru'] = list(latest_builds)
        context['mrb_type'] = 'all'

        return context

    def setup_queryset(self, *args, **kwargs):
        queryset = Build.objects.all()

        # don't include in progress builds
        queryset = queryset.exclude(outcome=Build.IN_PROGRESS)

        # sort
        queryset = queryset.order_by(self.default_orderby)

        # annotate with number of ERROR and EXCEPTION log messages
        queryset = queryset.annotate(
            errors_no = Count(
                'logmessage',
                only = Q(logmessage__level=LogMessage.ERROR) |
                       Q(logmessage__level=LogMessage.EXCEPTION)
            )
        )

        # annotate with number of WARNING log messages
        queryset = queryset.annotate(
            warnings_no = Count(
                'logmessage',
                only = Q(logmessage__level=LogMessage.WARNING)
            )
        )

        self.queryset = queryset

    def setup_columns(self, *args, **kwargs):
        outcome_template = '''
        <a href="{% url "builddashboard" data.id %}">
            {% if data.outcome == data.SUCCEEDED %}
                <i class="icon-ok-sign success"></i>
            {% elif data.outcome == data.FAILED %}
                <i class="icon-minus-sign error"></i>
            {% endif %}
        </a>

        {% if data.cooker_log_path %}
            &nbsp;
            <a href="{% url "build_artifact" data.id "cookerlog" data.id %}">
               <i class="icon-download-alt" title="Download build log"></i>
            </a>
        {% endif %}
        '''

        recipe_template = '''
        {% for target_label in data.target_labels %}
            <a href="{% url "builddashboard" data.id %}">
                {{target_label}}
            </a>
            <br />
        {% endfor %}
        '''

        machine_template = '''
        <a href="{% url "builddashboard" data.id %}">
            {{data.machine}}
        </a>
        '''

        started_on_template = '''
        <a href="{% url "builddashboard" data.id %}">
            {{data.started_on | date:"d/m/y H:i"}}
        </a>
        '''

        completed_on_template = '''
        <a href="{% url "builddashboard" data.id %}">
            {{data.completed_on | date:"d/m/y H:i"}}
        </a>
        '''

        failed_tasks_template = '''
        {% if data.failed_tasks.count == 1 %}
            <a href="{% url "task" data.id data.failed_tasks.0.id %}">
                <span class="error">
                    {{data.failed_tasks.0.recipe.name}}.{{data.failed_tasks.0.task_name}}
                </span>
            </a>
            <a href="{% url "build_artifact" data.id "tasklogfile" data.failed_tasks.0.id %}">
                <i class="icon-download-alt"
                   data-original-title="Download task log file">
                </i>
            </a>
        {% elif data.failed_tasks.count > 1 %}
            <a href="{% url "tasks" data.id %}?filter=outcome%3A{{extra.Task.OUTCOME_FAILED}}">
                <span class="error">{{data.failed_tasks.count}} tasks</span>
            </a>
        {% endif %}
        '''

        errors_template = '''
        {% if data.errors.count %}
            <a class="errors.count error" href="{% url "builddashboard" data.id %}#errors">
                {{data.errors.count}} error{{data.errors.count|pluralize}}
            </a>
        {% endif %}
        '''

        warnings_template = '''
        {% if data.warnings.count %}
            <a class="warnings.count warning" href="{% url "builddashboard" data.id %}#warnings">
                {{data.warnings.count}} warning{{data.warnings.count|pluralize}}
            </a>
        {% endif %}
        '''

        time_template = '''
        {% load projecttags %}
        <a href="{% url "buildtime" data.id %}">
            {{data.timespent_seconds | sectohms}}
        </a>
        '''

        image_files_template = '''
        {% if data.outcome == extra.Build.SUCCEEDED %}
          <a href="{% url "builddashboard" data.id %}#images">
            {{data.get_image_file_extensions}}
          </a>
        {% endif %}
        '''

        project_template = '''
        {% load project_url_tag %}
        <a href="{% project_url data.project %}">
            {{data.project.name}}
        </a>
        {% if data.project.is_default %}
            <i class="icon-question-sign get-help hover-help" title=""
               data-original-title="This project shows information about
               the builds you start from the command line while Toaster is
               running" style="visibility: hidden;"></i>
        {% endif %}
        '''

        self.add_column(title='Outcome',
                        help_text='Final state of the build (successful \
                                   or failed)',
                        hideable=False,
                        orderable=True,
                        filter_name='outcome_filter',
                        static_data_name='outcome',
                        static_data_template=outcome_template)

        self.add_column(title='Recipe',
                        help_text='What was built (i.e. one or more recipes \
                                   or image recipes)',
                        hideable=False,
                        orderable=False,
                        static_data_name='target',
                        static_data_template=recipe_template)

        self.add_column(title='Machine',
                        help_text='Hardware for which you are building a \
                                   recipe or image recipe',
                        hideable=False,
                        orderable=True,
                        static_data_name='machine',
                        static_data_template=machine_template)

        self.add_column(title='Started on',
                        help_text='The date and time when the build started',
                        hideable=True,
                        orderable=True,
                        filter_name='started_on_filter',
                        static_data_name='started_on',
                        static_data_template=started_on_template)

        self.add_column(title='Completed on',
                        help_text='The date and time when the build finished',
                        hideable=False,
                        orderable=True,
                        filter_name='completed_on_filter',
                        static_data_name='completed_on',
                        static_data_template=completed_on_template)

        self.add_column(title='Failed tasks',
                        help_text='The number of tasks which failed during \
                                   the build',
                        hideable=True,
                        orderable=False,
                        filter_name='failed_tasks_filter',
                        static_data_name='failed_tasks',
                        static_data_template=failed_tasks_template)

        self.add_column(title='Errors',
                        help_text='The number of errors encountered during \
                                   the build (if any)',
                        hideable=True,
                        orderable=False,
                        static_data_name='errors',
                        static_data_template=errors_template)

        self.add_column(title='Warnings',
                        help_text='The number of warnings encountered during \
                                   the build (if any)',
                        hideable=True,
                        orderable=False,
                        static_data_name='warnings',
                        static_data_template=warnings_template)

        self.add_column(title='Time',
                        help_text='How long the build took to finish',
                        hideable=False,
                        orderable=False,
                        static_data_name='time',
                        static_data_template=time_template)

        self.add_column(title='Image files',
                        help_text='The root file system types produced by \
                                   the build',
                        hideable=True,
                        orderable=False,
                        static_data_name='image_files',
                        static_data_template=image_files_template)

        self.add_column(title='Project',
                        hideable=True,
                        orderable=False,
                        static_data_name='project-name',
                        static_data_template=project_template)

    def setup_filters(self, *args, **kwargs):
        # outcomes
        outcome_filter = TableFilter(
            'outcome_filter',
            'Filter builds by outcome'
        )

        successful_builds_action = TableFilterActionToggle(
            'successful_builds',
            'Successful builds',
            QuerysetFilter(Q(outcome=Build.SUCCEEDED))
        )

        failed_builds_action = TableFilterActionToggle(
            'failed_builds',
            'Failed builds',
            QuerysetFilter(Q(outcome=Build.FAILED))
        )

        outcome_filter.add_action(successful_builds_action)
        outcome_filter.add_action(failed_builds_action)
        self.add_filter(outcome_filter)

        # started on
        started_on_filter = TableFilter(
            'started_on_filter',
            'Filter by date when build was started'
        )

        started_today_action = TableFilterActionDay(
            'today',
            'Today\'s builds',
            'started_on',
            'today'
        )

        started_yesterday_action = TableFilterActionDay(
            'yesterday',
            'Yesterday\'s builds',
            'started_on',
            'yesterday'
        )

        by_started_date_range_action = TableFilterActionDateRange(
            'date_range',
            'Build date range',
            'started_on'
        )

        started_on_filter.add_action(started_today_action)
        started_on_filter.add_action(started_yesterday_action)
        started_on_filter.add_action(by_started_date_range_action)
        self.add_filter(started_on_filter)

        # completed on
        completed_on_filter = TableFilter(
            'completed_on_filter',
            'Filter by date when build was completed'
        )

        completed_today_action = TableFilterActionDay(
            'today',
            'Today\'s builds',
            'completed_on',
            'today'
        )

        completed_yesterday_action = TableFilterActionDay(
            'yesterday',
            'Yesterday\'s builds',
            'completed_on',
            'yesterday'
        )

        by_completed_date_range_action = TableFilterActionDateRange(
            'date_range',
            'Build date range',
            'completed_on'
        )

        completed_on_filter.add_action(completed_today_action)
        completed_on_filter.add_action(completed_yesterday_action)
        completed_on_filter.add_action(by_completed_date_range_action)
        self.add_filter(completed_on_filter)

        # failed tasks
        failed_tasks_filter = TableFilter(
            'failed_tasks_filter',
            'Filter builds by failed tasks'
        )

        criteria = Q(task_build__outcome=Task.OUTCOME_FAILED)

        with_failed_tasks_action = TableFilterActionToggle(
            'with_failed_tasks',
            'Builds with failed tasks',
            QuerysetFilter(criteria)
        )

        without_failed_tasks_action = TableFilterActionToggle(
            'without_failed_tasks',
            'Builds without failed tasks',
            QuerysetFilter(~criteria)
        )

        failed_tasks_filter.add_action(with_failed_tasks_action)
        failed_tasks_filter.add_action(without_failed_tasks_action)
        self.add_filter(failed_tasks_filter)
