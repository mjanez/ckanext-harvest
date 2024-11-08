from sqlalchemy import func, text
import logging
import json

from ckan.model import Group
from ckan import logic
from ckanext.harvest.model import (HarvestJob, HarvestObject,
                                   HarvestGatherError, HarvestObjectError)

log = logging.getLogger(__name__)

PRIVATE_KEYS = ['api_key', 'credentials', 'password', 'secret', 'token']

def remove_private_keys(data):
    """
    Removes private keys from a dictionary, including nested dictionaries.

    Args:
        data (dict): The dictionary from which private keys will be removed.

    Returns:
        dict: The dictionary without private keys.
    """
    if isinstance(data, dict):
        # Create a new dictionary to avoid modifying the original data
        new_data = {}
        for key, value in data.items():
            if key in PRIVATE_KEYS:
                continue
            elif key == 'config' and isinstance(value, str):
                try:
                    config_dict = json.loads(value)
                    # Recursively remove private keys from the config dict
                    new_config = remove_private_keys(config_dict)
                    new_data[key] = json.dumps(new_config)
                except ValueError:
                    new_data[key] = value
            else:
                new_data[key] = remove_private_keys(value)
        return new_data
    elif isinstance(data, list):
        # Recursively process list items
        return [remove_private_keys(item) for item in data]
    else:
        return data

def harvest_source_dictize(source, context, last_job_status=False):
    out = source.as_dict()

    out['publisher_title'] = u''

    publisher_id = out.get('publisher_id')
    if publisher_id:
        group = Group.get(publisher_id)
        if group:
            out['publisher_title'] = group.title

    out['status'] = _get_source_status(source, context)

    if last_job_status:
        source_status = logic.get_action('harvest_source_show_status')(context, {'id': source.id})
        out['last_job_status'] = source_status.get('last_job', {})

    # Remove private keys
    out = remove_private_keys(out)

    return out


def harvest_job_dictize(job, context):
    out = job.as_dict()

    model = context['model']

    if context.get('return_stats', True):
        stats = model.Session.query(
            HarvestObject.report_status,
            func.count(HarvestObject.id).label('total_objects'))\
            .filter_by(harvest_job_id=job.id)\
            .group_by(HarvestObject.report_status).all()
        out['stats'] = {'added': 0, 'updated': 0, 'not modified': 0,
                        'errored': 0, 'deleted': 0}
        for status, count in stats:
            out['stats'][status] = count

        # We actually want to check which objects had errors, because they
        # could have been added/updated anyway (eg bbox errors)
        count = model.Session.query(
            func.distinct(HarvestObjectError.harvest_object_id)) \
            .join(HarvestObject) \
            .filter(HarvestObject.harvest_job_id == job.id) \
            .count()
        if count > 0:
            out['stats']['errored'] = count

        # Add gather errors to the error count
        count = model.Session.query(HarvestGatherError) \
            .filter(HarvestGatherError.harvest_job_id == job.id) \
            .count()
        if count > 0:
            out['stats']['errored'] = out['stats'].get('errored', 0) + count

    if context.get('return_error_summary', True):
        q = model.Session.query(
            HarvestObjectError.message,
            func.count(HarvestObjectError.message).label('error_count')) \
            .join(HarvestObject) \
            .filter(HarvestObject.harvest_job_id == job.id) \
            .group_by(HarvestObjectError.message) \
            .order_by(text('error_count desc')) \
            .limit(context.get('error_summmary_limit', 20))
        out['object_error_summary'] = harvest_error_dictize(q.all(), context)
        q = model.Session.query(
            HarvestGatherError.message,
            func.count(HarvestGatherError.message).label('error_count')) \
            .filter(HarvestGatherError.harvest_job_id == job.id) \
            .group_by(HarvestGatherError.message) \
            .order_by(text('error_count desc')) \
            .limit(context.get('error_summmary_limit', 20))
        out['gather_error_summary'] = harvest_error_dictize(q.all(), context)

    # Remove private keys
    out = remove_private_keys(out)

    return out

def harvest_object_dictize(obj, context):
    out = obj.as_dict()
    out['source'] = obj.harvest_source_id
    out['job'] = obj.harvest_job_id

    if obj.package:
        out['package'] = obj.package.id

    out['errors'] = []
    for error in obj.errors:
        out['errors'].append(error.as_dict())

    out['extras'] = {}
    for extra in obj.extras:
        out['extras'][extra.key] = extra.value

    # Remove private keys
    out = remove_private_keys(out)

    return out

def harvest_log_dictize(obj, context):
    out = obj.as_dict()
    del out['id']

    return out

def harvest_error_dictize(obj, context):
    out = []
    for elem in obj:
        out.append(elem._asdict())
    return out

def _get_source_status(source, context):
    '''
    TODO: Deprecated, use harvest_source_show_status instead
    '''

    out = dict()

    job_count = HarvestJob.filter(source=source).count()

    out = {
        'job_count': 0,
        'next_harvest': '',
        'last_harvest_request': '',
        }

    if not job_count:
        out['msg'] = 'No jobs yet'
        return out
    else:
        out['job_count'] = job_count

    # Get next scheduled job
    next_job = HarvestJob.filter(source=source, status=u'New').first()
    if next_job:
        out['next_harvest'] = 'Scheduled'
    else:
        out['next_harvest'] = 'Not yet scheduled'

    # Get the last finished job
    last_job = HarvestJob.filter(source=source, status=u'Finished') \
        .order_by(HarvestJob.created.desc()).first()

    if last_job:
        out['last_harvest_request'] = str(last_job.gather_finished)
    else:
        out['last_harvest_request'] = 'Not yet harvested'

    return out
