from ckan.plugins import toolkit as pt
from ckanext.harvest.logic.auth import user_is_sysadmin


def harvest_source_create(context, data_dict):
    '''
        Authorization check for harvest source creation

        Only sysadmins can do it
    '''
    user = context.get('user')

    if not user_is_sysadmin(context):
        return {'success': False,
                'msg': pt._('User {0} not authorized to create harvest sources').format(user)}
    else:
        return {'success': True}


def harvest_job_create(context, data_dict):
    '''
        Authorization check for harvest job creation

        It forwards the checks to package_update, ie the user can only create
        new jobs if she is allowed to edit the harvest source dataset.
    '''
    model = context['model']
    source_id = data_dict['source_id']

    pkg = model.Package.get(source_id)
    if not pkg:
        raise pt.ObjectNotFound(pt._('Harvest source not found'))

    context['package'] = pkg
    try:
        pt.check_access('package_update', context, {"id": source_id})
        return {'success': True}
    except pt.NotAuthorized:
        return {'success': False,
                'msg': pt._('User not authorized to create a job for source {0}').format(source_id)}


def harvest_job_create_all(context, data_dict):
    '''
        Authorization check for creating new jobs for all sources

        Only sysadmins can do it
    '''
    if not user_is_sysadmin(context):
        return {'success': False, 'msg': pt._('Only sysadmins can create harvest jobs for all sources')}
    else:
        return {'success': True}


def harvest_object_create(context, data_dict):
    """
        Auth check for creating a harvest object

        only the sysadmins can create harvest objects
    """
    # sysadmins can run all actions if we've got to this point we're not a sysadmin
    return {'success': False, 'msg': pt._('Only the sysadmins can create harvest objects')}
