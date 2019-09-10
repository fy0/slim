from wtforms import Form
import locale

class ValidateForm(Form):
    class Meta:
        locales = ['zh_CN']
        # locales = [locale.getdefaultlocale()[0]]
