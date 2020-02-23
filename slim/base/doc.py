
class DocMeta:
    def __init__(self, summary=None, description=None):
        """
        :param summary:
        :param description:
        """
        self.summary = summary
        self.description = description


class ApplicationDocInfo:
    def __init__(self, title='slim application', description='', license=None, version='1.0.0',
                 contact=None):
        self.title = title
        self.description = description
        self.license = license
        self.version = version
        self.contact = contact
