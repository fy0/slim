from collections import OrderedDict
from typing import List

from schematics import Model
from schematics.types import IntType, StringType, BaseType

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

    def add_x_tag_group(self, name: str, tags: List[str], display_name=None, index=-1):
        """
        :param name:
        :param tags:
        :param index:
        :return:
        """
        data = {'name': name, 'tags': tags, 'x-slim-index': index}

        if display_name is not None:
            data['x-displayName'] = display_name

        self.x_tag_groups[name] = data


class ResponseDataModel(Model):
    code = IntType(required=True, metadata=ValidatorDoc('系统返回值代码，成功为0，失败为非零。  \n参见 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=返回值 '))
    data = BaseType(required=True, metadata=ValidatorDoc('数据项'))
    msg = StringType(metadata=ValidatorDoc('文本提示信息'))
