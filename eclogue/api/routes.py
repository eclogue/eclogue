from eclogue.api.menus import Menus
from eclogue.api.catheter import Catheter
from eclogue.api.key import add_key
from eclogue.api.auth import Auth
from eclogue.api.deviece import add_deviece, get_devices, get_device_info
from eclogue.api.host import dump_inventory
from eclogue.api.bookshelf import get_entry
from eclogue.api.role import add_role, get_roles, update_role
from eclogue.api.user import search_user, get_user_info, bind_role, \
    add_user, get_current_roles, get_profile, bind_hosts
import eclogue.api.inventory as cmdb
from eclogue.api.credential import credentials, add_credential, update_credential
from eclogue.api.playbook import get_playbook, get_tags, edit_file, remove_file
from eclogue.api.job import get_jobs, get_job, add_jobs, check_job, \
    job_detail, runner_doc, runner_module, add_adhoc, test_job
from eclogue.api.app import get_apps, add_apps
from eclogue.api.console import run_task
from eclogue.api.playbook import import_galaxy
import eclogue.api.team as team
import eclogue.api.notification as notification
import eclogue.api.docker as docker
import eclogue.api.gitlab as gitlab
import eclogue.api.log as log
import eclogue.api.configuration as configuration
import eclogue.api.task as task
import eclogue.api.book as book
import eclogue.api.playbook as playbook

routes = [
    ('/login', Auth.login, ['POST']),
    ('/menus', Menus.get_menus, ['GET']),
    ('/menus', Menus.add, ['POST']),
    ('/playbook/dumper', Catheter.get, ['GET']),
    ('/playbook/dumper', Catheter.drop, ['DELETE']),
    ('/playbook/keys', add_key, ['POST']),
    ('/playbook/rename/<_id>', playbook.rename, ['PATCH']),
    ('/playbook/upload', Catheter.upload, ['POST']),
    ('/playbook/folder', Catheter.add_folder, ['POST']),
    ('/playbook/setup', Catheter.setup, ['POST']),
    ('/playbook/galaxy', import_galaxy, ['get']),
    ('/playbook/tags', get_tags, ['post']),
    ('/playbook/<_id>/file', edit_file, ['put']),
    ('/playbook/<_id>/file', remove_file, ['delete']),
    ('/playbook/edit/<_id>', Catheter.get_file, ['GET']),
    ('/tasks', task.monitor, ['get']),
    ('/tasks/queue', task.get_queue_tasks, ['get']),
    ('/tasks/history', task.get_task_history, ['get']),
    ('/tasks/<_id>/retry', task.retry, ['post']),
    ('/tasks/<_id>/<state>/cancel', task.cancel, ['delete']),
    ('/inventory/dumper', dump_inventory, ['GET', 'POST']),
    ('/books/all', book.all_books, ['GET']),
    ('/books', book.add_book, ['POST']),
    ('/books/<_id>', book.book_detail, ['get']),
    ('/books/<_id>', book.edit_book, ['put']),
    ('/books', book.books, ['get']),
    ('/books/<_id>/playbook', get_playbook, ['GET']),
    ('/books/<_id>/download', book.download_book, ['GET']),
    ('/books/<_id>/playbook', book.upload_playbook, ['post']),
    ('/books/<_id>/entries', get_entry, ['GET']),
    ('/books/<name>/inventory', cmdb.get_inventory_by_book, ['GET']),
    ('/books/<_id>/roles', cmdb.get_roles_by_book, ['GET']),
    ('/inventory', cmdb.explore, ['post']),
    ('/search/users', search_user, ['get']),
    ('/cmdb/regions', cmdb.regions, ['get']),
    ('/cmdb/regions', cmdb.add_region, ['post']),
    ('/cmdb/regions/<_id>', cmdb.update_region, ['put']),
    ('/cmdb/groups', cmdb.groups, ['get']),
    ('/cmdb/groups', cmdb.add_group, ['post']),
    ('/cmdb/groups/<_id>', cmdb.update_group, ['put']),
    ('/cmdb/groups/<_id>', cmdb.get_group_info, ['get']),
    ('/cmdb/groups/<_id>/hosts', cmdb.get_group_hosts, ['get']),
    ('/cmdb/inventory', cmdb.get_inventory, ['get']),
    ('/cmdb/hosts/<_id>', cmdb.get_node_info, ['get']),
    ('/cmdb/hosts', cmdb.get_inventory, ['get']),
    ('/cmdb/<user_id>/groups', cmdb.get_host_groups, ['get']),
    ('/devices/add', add_deviece, ['POST']),
    ('/devices', cmdb.get_devices, ['GET']),
    ('/devices/<_id>', get_device_info, ['GET']),
    ('/jobs/preview/inventory', cmdb.preview_inventory, ['post']),
    ('/jobs', get_jobs, ['get']),
    ('/jobs', add_jobs, ['post']),
    ('/jobs/<_id>', get_job, ['get']),
    ('/jobs/<_id>', check_job, ['post']),
    ('/jobs/<_id>/tasks', job_detail, ['get']),
    ('/jobs/runner/doc', runner_doc, ['get']),
    ('/jobs/runner/modules', runner_module, ['get']),
    ('/credentials', credentials, ['get']),
    ('/credentials', add_credential, ['post']),
    ('/credentials/_id', update_credential, ['put']),
    ('/apps', get_apps, ['get']),
    ('/apps', add_apps, ['post']),
    ('/configurations', configuration.list_config, ['get']),
    ('/configurations/<playbook_id>/register', configuration.get_register_config, ['get']),
    ('/configurations/<_id>', configuration.update_configuration, ['put']),
    ('/configurations/<_id>', configuration.get_config_info, ['get']),
    ('/configurations', configuration.add_configuration, ['post']),
    ('/configurations/list/ids', configuration.get_configs_by_ids, ['get']),
    ('/execute', run_task, ['post']),
    ('/teams', team.add_team, ['post']),
    ('/teams', team.get_team_tree, ['get']),
    ('/teams/<_id>', team.get_team_info, ['get']),
    ('/teams/members', team.add_user_to_team, ['post']),
    ('/users', add_user, ['post']),
    ('/users/<_id>', get_user_info, ['get']),
    ('/users/<_id>/profile', get_profile, ['get']),
    ('/users/roles', get_current_roles, ['get']),
    ('/users/<user_id>/roles', bind_role, ['post']),
    ('/users/<user_id>/hosts', bind_hosts, ['post']),
    ('/roles', add_role, ['post']),
    ('/roles', get_roles, ['get']),
    ('/roles/<_id>', update_role, ['put']),
    ('/notifications', notification.get_notify, ['get']),
    ('/notifications/read', notification.mark_read, ['put']),
    ('/docker', docker.test_docker, ['get']),
    ('/test/git', test_job, ['get']),
    ('/logs', log.log_query, ['get']),

]
