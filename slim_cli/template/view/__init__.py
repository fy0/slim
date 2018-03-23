try:
    from wtforms import Form
    import locale

    class ValidateForm(Form):
        class Meta:
            locales = [locale.getdefaultlocale()[0]]

except ImportError:
    pass
