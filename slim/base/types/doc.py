from collections import OrderedDict
from dataclasses import dataclass, Field, field
from typing import List, Optional

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


@dataclass
class ApplicationDocInfo:
    title: str = 'slim application'
    description: str = ''
    license: Optional[str] = None
    version: str = '1.0.0'
    contact: Optional[str] = None
    tags: OrderedDict = field(default_factory=lambda: OrderedDict())
    x_tag_groups: OrderedDict = field(default_factory=lambda: OrderedDict())
    roles: Optional[str] = None

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
