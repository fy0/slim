from slim.utils.autoload import import_path

from app import app
import config
import permissions.roles_apply


if __name__ == '__main__':
    import model._models

    import_path('./api')
    app.run(host=config.HOST, port=config.PORT)
