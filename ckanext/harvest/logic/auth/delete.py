from ckan.plugins import toolkit as pt
from ckanext.harvest.logic.auth import user_is_sysadmin

def harvest_source_delete(context, data_dict):
    '''
        Authorization check for harvest source deletion

        Only sysadmins can do it
    '''
    model = context.get('model')
    user = context.get('user')
    source_id = data_dict['id']

    pkg = model.Package.get(source_id)
    if not pkg:
        raise pt.ObjectNotFound(pt._('Harvest source not found'))

    context['package'] = pkg

    if not user_is_sysadmin(context):
        return {'success': False,
                'msg': pt._('User {0} not authorized to update harvest source {1}').format(user, source_id)}

    else:
        return {'success': True}
