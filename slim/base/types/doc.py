from collections import OrderedDict
from typing import List

from slim.utils.jsdict import JsDict


class ValidatorDoc(JsDict):
    def __init__(self, description, schema=None, **kwargs):
        """
        :param summary:
        :param description:
        """
        super().__init__(**kwargs)
        self.description = description
        self.schema = schema


class ApplicationDocInfo:
    def __init__(self, title='slim application', description='', license=None, version='1.0.0',
                 contact=None):
        self.title = title
        self.description = description.strip()
        self.license = license
        self.version = version
        self.contact = contact
        self.tags = OrderedDict()
        self.x_tag_groups = OrderedDict()

    def add_tag(self, name, description, display_name=None, index=-1):
        """
        :param name:
        :param description:
        :param display_name:
        :param index:
        :return:
        """
        tag_data = {
            'name': name,
            'description': description.strip(),
            'x-slim-index': index
        }

        if display_name is not None:
            tag_data['x-displayName'] = display_name

        self.tags[name] = tag_data

    def add_x_tag_group(self, name: str, tags: List[str], index=-1):
        """
        :param name:
        :param tags:
        :param index:
        :return:
        """
        self.x_tag_groups[name] = {'name': name, 'tags': tags, 'x-slim-index': index}
