from app import app
import config
import permissions.roles_apply

if __name__ == '__main__':
    import model._models
    import view._views
    app.run(host=config.HOST, port=config.PORT)
