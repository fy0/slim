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
        self.description = description
        self.license = license
        self.version = version
        self.contact = contact
